"""REST route for serving artifact file contents (Phase polish).

Replaces the file:/// placeholder in the UI. The path stored on the
Artifact row must be inside an allow-listed root (the task's repo_path or
the per-task artifacts directory), the same sandbox rule that post_artifact
enforces at registration time. We re-check at serve time too in case rows
were inserted via raw SQL or config drifted.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from agent_kanban.services import artifact_root
from agent_kanban.events import event_bus

from agent_kanban.auth import Principal, get_current_principal
from agent_kanban.db import get_session
from agent_kanban.models import Artifact, Task

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


def _is_path_allowed(path: str, allowed_roots: list[str]) -> bool:
    p = Path(path).expanduser().resolve()
    for root in allowed_roots:
        try:
            p.relative_to(Path(root).expanduser().resolve())
            return True
        except ValueError:
            continue
    return False


@router.api_route("/{artifact_id}/content", methods=["GET", "HEAD"])
async def get_artifact_content(
    artifact_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_principal),
):
    art = await session.get(Artifact, artifact_id)
    if art is None:
        raise HTTPException(404, "artifact not found")

    # Resolve the task to compute allowed roots.
    task = await session.get(Task, art.task_id)
    if task is None:
        raise HTTPException(404, "task not found")

    allowed_roots = [
        str(Path.home() / ".agent-kanban" / "artifacts" / str(task.id)),
        str(artifact_root(task.id)),
    ]
    if task.repo_path:
        allowed_roots.append(task.repo_path)

    if not _is_path_allowed(art.path, allowed_roots):
        raise HTTPException(403, "artifact path is outside the allowed roots")

    p = Path(art.path)
    if not p.is_file():
        raise HTTPException(404, "artifact file not found on disk")

    return FileResponse(str(p), filename=p.name, headers={"X-Content-Type-Options": "nosniff"})


@router.get("/task/{task_id}")
async def list_attachments(task_id: int, session: AsyncSession = Depends(get_session),
                           principal: Principal = Depends(get_current_principal)):
    return list((await session.execute(select(Artifact).where(Artifact.task_id == task_id).order_by(Artifact.id))).scalars())


@router.post("/task/{task_id}/upload", status_code=201)
async def upload_attachment(task_id: int, file: UploadFile = File(...),
                            session: AsyncSession = Depends(get_session),
                            principal: Principal = Depends(get_current_principal)):
    if principal.is_token:
        raise HTTPException(403, "human session required")
    if await session.get(Task, task_id) is None:
        raise HTTPException(404, "task not found")
    import uuid
    root = artifact_root(task_id)
    root.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "attachment").name
    path = root / f"{uuid.uuid4().hex}-{name}"
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise HTTPException(413, "attachment exceeds 20 MB")
                out.write(chunk)
        art = Artifact(task_id=task_id, path=str(path), kind="screenshot" if (file.content_type or "").startswith("image/") else "file", description=name)
        session.add(art)
        await session.commit()
        await session.refresh(art)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    await event_bus.publish(f"task:{task_id}", {"type": "attachment", "artifact_id": art.id})
    return art
