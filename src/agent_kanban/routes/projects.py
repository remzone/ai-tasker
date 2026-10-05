"""REST routes for projects."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from agent_kanban.auth import Principal, get_current_principal
from agent_kanban.db import get_session
from agent_kanban.models import Project
from agent_kanban.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    result = await session.execute(select(Project).order_by(Project.created_at))
    return list(result.scalars())


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    data: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    project = Project(**data.model_dump())
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    if not principal.is_user:
        raise HTTPException(403, "human session required")
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    values = data.model_dump(exclude_unset=True)
    if any(values.get(key) is None for key in ("name", "agent_instructions") if key in values):
        raise HTTPException(422, "name and agent_instructions cannot be null")
    if "name" in values and not values["name"].strip():
        raise HTTPException(422, "name cannot be empty")
    for key, value in values.items():
        setattr(project, key, value)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project
