"""Explicit, human-triggered Codex CLI runs; task data is read via MCP."""

import asyncio
import json
import logging
from datetime import UTC, datetime
import os
from pathlib import Path
import shutil
import signal

from agent_kanban.auth import generate_token, hash_token
from agent_kanban.config import get_settings
from agent_kanban.db import AsyncSessionLocal
from agent_kanban.events import event_bus
from agent_kanban.models import Comment, TaskStatus, Token
from agent_kanban.services import locked_task, record_transition, task_context

logger = logging.getLogger(__name__)
_runs: dict[int, asyncio.Task] = {}


async def launch_agent(session, task_id: int, actor: str) -> dict:
    settings = get_settings()
    executable = shutil.which(settings.codex_command)
    if executable is None:
        raise ValueError("Codex CLI не найден на сервере: настройте CODEX_COMMAND и codex login")
    task = await locked_task(session, task_id)
    if task_id in _runs:
        raise ValueError("Агент уже запущен для этой задачи")
    if task.status not in {TaskStatus.READY, TaskStatus.REVIEW}:
        raise ValueError("Запуск доступен только в колонках Готово и Ревью")
    review = task.status == TaskStatus.REVIEW
    if (review and task.reviewer) or (not review and task.claimed_by):
        raise ValueError("Задача уже занята агентом")
    context = await task_context(session, task_id)
    repo = context["repo_path"]
    if not repo or not Path(repo).is_absolute() or not Path(repo).is_dir():
        raise ValueError("Укажите существующий абсолютный путь к репозиторию на сервере")
    # Use the assigned identity, so assignment restrictions remain effective.
    agent = (task.review_assigned_to if review else task.assigned_to) or "codex"
    secret = generate_token()
    token = Token(
        agent_name=agent,
        token_hash=hash_token(secret),
        token_prefix=secret[:8],
        description=f"Manual run for task #{task_id}",
        created_by_user_id=int(actor.removeprefix("user:")),
    )
    session.add(token)
    if review:
        task.reviewer = agent
    else:
        task.claimed_by = agent
        task.claimed_at = datetime.now(UTC).replace(tzinfo=None)
    record_transition(
        session,
        task,
        actor,
        TaskStatus.REVIEW if review else TaskStatus.IN_PROGRESS,
        "Codex запущен вручную пользователем",
        "LAUNCH_AGENT",
    )
    await session.commit()
    run = asyncio.create_task(_execute(task_id, token.id, agent, secret, repo, review, executable))
    _runs[task_id] = run
    run.add_done_callback(lambda _: _runs.pop(task_id, None))
    await _publish("agent_started", task_id)
    return {"task_id": task_id, "agent": agent, "mode": "review" if review else "work"}


async def _execute(task_id, token_id, agent, secret, repo, review, executable):
    process = None
    message = "Codex завершил запуск"
    settings = get_settings()
    try:
        env = os.environ.copy()
        env["AITASKER_RUN_TOKEN"] = secret
        url = settings.codex_mcp_url or settings.public_url.rstrip("/") + "/mcp"
        args = [
            executable,
            "exec",
            "--ephemeral",
            "-C",
            repo,
            "-s",
            "read-only" if review else "workspace-write",
            "-c",
            "mcp_servers={}",
            "-c",
            "mcp_servers.tasker.url=" + json.dumps(url),
            "-c",
            'mcp_servers.tasker.bearer_token_env_var="AITASKER_RUN_TOKEN"',
            "-",
        ]
        finish = (
            f"Perform a code review without changing files. Call submit_review with task_id={task_id}, "
            f"agent={json.dumps(agent)}, decision APPROVE or REQUEST_CHANGES and detailed findings."
            if review
            else f"Execute the task and verify the result. Report progress via post_progress. "
            f"Finish with request_review(task_id={task_id}, agent={json.dumps(agent)}, summary=your detailed work/test summary)."
        )
        prompt = (
            f"The human explicitly launched you for AI Tasker task #{task_id}. "
            f"It is already claimed for you as {json.dumps(agent)}; do not claim it again. "
            f"First call tasker.get_task_context(task_id={task_id}) through MCP, then obey its full "
            f"agent_prompt, project/task instructions and local AGENTS.md. Work only in {repo}. "
            "Do not execute other tasks, commit, push or accept work as a human. " + finish
        )
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=repo,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        await asyncio.wait_for(
            process.communicate(prompt.encode()), timeout=settings.codex_timeout_seconds
        )
        if process.returncode:
            message = f"Codex завершился с ошибкой (код {process.returncode}). Проверьте codex login и подключение MCP на сервере."
    except asyncio.TimeoutError:
        message = "Запуск Codex остановлен по таймауту"
    except asyncio.CancelledError:
        message = "Запуск Codex остановлен при выключении сервера"
        raise
    except Exception:
        logger.exception("Codex launch failed for task %s", task_id)
        message = "Не удалось запустить Codex на сервере"
    finally:
        if process and process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except AttributeError:  # process doubles in tests
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
        async with AsyncSessionLocal() as session:
            task = await locked_task(session, task_id)
            # A missing MCP completion releases the reservation for a manual retry.
            if review and task.status == TaskStatus.REVIEW and task.reviewer == agent:
                task.reviewer = None
                task.updated_at = datetime.now(UTC).replace(tzinfo=None)
                message += "; ревью не отправлено, запуск можно повторить"
            elif not review and task.status == TaskStatus.IN_PROGRESS and task.claimed_by == agent:
                task.claimed_by = None
                task.claimed_at = None
                record_transition(
                    session,
                    task,
                    agent,
                    TaskStatus.READY,
                    "Запуск завершён без результата MCP; доступен повторный запуск",
                )
                message += "; результат не отправлен на ревью, запуск можно повторить"
            token = await session.get(Token, token_id)
            if token:
                await session.delete(token)
            session.add(Comment(task_id=task_id, author="system", content=message))
            await session.commit()
        await _publish("agent_finished", task_id)


async def stop_runs():
    runs = list(_runs.values())
    for run in runs:
        run.cancel()
    await asyncio.gather(*runs, return_exceptions=True)


async def _publish(kind, task_id):
    payload = {"type": kind, "task_id": task_id}
    await event_bus.publish("board", payload)
    await event_bus.publish(f"task:{task_id}", payload)
