import pytest

from agent_kanban.models import Artifact, Task, TaskStatus


@pytest.mark.asyncio
async def test_artifact_content_404_for_unknown_id(authed_client):
    r = await authed_client.get("/api/artifacts/999999/content")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_artifact_content_streams_file(authed_client, session, tmp_path):
    # Create a task with a repo_path that covers the sandbox dir, plus an
    # artifact row pointing at a real file inside it.
    sandbox_root = tmp_path / "arts"
    sandbox_root.mkdir()
    task_dir = sandbox_root / "1"
    task_dir.mkdir()
    f = task_dir / "log.txt"
    f.write_text("hello world")

    t = Task(title="t", status=TaskStatus.TODO, repo_path=str(sandbox_root))
    session.add(t)
    await session.commit()
    await session.refresh(t)
    art = Artifact(
        task_id=t.id,
        path=str(f),
        kind="log",
        description="a log",
    )
    session.add(art)
    await session.commit()
    await session.refresh(art)
    art_id = art.id

    r = await authed_client.get(f"/api/artifacts/{art_id}/content")
    assert r.status_code == 200
    assert r.text == "hello world"
    assert "text/plain" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_artifact_content_403_for_path_outside_sandbox(authed_client, session, tmp_path):
    # A file outside both repo_path and the artifacts dir.
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("ssh key")

    t = Task(title="t", status=TaskStatus.TODO)
    session.add(t)
    await session.commit()
    await session.refresh(t)
    art = Artifact(task_id=t.id, path=str(outside), kind="file")
    session.add(art)
    await session.commit()
    await session.refresh(art)
    art_id = art.id

    r = await authed_client.get(f"/api/artifacts/{art_id}/content")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_upload_size_limit_and_cleanup(authed_client, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_KANBAN_ARTIFACT_DIR", str(tmp_path))
    task = (await authed_client.post("/api/tasks", json={"title": "Upload limit"})).json()
    response = await authed_client.post(
        f'/api/artifacts/task/{task["id"]}/upload',
        files={"file": ("large.txt", b"x" * (20 * 1024 * 1024 + 1), "text/plain")},
    )
    assert response.status_code == 413
    assert list((tmp_path / str(task["id"])).iterdir()) == []
    assert (await authed_client.get(f'/api/artifacts/task/{task["id"]}')).json() == []


@pytest.mark.asyncio
async def test_uploaded_screenshot_and_head(authed_client, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_KANBAN_ARTIFACT_DIR", str(tmp_path))
    task = (await authed_client.post("/api/tasks", json={"title": "Screenshot"})).json()
    response = await authed_client.post(
        f'/api/artifacts/task/{task["id"]}/upload',
        files={"file": ("../../screenshot.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert response.status_code == 201
    artifact = response.json()
    assert artifact["description"] == "screenshot.png" and artifact["kind"] == "screenshot"
    assert (tmp_path / str(task["id"])) in __import__("pathlib").Path(artifact["path"]).parents
    head = await authed_client.head(f'/api/artifacts/{artifact["id"]}/content')
    assert head.status_code == 200 and head.headers["content-length"] == "8"
    assert head.headers["x-content-type-options"] == "nosniff"
