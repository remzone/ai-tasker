"""REST routes for comments."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agent_kanban.auth import Principal, get_current_principal
from agent_kanban.db import get_session
from agent_kanban.models import TaskStatus
from agent_kanban.schemas import CommentCreate, CommentRead
from agent_kanban.services import list_comments, post_comment_with_status

router = APIRouter(prefix="/api/tasks/{task_id}/comments", tags=["comments"])


@router.get("", response_model=list[CommentRead])
async def get_comments(
    task_id: int,
    since_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    # UI doesn't mark comments seen (only agents do via MCP).
    return await list_comments(session, task_id, since_id, mark_seen_by=None)


@router.post("", response_model=CommentRead, status_code=201)
async def add_comment(
    task_id: int,
    data: CommentCreate,
    status: Optional[TaskStatus] = Query(
        None, description="Override task status after comment. If omitted, review→in_progress."
    ),
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    from fastapi import HTTPException
    if status is not None:
        raise HTTPException(409, "use the dedicated review/acceptance operation")
    try:
        return await post_comment_with_status(session, task_id, principal.agent_name, data.content, None)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
