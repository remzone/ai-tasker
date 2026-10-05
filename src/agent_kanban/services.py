"""Business logic shared by REST routes and MCP tools.

Authorization rule (spec §5.3): mutations require task.claimed_by == calling agent.
We raise PermissionError on violation so callers can map to HTTP 403 / MCP error.
"""
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from agent_kanban.events import event_bus
from agent_kanban.git import GitError, collect_diff, collect_diffstats, resolve_base_branch
from agent_kanban.models import (
    Artifact,
    Comment,
    ProgressEvent,
    Project,
    Task,
    TaskStatus,
)
from agent_kanban.schemas import (
    ArtifactCreate,
    ClaimResult,
    ProgressCreate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)


def _to_task_read(task: Task) -> TaskRead:
    # ClaimResult.task is typed TaskRead; bridge ORM -> schema explicitly.
    return TaskRead.model_validate(task, from_attributes=True)


def _check_claimer(task: Task, agent: str) -> None:
    if task.claimed_by != agent:
        raise PermissionError(
            f"task {task.id} is claimed by {task.claimed_by!r}, not {agent!r}"
        )


def _is_path_allowed(path: str, allowed_roots: list[str]) -> bool:
    p = Path(path).expanduser().resolve()
    for root in allowed_roots:
        try:
            p.relative_to(Path(root).expanduser().resolve())
            return True
        except ValueError:
            continue
    return False


async def _publish_task_event(channel: str, evt_type: str, task: Task) -> None:
    payload = {
        "type": evt_type,
        "task_id": task.id,
        "status": task.status.value if isinstance(task.status, TaskStatus) else task.status,
    }
    await event_bus.publish(channel, payload)
    await event_bus.publish(f"task:{task.id}", payload)


# ---- Task CRUD ----
async def create_task(session: AsyncSession, data: TaskCreate) -> Task:
    if data.status not in (TaskStatus.TODO, TaskStatus.READY):
        raise ValueError("new tasks must start in todo or ready")
    values = data.model_dump()
    if data.project_id is not None:
        project = await session.get(Project, data.project_id)
        if project is None:
            raise ValueError("project not found")
        values["repo_path"] = data.repo_path or project.repo_path
        values["base_branch"] = data.base_branch or project.default_branch
    values["title"] = data.title.strip()
    if not values["title"]:
        raise ValueError("task title is required")
    task = Task(**values)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "task_created", task)
    return task


async def update_task(session: AsyncSession, task_id: int, data: TaskUpdate) -> Task:
    task = await locked_task(session, task_id)
    changes = data.model_dump(exclude_unset=True)
    target = changes.get("status")
    if target is not None and target != task.status:
        # Drag-and-drop is for planning only. Agent work, review and acceptance
        # use dedicated operations so a PATCH cannot bypass any gate.
        allowed = {
            TaskStatus.TODO: {TaskStatus.READY},
            TaskStatus.READY: {TaskStatus.TODO},
            TaskStatus.BLOCKED: {TaskStatus.READY},
            TaskStatus.CANCELLED: {TaskStatus.TODO},
            TaskStatus.DONE: {TaskStatus.TODO},
        }
        if target not in allowed.get(task.status, set()):
            raise ValueError("transition requires claim, AI review or human acceptance")
        record_transition(session, task, "user", target, "Planning transition")
        task.claimed_by = None
        task.claimed_at = None
        task.review_assigned_to = None
        task.reviewer = None
    if any(changes.get(k) is None for k in ("title", "description", "acceptance_criteria", "agent_instructions", "tags") if k in changes):
        raise ValueError("task content cannot be null")
    if changes.get("project_id") is not None and await session.get(Project, changes["project_id"]) is None:
        raise ValueError("project not found")
    if "title" in changes:
        changes["title"] = changes["title"].strip()
        if not changes["title"]:
            raise ValueError("task title is required")
    for k, v in changes.items():
        setattr(task, k, v)
    task.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "task_updated", task)
    return task


def _assigned_to_or_open(agent: Optional[str]):
    """SQLAlchemy filter: task is unassigned OR assigned to the given agent.

    When ``agent`` is None (the REST/UI path), returns no filter — the board
    shows every task to the human operator regardless of assignment.
    """
    if agent is None:
        return None
    return (Task.assigned_to.is_(None)) | (Task.assigned_to == agent)


async def list_tasks(
    session: AsyncSession,
    status: Optional[TaskStatus] = None,
    tags_any: Optional[list[str]] = None,
    agent: Optional[str] = None,
    project_id: Optional[int] = None,
) -> list[Task]:
    """List tasks. When ``agent`` is given (MCP path), only tasks that are
    unassigned OR assigned to that agent are returned — hard-assignment hiding.
    The UI path (agent=None) sees everything."""
    stmt = select(Task).order_by(Task.sort_order, Task.created_at)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    assigned_filter = _assigned_to_or_open(agent)
    if assigned_filter is not None:
        stmt = stmt.where(assigned_filter)
    result = await session.execute(stmt)
    tasks = result.scalars().all()
    if tags_any:
        tasks = [t for t in tasks if any(tag in t.tags for tag in tags_any)]
    return list(tasks)


async def get_task(session: AsyncSession, task_id: int) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise ValueError(f"task {task_id} not found")
    return task


async def get_next_task(
    session: AsyncSession,
    tags_any: Optional[list[str]],
    tags_all: Optional[list[str]],
    exclude_tags: Optional[list[str]],
    agent: Optional[str] = None,
    project_id: Optional[int] = None,
) -> Optional[Task]:
    """Return the next READY task (oldest first). When ``agent`` is given (MCP
    path), only tasks unassigned OR assigned to that agent are eligible — other
    agents' reserved tasks are invisible here."""
    stmt = (
        select(Task)
        .where((Task.status == TaskStatus.READY) | ((Task.status == TaskStatus.IN_PROGRESS) & (Task.claimed_by.is_(None))))
        .order_by(Task.sort_order, Task.created_at)
    )
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    assigned_filter = _assigned_to_or_open(agent)
    if assigned_filter is not None:
        stmt = stmt.where(assigned_filter)
    result = await session.execute(stmt)
    for task in result.scalars():
        if tags_any and not any(t in task.tags for t in tags_any):
            continue
        if tags_all and not all(t in task.tags for t in tags_all):
            continue
        if exclude_tags and any(t in task.tags for t in exclude_tags):
            continue
        return task
    return None


# ---- Claiming ----
async def claim_task(session: AsyncSession, task_id: int, agent: str) -> ClaimResult:
    # Pre-check the hard-assignment guard so we can return a precise reason
    # ("reserved for X") instead of the generic "not ready" below. The atomic
    # UPDATE additionally enforces it, so there's no TOCTOU window.
    existing = await session.get(Task, task_id)
    if existing is not None and existing.assigned_to and existing.assigned_to != agent:
        return ClaimResult(
            ok=False,
            reason=f"task is reserved for {existing.assigned_to!r}",
            task=None,
        )
    # Atomic conditional update: only flips if status is still READY.
    stmt = (
        update(Task)
        .where(
            Task.id == task_id,
            (Task.status == TaskStatus.READY) | ((Task.status == TaskStatus.IN_PROGRESS) & Task.claimed_by.is_(None)),
            (Task.assigned_to.is_(None)) | (Task.assigned_to == agent),
        )
        .values(
            status=TaskStatus.IN_PROGRESS,
            claimed_by=agent,
            claimed_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        .returning(Task.id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        # Either doesn't exist, no longer READY, or (edge case above) reserved.
        task = await session.get(Task, task_id)
        if task is None:
            return ClaimResult(ok=False, reason="task not found")
        return ClaimResult(
            ok=False,
            reason=f"task is {task.status.value}, not ready",
            task=None,
        )
    await session.commit()
    task = await session.get(Task, task_id)
    assert task is not None
    await session.refresh(task)
    await _publish_task_event("board", "task_claimed", task)
    return ClaimResult(ok=True, task=_to_task_read(task))


# ---- Progress ----
async def post_progress(
    session: AsyncSession, task_id: int, data: ProgressCreate
) -> ProgressEvent:
    task = await locked_task(session, task_id)
    _check_claimer(task, data.agent)
    if task.status not in (TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED):
        raise ValueError("work mutations require an active task")
    payload: dict = {"content": data.content}
    if data.kind.value == "artifact_ref" and data.artifact:
        # Copy so we can mutate; data.artifact is the agent-supplied dict.
        payload["artifact"] = dict(data.artifact)
        # Look up the most recent Artifact row for this task + path so the UI
        # can fetch the file via /api/artifacts/{id}/content. Never raises — a
        # select won't fail; if no row matches, the payload is left as-is and
        # the UI falls back to the file:/// path.
        art_path = data.artifact.get("path")
        if art_path:
            stmt = (
                select(Artifact)
                .where(Artifact.task_id == task_id, Artifact.path == art_path)
                .order_by(Artifact.id.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if row is not None:
                payload["artifact"]["id"] = row.id
    blocked = False
    if data.kind.value == "status_change" and data.status:
        if data.status.get("to") != "blocked":
            raise ValueError("use request_review for lifecycle transitions")
        payload["status"] = data.status
        if data.status.get("to") == "blocked":
            task.status = TaskStatus.BLOCKED
            task.updated_at = datetime.now(UTC).replace(tzinfo=None)
            blocked = True
    ev = ProgressEvent(
        task_id=task_id,
        agent=data.agent,
        kind=data.kind,
        payload=payload,
    )
    session.add(ev)
    await session.commit()
    await session.refresh(ev)
    if blocked:
        # Lifecycle event fans out to the board channel AND task:{id}. Skip the
        # redundant task-channel "progress" publish below so subscribers see a
        # single authoritative "task_blocked" event for this transition.
        await session.refresh(task)
        await _publish_task_event("board", "task_blocked", task)
        return ev
    await event_bus.publish(
        f"task:{task_id}",
        {"type": "progress", "event_id": ev.id, "kind": ev.kind.value},
    )
    await event_bus.publish("board", {"type": "progress", "task_id": task_id})
    return ev


async def complete_task(
    session: AsyncSession, task_id: int, agent: str, summary: Optional[str] = None
) -> Task:
    # Preserve the tool name for existing clients, but never bypass review.
    return await request_review(session, task_id, agent, summary)


async def _maybe_collect_review_diff(
    session: AsyncSession, task: Task, agent: str
) -> None:
    """Best-effort: if the task has repo_path + branch + a resolvable base,
    collect the diff and store it as a progress_event(kind=diff). On git
    failure, store a kind=error event so the user sees what went wrong.
    Never raises — review must succeed regardless of git.
    """
    if not task.repo_path or not task.branch:
        return
    base = await resolve_base_branch(session, task)
    if base is None:
        return
    # Collect the unified diff — failure here means we can't render anything.
    try:
        diff_text = await collect_diff(task.repo_path, base, task.branch)
    except GitError as exc:
        session.add(
            ProgressEvent(
                task_id=task.id,
                agent=agent,
                kind="error",
                payload={"content": f"diff collection failed: {exc}"},
            )
        )
        return
    except Exception as exc:  # defensive: never break review on a git surprise
        session.add(
            ProgressEvent(
                task_id=task.id,
                agent=agent,
                kind="error",
                payload={"content": f"diff collection raised {type(exc).__name__}: {exc}"},
            )
        )
        return

    # Collect per-file stats — failure here degrades to empty stats, not a lost diff.
    try:
        diffstats = await collect_diffstats(task.repo_path, base, task.branch)
    except Exception:
        diffstats = []

    files = [s["path"] for s in diffstats]
    stats = {
        s["path"]: (
            f"+{s['added']} -{s['deleted']}" if s["added"] >= 0 and s["deleted"] >= 0
            else "binary"
        )
        for s in diffstats
    }
    session.add(
        ProgressEvent(
            task_id=task.id,
            agent=agent,
            kind="diff",
            payload={"content": diff_text, "files": files, "stats": stats},
        )
    )


async def request_review(
    session: AsyncSession, task_id: int, agent: str, summary: Optional[str] = None
) -> Task:
    task = await locked_task(session, task_id)
    _check_claimer(task, agent)
    if task.status != TaskStatus.IN_PROGRESS:
        raise ValueError("only in_progress tasks can be submitted for review")
    if not summary or not summary.strip():
        raise ValueError("a work summary is required for review")
    task.work_summary = summary.strip()
    task.review_assigned_to = None
    task.reviewer = None
    record_transition(session, task, agent, TaskStatus.REVIEW, summary)
    # Phase 3: best-effort diff auto-collection.
    await _maybe_collect_review_diff(session, task, agent)
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "task_review_requested", task)
    return task


async def set_task_branch(
    session: AsyncSession, task_id: int, agent: str, branch: str
) -> Task:
    task = await locked_task(session, task_id)
    _check_claimer(task, agent)
    if task.status != TaskStatus.IN_PROGRESS:
        raise ValueError("work mutations require an active task")
    task.branch = branch
    task.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "task_updated", task)
    return task


async def set_task_pr(
    session: AsyncSession,
    task_id: int,
    agent: str,
    pr_url: str,
    pr_status: str,
) -> Task:
    task = await locked_task(session, task_id)
    _check_claimer(task, agent)
    if task.status != TaskStatus.IN_PROGRESS:
        raise ValueError("work mutations require an active task")
    task.pr_url = pr_url
    task.pr_status = pr_status
    task.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "task_updated", task)
    return task


# ---- Comments ----
async def list_comments(
    session: AsyncSession,
    task_id: int,
    since_id: Optional[int],
    mark_seen_by: Optional[str],
) -> list[Comment]:
    stmt = select(Comment).where(Comment.task_id == task_id)
    if since_id is not None:
        stmt = stmt.where(Comment.id > since_id)
    # Unseen first.
    stmt = stmt.order_by(Comment.seen_by_agent.asc(), Comment.id.asc())
    result = await session.execute(stmt)
    comments = list(result.scalars())
    if mark_seen_by is not None:
        # seen_by_agent is a read-receipt for messages TO the agent. The reading
        # agent should not mark its own comments as "seen by itself" — they were
        # authored by it, never "unseen" from its perspective.
        for c in comments:
            if not c.seen_by_agent and c.author != mark_seen_by:
                c.seen_by_agent = True
        await session.commit()
    return comments


async def post_comment(
    session: AsyncSession, task_id: int, author: str, content: str
) -> Comment:
    c = Comment(task_id=task_id, author=author, content=content)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    await event_bus.publish(
        f"task:{task_id}",
        {"type": "comment", "comment_id": c.id, "author": author},
    )
    return c


async def post_comment_with_status(
    session: AsyncSession,
    task_id: int,
    author: str,
    content: str,
    target_status: Optional[TaskStatus],
) -> Comment:
    """Post a normal comment without changing workflow state.

    Keep the legacy signature, but require dedicated review/acceptance decisions
    for status changes. Reject before adding pending ORM objects.
    """
    await locked_task(session, task_id)
    if target_status is not None:
        raise ValueError("use AI review or human acceptance for status changes")
    c = Comment(task_id=task_id, author=author, content=content)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    await event_bus.publish(
        f"task:{task_id}",
        {"type": "comment", "comment_id": c.id, "author": author},
    )
    return c


# ---- Artifacts ----
async def post_artifact(
    session: AsyncSession, task_id: int, data: ArtifactCreate
) -> Artifact:
    task = await locked_task(session, task_id)
    _check_claimer(task, data.agent)
    if task.status not in (TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED):
        raise ValueError("work mutations require an active task")
    allowed_roots = [
        artifact_root(task_id),
        Path.home() / ".agent-kanban" / "artifacts" / str(task_id),
    ]
    if task.repo_path:
        allowed_roots.append(task.repo_path)
    if not _is_path_allowed(data.path, [str(r) for r in allowed_roots]):
        raise ValueError(
            f"artifact path {data.path!r} is not inside an allowed root"
        )
    # NOTE: ArtifactCreate carries `agent` for authorization, but the Artifact
    # table has no agent column — drop it before constructing the ORM object.
    art = Artifact(task_id=task_id, **data.model_dump(exclude={"agent"}))
    session.add(art)
    await session.commit()
    await session.refresh(art)
    return art


async def locked_task(session: AsyncSession, task_id: int) -> Task:
    result = await session.execute(
        select(Task).where(Task.id == task_id).with_for_update().execution_options(populate_existing=True)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise ValueError(f"task {task_id} not found")
    return task


def record_transition(session, task, actor, target, note, decision=None):
    previous = task.status.value
    task.status = target
    task.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(ProgressEvent(task_id=task.id, agent=actor, kind="status_change", payload={
        "content": note, "status": {"from": previous, "to": target.value, "note": note},
        **({"decision": decision} if decision else {}),
    }))


async def claim_review(session: AsyncSession, task_id: int, agent: str) -> ClaimResult:
    result = await session.execute(
        update(Task).where(Task.id == task_id, Task.status == TaskStatus.REVIEW, Task.reviewer.is_(None), or_(Task.review_assigned_to.is_(None), Task.review_assigned_to == agent))
        .values(reviewer=agent, updated_at=datetime.now(UTC).replace(tzinfo=None)).returning(Task.id)
    )
    if result.first() is None:
        return ClaimResult(ok=False, reason="review is unavailable or already claimed")
    await session.commit()
    task = await get_task(session, task_id)
    await session.refresh(task)
    await _publish_task_event("board", "review_claimed", task)
    return ClaimResult(ok=True, task=_to_task_read(task))


async def submit_review(session: AsyncSession, task_id: int, agent: str, decision: str, comment: str) -> Task:
    task = await locked_task(session, task_id)
    if task.status != TaskStatus.REVIEW:
        raise ValueError("task is not in review")
    if task.reviewer != agent:
        raise PermissionError("claim the review before submitting a decision")
    if decision not in ("APPROVE", "REQUEST_CHANGES"):
        raise ValueError("decision must be APPROVE or REQUEST_CHANGES")
    if not comment.strip():
        raise ValueError("review findings are required")
    target = TaskStatus.ACCEPTANCE if decision == "APPROVE" else TaskStatus.IN_PROGRESS
    record_transition(session, task, agent, target, comment, decision)
    session.add(Comment(task_id=task_id, author=agent, content=f"{decision}\n{comment}"))
    if target == TaskStatus.IN_PROGRESS:
        task.claimed_by = None
        task.claimed_at = None
    task.review_assigned_to = None
    task.reviewer = None
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "review_submitted", task)
    return task


async def accept_task(session: AsyncSession, task_id: int, actor: str, approve: bool, comment: str) -> Task:
    task = await locked_task(session, task_id)
    if task.status != TaskStatus.ACCEPTANCE:
        raise ValueError("task must pass AI review before human acceptance")
    if not approve and not comment.strip():
        raise ValueError("a comment is required when returning work")
    target = TaskStatus.DONE if approve else TaskStatus.IN_PROGRESS
    note = comment.strip() or "Работа принята"
    record_transition(session, task, actor, target, note, "ACCEPT" if approve else "RETURN")
    session.add(Comment(task_id=task_id, author=actor, content=note))
    task.review_assigned_to = None
    task.reviewer = None
    if not approve:
        task.claimed_by = None
        task.claimed_at = None
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "human_acceptance", task)
    return task


def artifact_root(task_id: int) -> Path:
    import os
    # Keep local uploads in this workspace; deployment may override the root.
    return Path(os.environ.get("AGENT_KANBAN_ARTIFACT_DIR", ".runtime/artifacts")).resolve() / str(task_id)


async def task_context(session: AsyncSession, task_id: int) -> dict:
    task = await get_task(session, task_id)
    project = await session.get(Project, task.project_id) if task.project_id else None
    data = _to_task_read(task).model_dump(mode="json")
    data["repo_path"] = task.repo_path or (project.repo_path if project else None)
    data["base_branch"] = task.base_branch or (project.default_branch if project else None)
    comments = await list_comments(session, task_id, None, None)
    progress = (await session.execute(select(ProgressEvent).where(ProgressEvent.task_id == task_id).order_by(ProgressEvent.id))).scalars().all()
    artifacts = (await session.execute(select(Artifact).where(Artifact.task_id == task_id).order_by(Artifact.id))).scalars().all()
    data["comments"] = [c.model_dump(mode="json") for c in comments]
    data["progress"] = [e.model_dump(mode="json") for e in progress]
    data["attachments"] = [dict(a.model_dump(mode="json"), content_url=f"/api/artifacts/{a.id}/content") for a in artifacts]
    data["repository_instructions"] = "Work directly in repo_path. Read AGENTS.md and repository skills/instructions before changes. The board never executes Codex."
    data["project_agent_instructions"] = project.agent_instructions if project else ""
    data["effective_agent_instructions"] = "\n\n".join(
        text for text in (data["project_agent_instructions"], task.agent_instructions) if text
    )
    sections = [
        f"Работай в репозитории {data['repo_path'] or '[путь не задан — уточни перед изменениями]'}.\n"
        "Перед началом полностью прочитай корневой AGENTS.md и все вложенные AGENTS.md, относящиеся к изменяемым файлам.\n"
        "Соблюдай ограничения проекта и задачи при выполнении и ревью. Если инструкции конфликтуют или требуют расширения разрешённой области, остановись и уточни у человека.\n"
        "Не делай commit/push без отдельной просьбы.",
        "Ограничения и инструкции проекта:\n" + (data["project_agent_instructions"] or "Не заданы."),
        "Дополнительные ограничения и инструкции задачи:\n" + (task.agent_instructions or "Не заданы."),
        f"Задача #{task.id}: {task.title}\nСтатус: {task.status.value}\n\n{task.description}",
        "Критерии приёмки:\n" + (task.acceptance_criteria or "Не заданы — уточни требуемый результат."),
    ]
    if task.work_summary:
        sections.append("Результат выполнения для ревью:\n" + task.work_summary)
    if comments:
        sections.append("Комментарии:\n" + "\n".join(f"{c.author}: {c.content}" for c in comments))
    if artifacts:
        sections.append("Вложения:\n" + "\n".join(f"{a.path}: /api/artifacts/{a.id}/content" for a in artifacts))
    sections.append("В финале сообщи причину проблемы, изменённые файлы, что исправлено, результаты тестов и сборок, runtime-действия, оставшиеся риски и подтверждение соблюдения разрешённой области изменений.")
    data["agent_prompt"] = "\n\n".join(sections)
    return data


async def human_workflow(session: AsyncSession, task_id: int, actor: str, action: str,
                         comment: str = "", reviewer: Optional[str] = None) -> Task:
    """Explicit human decisions; REST rejects agent principals before entry."""
    task = await locked_task(session, task_id)
    active = {TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.ACCEPTANCE}
    note = comment.strip()
    if action == "ready":
        if task.status == TaskStatus.READY:
            return task
        if task.status not in active | {TaskStatus.TODO, TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.CANCELLED}:
            raise ValueError("Нельзя вернуть эту задачу в Готово")
        target, decision = TaskStatus.READY, "REQUEUE"
        note = note or "Задача возвращена в очередь работы человеком"
    elif action == "start":
        if task.status != TaskStatus.READY:
            raise ValueError("Начать можно только готовую к работе задачу")
        target, decision = TaskStatus.IN_PROGRESS, "START"
        note = note or "Работа начата человеком"
    elif action == "review":
        if task.status not in active:
            raise ValueError("На проверку можно отправить только результат работы")
        note = note or task.work_summary.strip()
        if not note:
            raise ValueError("Опишите результат работы перед отправкой на ревью")
        if reviewer:
            from agent_kanban.models import Token
            if (await session.execute(select(Token.id).where(Token.agent_name == reviewer).limit(1))).first() is None:
                raise ValueError("У выбранного агента нет действующего токена")
        task.work_summary = note
        target, decision = TaskStatus.REVIEW, "SEND_REVIEW"
    elif action == "human_review":
        if task.status not in {TaskStatus.IN_PROGRESS, TaskStatus.REVIEW}:
            raise ValueError("Нет результата для ручной проверки")
        target, decision = TaskStatus.ACCEPTANCE, "SEND_HUMAN_REVIEW"
        note = note or "Результат отправлен на проверку человеку"
    elif action == "accept":
        if task.status not in active:
            raise ValueError("Принять можно только результат работы")
        target, decision = TaskStatus.DONE, "ACCEPT"
        note = note or "Работа проверена и принята человеком"
    elif action == "return":
        if task.status not in {TaskStatus.REVIEW, TaskStatus.ACCEPTANCE} or not note:
            raise ValueError("Для возврата с проверки нужны замечания")
        target, decision = TaskStatus.IN_PROGRESS, "RETURN"
    else:
        raise ValueError("Неизвестное действие")
    task.reviewer = None
    task.review_assigned_to = reviewer if action == "review" else None
    if action in {"ready", "return", "accept"}:
        task.claimed_by = None
        task.claimed_at = None
    record_transition(session, task, actor, target, note, decision)
    session.add(Comment(task_id=task.id, author=actor, content=f"{decision}\n{note}"))
    await session.commit()
    await session.refresh(task)
    await _publish_task_event("board", "human_workflow", task)
    return task
