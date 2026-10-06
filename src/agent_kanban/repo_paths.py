"""Resolve client paths lexically, without touching the server filesystem."""

from pathlib import PurePosixPath
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agent_kanban.models import AgentProjectPath, Project


def validate_local_repo_path(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("local_repo_path cannot contain control characters")
    value = value.strip()
    path = PurePosixPath(value)
    if (
        not value
        or len(value) > 4096
        or not path.is_absolute()
        or value.startswith("//")
        or "\\" in value
        or ".." in path.parts
    ):
        raise ValueError(
            "local_repo_path must be an absolute Linux path without '..' or control characters"
        )
    return str(path)


async def set_project_path(
    session: AsyncSession, project_id: int, agent_name: str, local_repo_path: Optional[str]
) -> dict:
    project = await session.get(Project, project_id)
    if project is None:
        raise ValueError("project not found")
    normalized = validate_local_repo_path(local_repo_path) if local_repo_path is not None else None
    if normalized is None:
        await session.execute(
            delete(AgentProjectPath).where(
                AgentProjectPath.project_id == project_id, AgentProjectPath.agent_name == agent_name
            )
        )
    else:
        statement = insert(AgentProjectPath).values(
            project_id=project_id, agent_name=agent_name, local_repo_path=normalized
        )
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=["project_id", "agent_name"],
                set_={"local_repo_path": normalized},
            )
        )
    await session.commit()
    return {"project_id": project_id, "agent_name": agent_name, "local_repo_path": normalized}


async def repository_paths(
    session: AsyncSession,
    project: Optional[Project],
    server_repo_path: Optional[str],
    agent_name: str,
) -> dict:
    binding = await session.get(AgentProjectPath, (project.id, agent_name)) if project else None
    data = {
        "repo_path": server_repo_path,
        "server_repo_path": server_repo_path,
        "local_project_repo_path": binding.local_repo_path if binding else None,
        "repo_path_source": "shared",
    }
    if binding is None:
        return data
    if not server_repo_path or server_repo_path == project.repo_path:
        data.update(repo_path=binding.local_repo_path, repo_path_source="personal")
        return data
    # A task may target a subdirectory, but another repository cannot silently
    # be replaced with the project's checkout. Do not resolve symlinks remotely.
    try:
        root = PurePosixPath(project.repo_path or "")
        target = PurePosixPath(server_repo_path)
        if (
            not root.is_absolute()
            or not target.is_absolute()
            or ".." in target.parts
            or ".." in root.parts
        ):
            raise ValueError("invalid shared path")
        relative = target.relative_to(root)
    except ValueError:
        data.update(
            repo_path=None,
            repo_path_source="unresolved",
            repo_path_error="Task repository is outside the project path; ask the human for its local checkout before working.",
        )
        return data
    data.update(
        repo_path=str(PurePosixPath(binding.local_repo_path) / relative),
        repo_path_source="personal",
    )
    return data
