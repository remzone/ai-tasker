import asyncio
from pathlib import Path

import pytest
from sqlmodel import select

from agent_kanban import agent_runner as runner
from agent_kanban.db import AsyncSessionLocal
from agent_kanban.models import Comment, Task, TaskStatus, Token


async def create_ready(client):
    return (
        await client.post(
            "/api/tasks",
            json={
                "title": "Manual run",
                "status": "ready",
                "repo_path": str(Path.cwd()),
            },
        )
    ).json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("review", [False, True])
async def test_manual_run_mcp_completion(authed_client, monkeypatch, review):
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/fake/codex")
    task_id = await create_ready(authed_client)
    if review:
        await authed_client.post(f"/api/tasks/{task_id}/workflow", json={"action": "start"})
        await authed_client.post(
            f"/api/tasks/{task_id}/workflow", json={"action": "review", "comment": "Completed"}
        )
    captured = {}

    class Process:
        returncode = None

        async def communicate(self, prompt):
            captured["prompt"] = prompt.decode()
            async with AsyncSessionLocal() as session:
                from agent_kanban.services import request_review, submit_review

                if review:
                    await submit_review(session, task_id, "codex", "APPROVE", "Tests passed")
                else:
                    await request_review(session, task_id, "codex", "Implemented and tested")
            self.returncode = 0

    async def spawn(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return Process()

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn)
    response = await authed_client.post(f"/api/tasks/{task_id}/run-agent")
    assert response.status_code == 202
    await asyncio.gather(*list(runner._runs.values()))
    task = (await authed_client.get(f"/api/tasks/{task_id}")).json()
    assert task["status"] == ("acceptance" if review else "review")
    assert "get_task_context" in captured["prompt"]
    assert ("read-only" if review else "workspace-write") in captured["args"]
    secret = captured["env"]["AITASKER_RUN_TOKEN"]
    assert all(secret not in arg for arg in captured["args"])
    async with AsyncSessionLocal() as session:
        assert not (await session.execute(select(Token))).scalars().all()


@pytest.mark.asyncio
@pytest.mark.parametrize("review", [False, True])
async def test_failure_releases_reservation_and_token(authed_client, monkeypatch, review):
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/fake/codex")
    task_id = await create_ready(authed_client)
    if review:
        await authed_client.post(f"/api/tasks/{task_id}/workflow", json={"action": "start"})
        await authed_client.post(
            f"/api/tasks/{task_id}/workflow", json={"action": "review", "comment": "Completed"}
        )

    async def spawn(*args, **kwargs):
        raise OSError("Unavailable")

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn)
    assert (await authed_client.post(f"/api/tasks/{task_id}/run-agent")).status_code == 202
    await asyncio.gather(*list(runner._runs.values()))
    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        assert task.status == (TaskStatus.REVIEW if review else TaskStatus.READY)
        assert task.reviewer is None and task.claimed_by is None
        assert not (await session.execute(select(Token))).scalars().all()
        assert (
            (await session.execute(select(Comment).where(Comment.author == "system")))
            .scalars()
            .all()
        )


@pytest.mark.asyncio
async def test_double_click_and_shutdown(authed_client, monkeypatch):
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/fake/codex")
    task_id = await create_ready(authed_client)
    killed = []

    class Process:
        returncode = None

        async def communicate(self, prompt):
            await asyncio.Event().wait()

        def kill(self):
            killed.append(True)
            self.returncode = -9

        async def wait(self):
            return self.returncode

    async def spawn(*args, **kwargs):
        return Process()

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn)
    assert (await authed_client.post(f"/api/tasks/{task_id}/run-agent")).status_code == 202
    await asyncio.sleep(0)
    assert (await authed_client.post(f"/api/tasks/{task_id}/run-agent")).status_code == 409
    await runner.stop_runs()
    assert killed
    assert (await authed_client.get(f"/api/tasks/{task_id}")).json()["status"] == "ready"


@pytest.mark.asyncio
async def test_reject_token_missing_cli_and_invalid_status(authed_client, monkeypatch):
    task_id = await create_ready(authed_client)
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    assert (await authed_client.post(f"/api/tasks/{task_id}/run-agent")).status_code == 409
    assert (await authed_client.get(f"/api/tasks/{task_id}")).json()["status"] == "ready"
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/fake/codex")
    await authed_client.patch(f"/api/tasks/{task_id}", json={"status": "todo"})
    assert (await authed_client.post(f"/api/tasks/{task_id}/run-agent")).status_code == 409
    token = (await authed_client.post("/api/tokens", json={"agent_name": "codex"})).json()["token"]
    authed_client.cookies.clear()
    assert (
        await authed_client.post(
            f"/api/tasks/{task_id}/run-agent", headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 403
