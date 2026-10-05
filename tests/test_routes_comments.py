import pytest


@pytest.mark.asyncio
async def test_post_and_list_comments(authed_client):
    r = await authed_client.post("/api/tasks", json={"title": "t"})
    task_id = r.json()["id"]

    r = await authed_client.post(
        f"/api/tasks/{task_id}/comments",
        json={"author": "user", "content": "hello"},
    )
    assert r.status_code == 201
    assert r.json()["author"] == "user"

    r = await authed_client.get(f"/api/tasks/{task_id}/comments")
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_comment_on_review_does_not_decide_review(authed_client):
    r = await authed_client.post("/api/tasks", json={"title": "t", "status": "ready"})
    task_id = r.json()["id"]
    from agent_kanban.mcp_server import mcp
    await mcp.call_tool("claim_task", {"task_id": task_id, "agent": "codex"})
    await mcp.call_tool("request_review", {"task_id": task_id, "agent": "codex", "summary": "Done"})
    r = await authed_client.post(f"/api/tasks/{task_id}/comments", json={"author": "user", "content": "Question about this work"})
    assert r.status_code == 201
    assert (await authed_client.get(f"/api/tasks/{task_id}")).json()["status"] == "review"


@pytest.mark.asyncio
async def test_comment_cannot_bypass_review(authed_client):
    r = await authed_client.post("/api/tasks", json={"title": "t"})
    task_id = r.json()["id"]
    r = await authed_client.post(f"/api/tasks/{task_id}/comments?status=done", json={"author": "user", "content": "bypass"})
    assert r.status_code == 409
    assert (await authed_client.get(f"/api/tasks/{task_id}")).json()["status"] == "todo"


@pytest.mark.asyncio
async def test_comment_on_non_review_task_does_not_change_status(authed_client):
    r = await authed_client.post("/api/tasks", json={"title": "t"})
    task_id = r.json()["id"]
    # Task is in 'todo'.
    r = await authed_client.post(
        f"/api/tasks/{task_id}/comments",
        json={"author": "user", "content": "hi"},
    )
    assert r.status_code == 201
    r = await authed_client.get(f"/api/tasks/{task_id}")
    assert r.json()["status"] == "todo"


@pytest.mark.asyncio
async def test_comment_with_invalid_status_returns_422(authed_client):
    r = await authed_client.post("/api/tasks", json={"title": "t"})
    task_id = r.json()["id"]
    r = await authed_client.post(
        f"/api/tasks/{task_id}/comments?status=bogus",
        json={"author": "user", "content": "x"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_comment_with_status_is_atomic(session):
    """If the status update would fail, the comment must not be persisted either."""
    from agent_kanban.services import post_comment_with_status
    from agent_kanban.models import TaskStatus
    # Use a non-existent task_id to trigger a ValueError inside the service
    # (get_task raises). The comment must NOT be persisted.
    from sqlmodel import select
    from agent_kanban.models import Comment
    with pytest.raises(ValueError):
        await post_comment_with_status(
            session, 999999, "user", "should not persist", TaskStatus.IN_PROGRESS
        )
    # Verify no comment was committed for the ghost task.
    stmt = select(Comment).where(Comment.task_id == 999999)
    result = await session.execute(stmt)
    assert result.scalars().all() == []
