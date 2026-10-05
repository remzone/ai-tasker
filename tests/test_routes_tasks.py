import pytest


@pytest.mark.asyncio
async def test_create_and_list_tasks(authed_client):
    r = await authed_client.post(
        "/api/tasks",
        json={"title": "do thing", "tags": ["ui"]},
    )
    assert r.status_code == 201
    created = r.json()
    assert created["status"] == "todo"
    assert created["tags"] == ["ui"]

    r = await authed_client.get("/api/tasks")
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == created["id"]


@pytest.mark.asyncio
async def test_update_task_status(authed_client):
    r = await authed_client.post("/api/tasks", json={"title": "t"})
    task_id = r.json()["id"]
    r = await authed_client.patch(f"/api/tasks/{task_id}", json={"status": "ready"})
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_get_task_by_id(authed_client):
    r = await authed_client.post("/api/tasks", json={"title": "t"})
    task_id = r.json()["id"]
    r = await authed_client.get(f"/api/tasks/{task_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "t"


@pytest.mark.asyncio
async def test_get_task_404(authed_client):
    r = await authed_client.get("/api/tasks/9999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks_invalid_status_returns_422(authed_client):
    r = await authed_client.get("/api/tasks?status=bogus")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status(authed_client):
    await authed_client.post("/api/tasks", json={"title": "t1"})
    r = await authed_client.get("/api/tasks?status=ready")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_task_project_context_and_utc_comments(authed_client):
    first = (await authed_client.post("/api/projects", json={"name": "One", "repo_path": "/work/one", "default_branch": "main"})).json()
    second = (await authed_client.post("/api/projects", json={"name": "Two", "repo_path": "/work/two", "default_branch": "develop"})).json()
    for project in (first, second):
        response = await authed_client.post("/api/tasks", json={"title": project["name"], "project_id": project["id"], "status": "ready", "acceptance_criteria": "Verified"})
        assert response.status_code == 201
        assert response.json()["repo_path"] == project["repo_path"]
        assert response.json()["base_branch"] == project["default_branch"]
    from agent_kanban.mcp_server import mcp
    from tests.test_mcp_server import _to_dict
    result = _to_dict(await mcp.call_tool("get_next_task", {"project_id": second["id"]}))
    assert result["project_id"] == second["id"]
    listed = _to_dict(await mcp.call_tool("list_tasks", {"project_id": second["id"]}))
    assert len(listed) == 1 and listed[0]["id"] == result["id"]
    comment = await authed_client.post(f'/api/tasks/{result["id"]}/comments', json={"author": "user", "content": "Feedback"})
    assert comment.json()["created_at"].endswith("Z")
