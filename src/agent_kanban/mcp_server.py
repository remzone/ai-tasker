"""MCP server exposing the core tools for agents.

Uses FastMCP (bundled in the official `mcp` SDK since v1.2). The HTTP app
returned by `mcp.streamable_http_app()` is mounted in server.py at /mcp.

Two ways to obtain an instance:
  - `create_mcp()` factory: builds a fresh FastMCP with all core tools
    registered. Used by `server.create_app()` so each app gets its own session
    manager (StreamableHTTPSessionManager is single-use per instance; reusing
    one across multiple app lifespans raises RuntimeError).
  - `mcp` module-level singleton: a convenience instance for in-process tool
    invocation (e.g. `mcp.call_tool(name, args)`, used by tests). It does not
    serve HTTP and never has its session manager started.

Session resolution: each tool resolves the engine from current settings on
every call via `agent_kanban.db._engine_for(get_settings().database_url)` —
the same dynamic pattern the REST routes use (see `db.get_session`). A test
that overrides DATABASE_URL (and clears the settings cache) transparently
routes MCP tool calls to the throwaway DB.
"""
import contextvars
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel.server import request_ctx
from mcp.server.transport_security import TransportSecuritySettings

from agent_kanban.auth import Principal, _resolve_bearer
from agent_kanban.config import get_settings
from agent_kanban.db import _engine_for
from agent_kanban.models import ProgressKind, TaskStatus  # noqa: F401
from agent_kanban.schemas import ArtifactCreate, ProgressCreate
from agent_kanban.services import (
    claim_task as svc_claim_task,
    complete_task as svc_complete_task,
    get_next_task as svc_get_next_task,
    list_comments as svc_list_comments,
    list_tasks as svc_list_tasks,
    post_artifact as svc_post_artifact,
    post_comment as svc_post_comment,
    post_progress as svc_post_progress,
    request_review as svc_request_review,
    set_task_branch as svc_set_task_branch,
    set_task_pr as svc_set_task_pr,
)

# --- MCP principal resolution -------------------------------------------------
# Streamable HTTP sessions run tools in a background task whose ContextVars
# originate at initialize. Resolve each message's identity from the HTTP Request
# carried by the SDK request context, never from that session task's context.
# The ContextVar remains available only for direct, in-process invocation.
_PRINCIPAL_SCOPE_KEY = "agent_kanban.mcp_principal"
_mcp_principal: contextvars.ContextVar[Optional[Principal]] = contextvars.ContextVar(
    "_mcp_principal", default=None
)


class MCPAuthMiddleware:
    """ASGI middleware that resolves a Principal from the Authorization header.

    Mounted around the FastMCP streamable-HTTP app in server.create_app(). It
    reads ``Authorization: Bearer <token>`` on every /mcp request, resolves it
    to a Principal via the shared token lookup, and stores the result (None if
    absent/invalid) in the HTTP scope for the tool functions to read. It
    never blocks — enforcement is the verifiers' job so the failure surfaces as
    a tool result, not an HTTP error, which is the intended agent UX.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        principal: Optional[Principal] = None
        if scope["type"] == "http":
            # Pull the Authorization header out of the raw ASGI scope without
            # constructing a full Starlette Request (cheaper, and avoids
            # consuming the receive channel).
            for hdr_name, hdr_value in scope.get("headers", []):
                if hdr_name.lower() == b"authorization":
                    authz = hdr_value.decode("latin-1")
                    if authz.lower().startswith("bearer "):
                        token_value = authz[7:].strip()
                        from agent_kanban.db import AsyncSessionLocal

                        async with AsyncSessionLocal() as s:
                            principal = await _resolve_bearer(s, token_value)
                    break
        scope[_PRINCIPAL_SCOPE_KEY] = principal
        await self.app(scope, receive, send)


def _current_principal() -> Optional[Principal]:
    context = request_ctx.get(None)
    request = context.request if context is not None else None
    if request is not None:
        # Missing/invalid auth must remain None; do not fall back to an identity
        # inherited by the long-lived MCP session task.
        return request.scope.get(_PRINCIPAL_SCOPE_KEY)
    return _mcp_principal.get()


def _authentication_error() -> PermissionError:
    context = request_ctx.get(None)
    request = context.request if context is not None else None
    reason = "no authenticated request context"
    if request is not None:
        authz = request.headers.get("authorization")
        if authz is None:
            reason = "Authorization header is missing"
        elif not authz.lower().startswith("bearer ") or not authz[7:].strip():
            reason = "Authorization must contain Bearer followed by the agent token"
        else:
            reason = "Bearer token is invalid or revoked"
    # Report the failure category only; never include a token or header value.
    return PermissionError(f"authentication required (Bearer token): {reason}")


async def _require_matching_agent(agent: str) -> Principal:
    """Resolve the MCP principal and verify the ``agent`` arg matches it.

    Used by all mutation tools (claim_task, post_progress, ...). Raises
    PermissionError if no token authenticated the request, or if the supplied
    ``agent`` differs from the token's bound ``agent_name``. The error surfaces
    to the agent as a tool result (the SDK converts raised exceptions).
    """
    principal = _current_principal()
    if principal is None:
        raise _authentication_error()
    if agent != principal.agent_name:
        raise PermissionError(
            f"agent {agent!r} does not match the authenticated token's "
            f"agent_name {principal.agent_name!r}"
        )
    return principal


async def _require_any_principal() -> Principal:
    """Resolve the MCP principal, requiring only that one exists.

    Used by read tools (get_next_task, list_tasks, get_comments): any
    authenticated principal may read; the agent arg is not bound.
    """
    principal = _current_principal()
    if principal is None:
        raise _authentication_error()
    return principal


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession bound to the currently-configured DATABASE_URL.

    Mirrors `db.get_session` (used by the REST dependency) so MCP tools and
    HTTP routes share the same engine-resolution semantics and test isolation.
    """
    factory = async_sessionmaker(
        _engine_for(get_settings().database_url),
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as s:
        yield s


async def _task_to_dict(task, s: AsyncSession, agent_name: str) -> dict:
    from agent_kanban.models import Project
    from agent_kanban.repo_paths import repository_paths

    project = await s.get(Project, task.project_id) if task.project_id else None
    paths = await repository_paths(
        s, project, task.repo_path or (project.repo_path if project else None), agent_name
    )
    return {
        **paths,
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "agent_instructions": task.agent_instructions,
        "acceptance_criteria": task.acceptance_criteria,
        "work_summary": task.work_summary,
        "reviewer": task.reviewer,
        "review_assigned_to": task.review_assigned_to,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "tags": task.tags,
        "claimed_by": task.claimed_by,
        "claimed_at": task.claimed_at.isoformat() + "Z" if task.claimed_at else None,
        "assigned_to": task.assigned_to,
        "project_id": task.project_id,
        "sort_order": task.sort_order,
        "base_branch": task.base_branch,
        "branch": task.branch,
        "pr_url": task.pr_url,
        "pr_status": task.pr_status,
        "created_at": task.created_at.isoformat() + "Z",
        "updated_at": task.updated_at.isoformat() + "Z",
    }


def create_mcp() -> FastMCP:
    """Build a FastMCP instance with all core tools registered.

    Each call returns an independent instance with its own tool registry and
    (lazily-created, single-use) session manager. Callers that serve HTTP
    should create one instance per app so the session manager lifecycle is not
    shared across multiple app lifespans.

    The MCP streamable-HTTP transport enables DNS-rebinding protection by
    default (localhost only). We override the allow-lists with the configured
    MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS plus the PUBLIC_URL hostname so a
    public deployment (e.g. kanban.example.com) is reachable by agents without
    hitting "Invalid Host header".
    """
    # `streamable_http_path="/"` makes the inner Starlette route resolve at "/"
    # so that mounting the app under "/mcp" in server.py yields a canonical
    # endpoint of "/mcp/" (with "/mcp" 307-redirecting to it). Without this the
    # inner default route "/mcp" would combine with the "/mcp" mount prefix to
    # produce a doubled "/mcp/mcp" path.
    s = get_settings()
    security = TransportSecuritySettings(
        allowed_hosts=s.effective_mcp_allowed_hosts(),
        allowed_origins=s.effective_mcp_allowed_origins(),
    )
    mcp = FastMCP(
        "agent-kanban",
        instructions="Before performing work or review, call get_task_context. Read and obey project_agent_instructions and agent_instructions, acceptance criteria and local AGENTS.md. Never expand the permitted file scope silently; ask the human if instructions conflict. Use set_project_path to register your local checkout before work when shared paths differ. Claim the task or review through MCP before working; repository instructions remain mandatory.",
        streamable_http_path="/",
        transport_security=security,
    )

    @mcp.tool()
    async def get_next_task(
        tags_any: Optional[list[str]] = None,
        tags_all: Optional[list[str]] = None,
        exclude_tags: Optional[list[str]] = None,
        project_id: Optional[int] = None,
    ) -> Optional[dict]:
        """Return the next ready or returned-unclaimed in_progress task (oldest first). Returns null if none.

        Filters:
          tags_any: task must have at least one of these tags
          tags_all: task must have all of these tags
          exclude_tags: task must have none of these tags

        Only tasks that are unassigned OR assigned to the calling agent are
        returned — tasks reserved for other agents are invisible here.

        Does NOT claim the task. Call claim_task to take it.
        """
        principal = await _require_any_principal()
        async with session() as s:
            task = await svc_get_next_task(
                s, tags_any, tags_all, exclude_tags, agent=principal.agent_name, project_id=project_id
            )
            if task is None:
                return None
            return await _task_to_dict(task, s, principal.agent_name)

    @mcp.tool()
    async def claim_task(task_id: int, agent: str) -> dict:
        """Atomically claim a ready task. Sets status to in_progress.

        Returns {ok: bool, reason: str?, task: Task?}.
        """
        principal = await _require_matching_agent(agent)
        async with session() as s:
            result = await svc_claim_task(s, task_id, agent)
            return {
                "ok": result.ok,
                "reason": result.reason,
                "task": await _task_to_dict(result.task, s, principal.agent_name) if result.task else None,
            }

    @mcp.tool()
    async def list_tasks(
        status: Optional[str] = None, tags_any: Optional[list[str]] = None, project_id: Optional[int] = None
    ) -> list[dict]:
        """List tasks, optionally filtered by status and/or tags. Does not claim.

        Only tasks that are unassigned OR assigned to the calling agent are
        returned — tasks reserved for other agents are hidden.
        """
        principal = await _require_any_principal()
        status_enum = TaskStatus(status) if status else None
        async with session() as s:
            tasks = await svc_list_tasks(s, status_enum, tags_any, agent=principal.agent_name, project_id=project_id)
            return [await _task_to_dict(t, s, principal.agent_name) for t in tasks]

    @mcp.tool()
    async def post_progress(
        task_id: int,
        agent: str,
        kind: str,
        content: str,
        artifact: Optional[dict] = None,
        status: Optional[dict] = None,
    ) -> dict:
        """Append a progress event to the task's feed.

        kind: text | diff | artifact_ref | error | status_change
        content: text / raw diff / error message / status note
        artifact: {path, kind} required when kind == artifact_ref
        status: {from, to, note} required when kind == status_change

        Report blockers with kind="status_change", status={"to": "blocked"}
        and a description in content. Only a human can resolve the blocker.
        Requires task.claimed_by == agent.
        """
        await _require_matching_agent(agent)
        async with session() as s:
            ev = await svc_post_progress(
                s,
                task_id,
                ProgressCreate(
                    agent=agent,
                    kind=ProgressKind(kind),
                    content=content,
                    artifact=artifact,
                    status=status,
                ),
            )
            return {
                "id": ev.id,
                "kind": ev.kind.value if hasattr(ev.kind, "value") else ev.kind,
                "created_at": ev.created_at.isoformat(),
            }

    @mcp.tool()
    async def complete_task(
        task_id: int, agent: str, summary: Optional[str] = None
    ) -> dict:
        """Submit completed work for AI review (compatibility alias of request_review). Never marks Done; human acceptance is required."""
        principal = await _require_matching_agent(agent)
        async with session() as s:
            task = await svc_complete_task(s, task_id, agent, summary)
            return await _task_to_dict(task, s, principal.agent_name)

    @mcp.tool()
    async def request_review(
        task_id: int, agent: str, summary: Optional[str] = None
    ) -> dict:
        """Submit an active task for AI review. A nonempty summary describing files/commits/tests is required. Requires task.claimed_by == agent; cannot bypass human acceptance."""
        principal = await _require_matching_agent(agent)
        async with session() as s:
            task = await svc_request_review(s, task_id, agent, summary)
            return await _task_to_dict(task, s, principal.agent_name)

    @mcp.tool()
    async def get_comments(
        task_id: int, since_id: Optional[int] = None, agent: Optional[str] = None
    ) -> list[dict]:
        """List comments for a task since a given comment id.

        If agent is provided, marks the returned comments as seen by that agent
        (read receipt). The agent must match the calling token's agent_name.
        Unseen comments are returned first.
        """
        principal = await _require_any_principal()
        # Bind mark_seen_by to the authenticated principal, ignoring the
        # caller-supplied agent for read-receipts, so a codex token can't mark
        # comments seen-by-hermes. For token principals, principal.agent_name is
        # used regardless of what the caller passed; for human-session principals
        # (which never actually call this tool), the original agent arg applies.
        mark_seen_by = principal.agent_name if principal.is_token else agent
        async with session() as s:
            comments = await svc_list_comments(s, task_id, since_id, mark_seen_by)
            return [
                {
                    "id": c.id,
                    "author": c.author,
                    "content": c.content,
                    "seen_by_agent": c.seen_by_agent,
                    "created_at": c.created_at.isoformat(),
                }
                for c in comments
            ]

    @mcp.tool()
    async def post_comment(task_id: int, agent: str, content: str) -> dict:
        """Post a comment authored by the calling agent."""
        await _require_matching_agent(agent)
        async with session() as s:
            c = await svc_post_comment(s, task_id, agent, content)
            return {"id": c.id, "created_at": c.created_at.isoformat()}

    @mcp.tool()
    async def post_artifact(
        task_id: int,
        agent: str,
        kind: str,
        path: str,
        description: Optional[str] = None,
    ) -> dict:
        """Register an artifact file. Path must be inside an allow-listed root.

        Report blockers with kind="status_change", status={"to": "blocked"}
        and a description in content. Only a human can resolve the blocker.
        Requires task.claimed_by == agent.
        """
        await _require_matching_agent(agent)
        async with session() as s:
            art = await svc_post_artifact(
                s,
                task_id,
                ArtifactCreate(
                    agent=agent, kind=kind, path=path, description=description
                ),
            )
            return {"id": art.id, "path": art.path, "kind": art.kind}

    @mcp.tool()
    async def set_task_branch(task_id: int, agent: str, branch: str) -> dict:
        """Report the working branch the agent created for this task.

        Stores branch on the task so the UI can show it and request_review can
        collect a diff against the base branch. Requires task.claimed_by == agent.
        """
        principal = await _require_matching_agent(agent)
        async with session() as s:
            task = await svc_set_task_branch(s, task_id, agent, branch)
            return await _task_to_dict(task, s, principal.agent_name)

    @mcp.tool()
    async def set_task_pr(
        task_id: int, agent: str, pr_url: str, status: str
    ) -> dict:
        """Report a pull request URL and its status for this task.

        status: "open" | "merged" | "closed". Requires task.claimed_by == agent.
        """
        principal = await _require_matching_agent(agent)
        async with session() as s:
            task = await svc_set_task_pr(s, task_id, agent, pr_url, status)
            return await _task_to_dict(task, s, principal.agent_name)

    @mcp.tool()
    async def list_projects() -> list[dict]:
        """Discover projects with your personal paths (server_repo_path is shared)."""
        principal = await _require_any_principal()
        from agent_kanban.models import Project
        from sqlmodel import select
        async with session() as s:
            rows = (await s.execute(select(Project).order_by(Project.id))).scalars()
            from agent_kanban.repo_paths import repository_paths
            return [
                dict(p.model_dump(mode="json"), **await repository_paths(
                    s, p, p.repo_path, principal.agent_name
                ))
                for p in rows
            ]

    @mcp.tool()
    async def set_project_path(project_id: int, local_repo_path: Optional[str] = None) -> dict:
        """Set your persistent local checkout path for a shared project (WSL/Ubuntu absolute Linux path).

        Identity comes from your Bearer token; other agents and shared paths are unchanged.
        Omit local_repo_path or pass null to remove your override. The server does not access
        this client path. Call get_task_context again after changing it. Task subdirectories
        are mapped relative to the shared project root; unrelated repositories are unresolved.
        """
        principal = await _require_any_principal()
        from agent_kanban.repo_paths import set_project_path as save_path
        async with session() as s:
            return await save_path(s, project_id, principal.agent_name, local_repo_path)

    @mcp.tool()
    async def get_task_context(task_id: int) -> dict:
        """Required before execution or review: read project/task restrictions, full agent_prompt, task, criteria, repository, comments, attachments, results and history. Read repository AGENTS.md/skills locally before working."""
        principal = await _require_any_principal()
        from agent_kanban.services import task_context
        async with session() as s:
            return await task_context(s, task_id, agent_name=principal.agent_name)

    @mcp.tool()
    async def get_next_review() -> Optional[dict]:
        """Discover the oldest unclaimed review. Call claim_review, then get_task_context."""
        principal = await _require_any_principal()
        from agent_kanban.models import Task
        from sqlalchemy import or_
        from sqlmodel import select
        async with session() as s:
            task = (await s.execute(select(Task).where(Task.status == TaskStatus.REVIEW, Task.reviewer.is_(None), or_(Task.review_assigned_to.is_(None), Task.review_assigned_to == principal.agent_name)).order_by(Task.updated_at, Task.id).limit(1))).scalars().first()
            return await _task_to_dict(task, s, principal.agent_name) if task else None

    @mcp.tool()
    async def claim_review(task_id: int, agent: str) -> dict:
        """Atomically reserve an AI review for the authenticated reviewer. Preserves the implementation author."""
        principal = await _require_matching_agent(agent)
        from agent_kanban.services import claim_review as claim
        async with session() as s:
            result = await claim(s, task_id, agent)
            return {"ok": result.ok, "reason": result.reason, "task": await _task_to_dict(result.task, s, principal.agent_name) if result.task else None}

    @mcp.tool()
    async def submit_review(task_id: int, agent: str, decision: str, comment: str) -> dict:
        """After claim_review: APPROVE → acceptance; REQUEST_CHANGES → in_progress (available for claim_task). Findings are mandatory and preserved. Never closes the task."""
        principal = await _require_matching_agent(agent)
        from agent_kanban.services import submit_review as submit
        async with session() as s:
            return await _task_to_dict(await submit(s, task_id, agent, decision, comment), s, principal.agent_name)

    return mcp


# Module-level singleton for in-process tool invocation (tests, programmatic
# use). Not used for HTTP serving — server.create_app() builds its own instance
# via create_mcp() so the session manager lifecycle is not shared.
mcp = create_mcp()
