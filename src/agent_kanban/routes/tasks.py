"""REST routes for tasks (used by the UI)."""
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_kanban.auth import Principal, get_current_principal
from agent_kanban.db import get_session
from agent_kanban.models import TaskStatus
from agent_kanban.schemas import TaskCreate, TaskRead, TaskUpdate, AcceptanceDecision
from agent_kanban.services import create_task, get_task, list_tasks, update_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
async def get_tasks(
    status: Optional[TaskStatus] = None,
    tags_any: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
    project_id: Optional[int] = None,
):
    tags = tags_any.split(",") if tags_any else None
    return await list_tasks(session, status, tags, project_id=project_id)


@router.post("", response_model=TaskRead, status_code=201)
async def post_task(
    data: TaskCreate,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    if principal.is_token:
        raise HTTPException(403, "human session required")
    try:
        return await create_task(session, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/{task_id}", response_model=TaskRead)
async def get_one(
    task_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    try:
        return await get_task(session, task_id)
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 409, str(exc))


@router.patch("/{task_id}", response_model=TaskRead)
async def patch_task(
    task_id: int,
    data: TaskUpdate,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    if principal.is_token:
        raise HTTPException(403, "human session required")
    try:
        return await update_task(session, task_id, data)
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 409, str(exc))


@router.post("/{task_id}/acceptance", response_model=TaskRead)
async def acceptance(task_id: int, data: AcceptanceDecision,
                     session: AsyncSession = Depends(get_session),
                     principal: Principal = Depends(get_current_principal)):
    if principal.is_token:
        raise HTTPException(403, "only a human session may accept work")
    from agent_kanban.services import accept_task
    try:
        return await accept_task(session, task_id, principal.agent_name, data.approve, data.comment)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


class HumanWorkflowDecision(BaseModel):
    action: Literal["ready", "start", "review", "human_review", "accept", "return"]
    comment: str = ""
    reviewer: Optional[str] = None


@router.post("/{task_id}/workflow", response_model=TaskRead)
async def workflow(task_id: int, data: HumanWorkflowDecision,
                   session: AsyncSession = Depends(get_session),
                   principal: Principal = Depends(get_current_principal)):
    if not principal.is_user:
        raise HTTPException(403, "human session required")
    from agent_kanban.services import human_workflow
    try:
        return await human_workflow(session, task_id, f"user:{principal.user_id}", data.action,
                                    data.comment, data.reviewer)
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 409, str(exc))


@router.get("/{task_id}/context")
async def get_context(
    task_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    from agent_kanban.services import task_context
    try:
        return await task_context(session, task_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
