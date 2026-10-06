"""Personal paths change MCP responses, never shared data or server file access."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from agent_kanban.config import get_settings
from agent_kanban.mcp_server import mcp
from agent_kanban.models import AgentProjectPath, Project, Task, TaskStatus
from agent_kanban.services import task_context
from tests.test_mcp_server import _to_dict


@pytest.fixture(autouse=True)
def bind_database(db_url):
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def call(name, **arguments):
    return _to_dict(await mcp.call_tool(name, arguments))


async def make_project(session, repo_path="/srv/app"):
    project = Project(name="Shared", repo_path=repo_path, agent_instructions="Only src/")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def make_task(session, project, repo_path=None, status=TaskStatus.READY):
    task = Task(title="Work", project_id=project.id, repo_path=repo_path, status=status)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def test_personal_path_used_for_discovery_claim_context_and_review(session):
    project = await make_project(session)
    task = await make_task(session, project, "/srv/app")
    review = await make_task(session, project, "/srv/app", TaskStatus.REVIEW)
    result = await call(
        "set_project_path", project_id=project.id, local_repo_path="/home/codex/my checkout/"
    )
    assert result["agent_name"] == "codex"
    assert result["local_repo_path"] == "/home/codex/my checkout"
    projects = await call("list_projects")
    tasks = await call("list_tasks", project_id=project.id)
    next_task = await call("get_next_task", project_id=project.id)
    claimed = await call("claim_task", task_id=task.id, agent="codex")
    next_review = await call("get_next_review")
    claimed_review = await call("claim_review", task_id=review.id, agent="codex")
    for response in (
        projects[0],
        tasks[0],
        next_task,
        claimed["task"],
        next_review,
        claimed_review["task"],
    ):
        assert response["repo_path"] == "/home/codex/my checkout"
        assert response["server_repo_path"] == "/srv/app"
        assert response["repo_path_source"] == "personal"
    for item in (task, review):
        context = await call("get_task_context", task_id=item.id)
        assert context["agent_prompt"].startswith("Работай в репозитории /home/codex/my checkout.")
        assert context["project_agent_instructions"] == "Only src/"
    await session.refresh(project)
    await session.refresh(task)
    assert project.repo_path == task.repo_path == "/srv/app"
    shared = await task_context(session, task.id)
    assert shared["repo_path"] == "/srv/app"
    assert shared["agent_prompt"].startswith("Работай в репозитории /srv/app.")
    # A client path never becomes an artifact allowlisted server root.
    with pytest.raises(ToolError, match="outside|allowed"):
        await call(
            "post_artifact",
            task_id=task.id,
            agent="codex",
            kind="text",
            path="/home/codex/my checkout/result.txt",
        )


async def test_mapping_subdirectories_unrelated_paths_and_reset(session):
    project = await make_project(session)
    subdir = await make_task(session, project, "/srv/app/packages/api")
    external = await make_task(session, project, "/srv/app-other")
    await call("set_project_path", project_id=project.id, local_repo_path="/mnt/c/work/app")
    context = await call("get_task_context", task_id=subdir.id)
    assert context["repo_path"] == "/mnt/c/work/app/packages/api"
    context = await call("get_task_context", task_id=external.id)
    assert context["repo_path"] is None
    assert context["server_repo_path"] == "/srv/app-other"
    assert context["repo_path_source"] == "unresolved"
    assert context["repo_path_error"]
    assert "уточни перед изменениями" in context["agent_prompt"]
    # Updating is an upsert; removing it restores shared-path behavior.
    await call("set_project_path", project_id=project.id, local_repo_path="/home/new/app")
    assert (await call("get_task_context", task_id=subdir.id))[
        "repo_path"
    ] == "/home/new/app/packages/api"
    await call("set_project_path", project_id=project.id)
    assert (await call("get_task_context", task_id=subdir.id))[
        "repo_path"
    ] == "/srv/app/packages/api"
    assert await session.get(AgentProjectPath, (project.id, "codex")) is None
    # No shared path is needed when the agent supplies a root for the project.
    empty_project = await make_project(session, None)
    task = await make_task(session, empty_project)
    await call("set_project_path", project_id=empty_project.id, local_repo_path="/home/local/app")
    assert (await call("get_task_context", task_id=task.id))["repo_path"] == "/home/local/app"


async def test_invalid_paths_missing_project_and_unauthenticated_registration(session, monkeypatch):
    project = await make_project(session)
    await call("set_project_path", project_id=project.id, local_repo_path="/home/valid")
    for path in (
        "",
        "relative/repo",
        "~/repo",
        "C:\\work",
        "//host/share",
        "/home/a/../b",
        "/home/a\x00",
        "/home/a\n",
        "/" + "a" * 4096,
    ):
        with pytest.raises(ToolError):
            await call("set_project_path", project_id=project.id, local_repo_path=path)
    assert (await call("list_projects"))[0]["repo_path"] == "/home/valid"
    with pytest.raises(ToolError, match="project not found"):
        await call("set_project_path", project_id=999999, local_repo_path="/home/a")
    from agent_kanban import mcp_server
    from tests.test_mcp_server import _real_require_any_principal

    monkeypatch.setattr(mcp_server, "_require_any_principal", _real_require_any_principal)
    with pytest.raises(ToolError, match="authentication required"):
        await call("set_project_path", project_id=project.id, local_repo_path="/home/a")
