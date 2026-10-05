"""Restrictions remain human controlled and are refreshed in agent context."""
import pytest


@pytest.mark.asyncio
async def test_instructions_inherit_dynamically_and_prompt_contains_task_context(authed_client):
    c = authed_client
    project = (await c.post('/api/projects', json={
        'name': 'Odyssey', 'repo_path': '/work/SD',
        'agent_instructions': 'Изменять только /work/SD/bundles/Odyssey. Не менять .env*.',
    })).json()
    task = (await c.post('/api/tasks', json={
        'project_id': project['id'], 'title': 'Fix grid', 'description': 'POST /api/grid returns 500',
        'agent_instructions': 'Не отключать индексацию. npm run build.',
        'acceptance_criteria': 'POST returns 200',
    })).json()
    assert task['agent_instructions'] == 'Не отключать индексацию. npm run build.'
    await c.post(f"/api/tasks/{task['id']}/comments", json={'author': 'user', 'content': 'folderId=53739'})
    context = (await c.get(f"/api/tasks/{task['id']}/context")).json()
    for text in ['Изменять только /work/SD/bundles/Odyssey', 'Не отключать индексацию',
                 'POST /api/grid returns 500', 'POST returns 200', 'folderId=53739', '/work/SD', 'AGENTS.md']:
        assert text in context['agent_prompt']
    assert context['project_agent_instructions'] == project['agent_instructions']
    updated = await c.patch(f"/api/projects/{project['id']}", json={'agent_instructions': 'Новые ограничения: no migrations'})
    assert updated.status_code == 200
    context = (await c.get(f"/api/tasks/{task['id']}/context")).json()
    assert context['project_agent_instructions'] == 'Новые ограничения: no migrations'
    assert 'Новые ограничения: no migrations' in context['agent_prompt']
    assert 'Изменять только /work/SD/bundles/Odyssey' not in context['agent_prompt']
    changed = await c.patch(f"/api/tasks/{task['id']}", json={'agent_instructions': 'Новая область задачи'})
    assert changed.status_code == 200
    assert changed.json()['agent_instructions'] == 'Новая область задачи'
    for path in [f"/api/projects/{project['id']}", f"/api/tasks/{task['id']}"]:
        assert (await c.patch(path, json={'agent_instructions': None})).status_code in (409, 422)
    assert (await c.get('/api/tasks/999999/context')).status_code == 404


@pytest.mark.asyncio
async def test_agent_can_read_but_cannot_rewrite_restrictions(authed_client):
    c = authed_client
    project = (await c.post('/api/projects', json={'name': 'Restricted', 'agent_instructions': 'Only src/'})).json()
    task = (await c.post('/api/tasks', json={'title': 'Limited task', 'project_id': project['id'], 'agent_instructions': 'No infrastructure'})).json()
    token = (await c.post('/api/tokens', json={'agent_name': 'worker'})).json()['token']
    c.cookies.clear()  # Exercise token authentication without a human session.
    headers = {'Authorization': f'Bearer {token}'}
    context = await c.get(f"/api/tasks/{task['id']}/context", headers=headers)
    assert context.status_code == 200
    assert 'Only src/' in context.json()['agent_prompt']
    for path in [f"/api/projects/{project['id']}", f"/api/tasks/{task['id']}"]:
        assert (await c.patch(path, json={'agent_instructions': 'All files allowed'}, headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_legacy_empty_restrictions_and_review_context_mcp(session):
    from agent_kanban.models import Project, Task
    from agent_kanban.mcp_server import mcp
    from tests.test_mcp_server import _to_dict
    project = Project(name='Legacy')
    session.add(project)
    await session.commit()
    await session.refresh(project)
    task = Task(title='Legacy task', project_id=project.id)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    context = _to_dict(await mcp.call_tool('get_task_context', {'task_id': task.id}))
    assert context['project_agent_instructions'] == ''
    assert context['agent_instructions'] == ''
    project.agent_instructions = 'Review must obey the same src/ boundary'
    task.agent_instructions = 'Check compatibility'
    session.add(project)
    session.add(task)
    await session.commit()
    context = _to_dict(await mcp.call_tool('get_task_context', {'task_id': task.id}))
    assert 'Review must obey the same src/ boundary' in context['agent_prompt']
    assert 'Check compatibility' in context['agent_prompt']
