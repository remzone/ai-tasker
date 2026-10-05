"""End-to-end test of the MCP HTTP auth chain.

The rest of the MCP test suite drives the tools in-process via
``mcp.call_tool`` with stubbed verifiers. This module proves the real HTTP path:
a ``POST /mcp/`` carrying ``Authorization: Bearer <token>`` flows through
``MCPAuthMiddleware`` → the current HTTP request scope → the verifier → the
tool. A request with no bearer must not yield a normal success result.
"""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kanban.server import create_app
from agent_kanban.mcp_server import _require_any_principal as real_any, _require_matching_agent as real_matching


def _sse_payload(text: str) -> dict:
    """Extract the first JSON-RPC object from an MCP SSE response body.

    The streamable-http transport frames each JSON-RPC message as an SSE
    ``event: message\\n data: <json>`` block. The payload (the dict) is what
    callers should assert on.
    """
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                return json.loads(line[len("data:"):].strip())
            except json.JSONDecodeError:
                continue
    # Fallback: the whole body might be plain JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text}


def _maybe_json(response) -> dict:
    try:
        return response.json()
    except Exception:
        return {"_raw": response.text}


@pytest.fixture
async def http_client(db_url, monkeypatch):
    """An httpx AsyncClient over the app with the MCP session manager running.

    We do NOT drive the app's full lifespan here: its ``session_manager.run()``
    spawns an anyio task group whose cancel scope must exit in the same task that
    entered it, and pytest-asyncio tears async-generator fixtures down in a
    different task, which raises "Attempted to exit cancel scope in a different
    task". Instead we start only the MCP session manager (the one thing /mcp/
    needs to be servable) and create the admin user directly. Both setups and
    their teardown run inside this fixture's own task, so their cancel scopes
    exit cleanly.
    """
    import os
    from agent_kanban import mcp_server
    monkeypatch.setattr(mcp_server, "_require_any_principal", real_any)
    monkeypatch.setattr(mcp_server, "_require_matching_agent", real_matching)
    from agent_kanban.config import get_settings
    from agent_kanban.db import AsyncSessionLocal
    from agent_kanban.models import User
    from agent_kanban.auth import hash_password

    os.environ["AGENT_KANBAN_BOOTSTRAP_ADMIN_PASSWORD"] = "pw"
    get_settings.cache_clear()
    app = create_app()
    # Create the admin user directly (the app lifespan would have done this).
    async with AsyncSessionLocal() as session:
        session.add(User(username="admin", password_hash=hash_password("pw"), is_admin=True))
        await session.commit()
    mcp_instance = app.state.mcp
    transport = ASGITransport(app=app)
    client = AsyncClient(
        transport=transport,
        base_url="http://localhost",
        headers={
            # The MCP streamable-http transport validates:
            #   - Host header (DNS-rebinding protection): allows "localhost:*" —
            #     the host MUST include a port; and
            #   - Accept header: POSTs must accept application/json and
            #     text/event-stream.
            "host": "localhost:80",
            "accept": "application/json, text/event-stream",
        },
    )
    session_mgr_cm = mcp_instance.session_manager.run()
    await session_mgr_cm.__aenter__()
    try:
        await client.__aenter__()
        try:
            yield client
        finally:
            await client.__aexit__(None, None, None)
    finally:
        # pytest-asyncio may finalize this async-generator fixture on a
        # different task than setup; the MCP session_manager's anyio cancel
        # scope must exit in its entering task. Swallow the resulting
        # RuntimeError — the test body has already passed and the throwaway
        # DB (and its connections) are dropped by the `db_url` fixture anyway.
        try:
            await session_mgr_cm.__aexit__(None, None, None)
        except RuntimeError:
            pass
        os.environ.pop("AGENT_KANBAN_BOOTSTRAP_ADMIN_PASSWORD", None)


async def _bootstrap_admin_and_token(http_client):
    """Log in as the lifespan-bootstrapped admin, mint a token for 'codex'.

    Returns the plaintext token.
    """
    await http_client.post("/api/login", json={"username": "admin", "password": "pw"})
    r = await http_client.post("/api/tokens", json={"agent_name": "codex"})
    return r.json()["token"]


_INIT_PARAMS = {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test", "version": "1.0"},
}


@pytest.mark.asyncio
async def test_mcp_http_rejects_unauthenticated(http_client):
    """A tools/call to /mcp/ without a bearer token must fail (the verifier raises)."""
    # initialize to obtain a session id
    r = await http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": _INIT_PARAMS},
    )
    session_id = r.headers.get("mcp-session-id")
    headers = {"mcp-session-id": session_id} if session_id else {}
    # list_tasks without bearer → the verifier raises PermissionError → tool error.
    r = await http_client.post(
        "/mcp/",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "list_tasks", "arguments": {}}},
    )
    # The streamable-http transport responds with SSE; the JSON-RPC payload is
    # in a `data:` line. Some SDK versions reply with a plain JSON body instead,
    # so handle both.
    if r.headers.get("content-type", "").startswith("text/event-stream"):
        body = _sse_payload(r.text)
    else:
        body = _maybe_json(r)
    # The key assertion: an unauthenticated call did NOT return a normal
    # empty-list success. Accept a JSON-RPC error, an is_error tool result, or
    # a 4xx status — the exact shape depends on the pinned SDK version.
    result_str = str(body)
    assert (
        "auth" in result_str.lower()
        or "error" in result_str.lower()
        or r.status_code in (400, 401, 403)
    ), f"expected auth/error, got {r.status_code}: {body}"


@pytest.mark.asyncio
async def test_mcp_http_accepts_bearer_token(http_client):
    """A tools/call with a valid bearer token + matching agent succeeds."""
    token = await _bootstrap_admin_and_token(http_client)
    auth = {"Authorization": f"Bearer {token}"}
    # initialize to get a session id
    r = await http_client.post(
        "/mcp/",
        headers=auth,
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": _INIT_PARAMS},
    )
    session_id = r.headers.get("mcp-session-id")
    headers = dict(auth)
    if session_id:
        headers["mcp-session-id"] = session_id
    # list_tasks should succeed (empty list — no tasks created).
    r = await http_client.post(
        "/mcp/",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "list_tasks", "arguments": {}}},
    )
    assert r.status_code == 200
    body = _sse_payload(r.text)
    # No "error" key at the JSON-RPC level on the success path.
    assert "error" not in body, f"unexpected JSON-RPC error: {body}"


class WireAgent:
    """Real JSON-RPC transport and bearer authorization, without tool stubs."""
    def __init__(self, client, token, name):
        self.client = client
        self.name = name
        self.headers = {"Authorization": f"Bearer {token}"}
        self.seq = 1

    async def initialize(self):
        r = await self.client.post("/mcp", headers=self.headers,
            json={"jsonrpc": "2.0", "id": self.seq, "method": "initialize", "params": _INIT_PARAMS})
        assert r.status_code == 200, r.text
        self.headers["mcp-session-id"] = r.headers["mcp-session-id"]
        self.headers["mcp-protocol-version"] = _INIT_PARAMS["protocolVersion"]
        r = await self.client.post("/mcp", headers=self.headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert r.status_code == 202

    async def call(self, name, args=None, error=False):
        self.seq += 1
        r = await self.client.post("/mcp", headers=self.headers,
            json={"jsonrpc": "2.0", "id": self.seq, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})
        assert r.status_code == 200, r.text
        body = _sse_payload(r.text)
        assert "error" not in body, body
        result = body["result"]
        if error:
            assert result.get("isError"), result
            return result
        assert not result.get("isError"), result
        data = result.get("structuredContent")
        if data is not None:
            return data.get("result") if set(data) == {"result"} else data
        blocks = [json.loads(b["text"]) for b in result.get("content", []) if b["type"] == "text"]
        return blocks[0] if len(blocks) == 1 else blocks or None


@pytest.mark.asyncio
async def test_full_http_review_acceptance_and_returns(http_client, monkeypatch):
    from pathlib import Path
    monkeypatch.setenv("AGENT_KANBAN_ARTIFACT_DIR", str(Path(".runtime/test-artifacts").resolve()))
    await http_client.post("/api/login", json={"username": "admin", "password": "pw"})
    agents = []
    for name in ("codex", "reviewer", "rival"):
        r = await http_client.post("/api/tokens", json={"agent_name": name})
        a = WireAgent(http_client, r.json()["token"], name)
        await a.initialize()
        agents.append(a)
    worker, reviewer, rival = agents
    r = await http_client.post("/api/projects", json={"name": "Test project", "repo_path": str(Path.cwd()), "default_branch": "main"})
    project_id = r.json()["id"]
    r = await http_client.post("/api/tasks", json={"title": "Implement", "description": "Original task", "acceptance_criteria": "Tests pass", "project_id": project_id})
    task_id = r.json()["id"]
    assert r.json()["repo_path"] == str(Path.cwd())
    await http_client.post(f"/api/tasks/{task_id}/comments", json={"author": "spoof", "content": "Remember empty input"})
    upload = await http_client.post(f"/api/artifacts/task/{task_id}/upload", files={"file": ("spec.txt", b"Acceptance detail", "text/plain")})
    assert upload.status_code == 201, upload.text
    assert (await http_client.get(f'/api/artifacts/{upload.json()["id"]}/content')).content == b"Acceptance detail"
    assert (await worker.call("list_projects"))[0]["id"] == project_id
    assert (await http_client.get(f"/api/tasks?project_id={project_id}")).json()[0]["id"] == task_id
    # Every generic bypass is rejected.
    for target in ("review", "acceptance", "done", "in_progress"):
        assert (await http_client.patch(f"/api/tasks/{task_id}", json={"status": target})).status_code == 409
    assert (await http_client.post(f"/api/tasks/{task_id}/acceptance", json={"approve": True})).status_code == 409
    assert (await http_client.patch(f"/api/tasks/{task_id}", json={"status": "ready"})).status_code == 200
    assert (await worker.call("get_next_task"))["id"] == task_id
    assert (await worker.call("claim_task", {"task_id": task_id, "agent": "codex"}))["ok"]
    assert not (await rival.call("claim_task", {"task_id": task_id, "agent": "rival"}))["ok"]
    await rival.call("post_progress", {"task_id": task_id, "agent": "codex", "kind": "text", "content": "spoof"}, error=True)
    context = await worker.call("get_task_context", {"task_id": task_id})
    assert context["acceptance_criteria"] == "Tests pass"
    assert context["comments"][0]["author"] == "user"
    assert context["attachments"][0]["description"] == "spec.txt"
    for round_no in (1, 2, 3):
        await worker.call("post_progress", {"task_id": task_id, "agent": "codex", "kind": "text", "content": f"Round {round_no}: tests pass; commit abc; changed file.py"})
        await worker.call("post_progress", {"task_id": task_id, "agent": "codex", "kind": "status_change", "content": "bypass", "status": {"to": "done"}}, error=True)
        await worker.call("request_review", {"task_id": task_id, "agent": "codex"}, error=True)
        reviewed = await worker.call("complete_task", {"task_id": task_id, "agent": "codex", "summary": f"Round {round_no}: commit abc, tests pass"})
        assert reviewed["status"] == "review"
        assert (await reviewer.call("get_next_review"))["id"] == task_id
        assert (await reviewer.call("claim_review", {"task_id": task_id, "agent": "reviewer"}))["ok"]
        assert not (await rival.call("claim_review", {"task_id": task_id, "agent": "rival"}))["ok"]
        await rival.call("submit_review", {"task_id": task_id, "agent": "rival", "decision": "APPROVE", "comment": "bypass"}, error=True)
        before = await reviewer.call("get_task_context", {"task_id": task_id})
        assert before["claimed_by"] == "codex" and before["reviewer"] == "reviewer"
        decision = "REQUEST_CHANGES" if round_no == 1 else "APPROVE"
        reviewed = await reviewer.call("submit_review", {"task_id": task_id, "agent": "reviewer", "decision": decision, "comment": "Add empty-input coverage" if round_no == 1 else "Verified tests and acceptance criteria"})
        if round_no == 1:
            assert reviewed["status"] == "in_progress" and reviewed["claimed_by"] is None
        elif round_no == 2:
            assert reviewed["status"] == "acceptance"
            assert (await http_client.post(f"/api/tasks/{task_id}/acceptance", json={"approve": False})).status_code == 409
            returned = await http_client.post(f"/api/tasks/{task_id}/acceptance", json={"approve": False, "comment": "Improve copy"})
            assert returned.json()["status"] == "in_progress"
        else:
            assert reviewed["status"] == "acceptance"
            await worker.call("request_review", {"task_id": task_id, "agent": "codex", "summary": "bypass"}, error=True)
            # Use no human cookie: an agent bearer cannot accept or PATCH Done.
            from httpx import AsyncClient
            async with AsyncClient(transport=http_client._transport, base_url="http://localhost", headers={"host": "localhost:80", "Authorization": worker.headers["Authorization"]}) as agent_http:
                assert (await agent_http.post(f"/api/tasks/{task_id}/acceptance", json={"approve": True})).status_code == 403
                assert (await agent_http.patch(f"/api/tasks/{task_id}", json={"status": "done"})).status_code == 403
            accepted = await http_client.post(f"/api/tasks/{task_id}/acceptance", json={"approve": True, "comment": "Accepted"})
            assert accepted.json()["status"] == "done"
            break
        assert (await worker.call("get_next_task"))["id"] == task_id
        assert (await worker.call("claim_task", {"task_id": task_id, "agent": "codex"}))["ok"]
    final = await worker.call("get_task_context", {"task_id": task_id})
    assert [e["payload"]["decision"] for e in final["progress"] if "decision" in e["payload"]] == ["REQUEST_CHANGES", "APPROVE", "RETURN", "APPROVE", "ACCEPT"]
    assert final["status"] == "done" and final["work_summary"].startswith("Round 3")


@pytest.mark.asyncio
async def test_mcp_auth_uses_current_request_after_anonymous_initialize(http_client):
    token = await _bootstrap_admin_and_token(http_client)
    agent = WireAgent(http_client, token, "codex")
    agent.headers.pop("Authorization")
    await agent.initialize()
    agent.headers["Authorization"] = f"Bearer {token}"
    assert await agent.call("list_projects") == []
    assert await agent.call("list_tasks") == []


@pytest.mark.asyncio
async def test_mcp_auth_does_not_reuse_initialize_token(http_client):
    token = await _bootstrap_admin_and_token(http_client)
    agent = WireAgent(http_client, token, "codex")
    await agent.initialize()
    agent.headers.pop("Authorization")
    missing = await agent.call("list_projects", error=True)
    assert "Authorization header is missing" in str(missing)
    agent.headers["Authorization"] = "Bearer invalid-token"
    invalid = await agent.call("list_tasks", error=True)
    assert "Bearer token is invalid or revoked" in str(invalid)
    agent.headers["Authorization"] = f"Bearer {token}"
    assert await agent.call("list_tasks") == []


@pytest.mark.asyncio
async def test_mcp_auth_agent_changes_with_request_token(http_client):
    token = await _bootstrap_admin_and_token(http_client)
    agent = WireAgent(http_client, token, "codex")
    await agent.initialize()
    r = await http_client.post("/api/tokens", json={"agent_name": "reviewer"})
    agent.headers["Authorization"] = f'Bearer {r.json()["token"]}'
    result = await agent.call("claim_task", {"task_id": 999999, "agent": "codex"}, error=True)
    assert "does not match" in str(result)


@pytest.mark.asyncio
async def test_revealed_token_and_replacement_on_real_mcp_session(http_client):
    await http_client.post('/api/login', json={'username': 'admin', 'password': 'pw'})
    created = (await http_client.post('/api/tokens', json={'agent_name': 'codex'})).json()
    token_id = created['id']
    token = (await http_client.post(f'/api/tokens/{token_id}/reveal')).json()['token']
    worker = WireAgent(http_client, token, 'codex')
    await worker.initialize()
    assert await worker.call('list_projects') == []
    replacement = (await http_client.post(f'/api/tokens/{token_id}/regenerate')).json()['token']
    await worker.call('list_tasks', error=True)
    worker.headers['Authorization'] = f'Bearer {replacement}'
    assert await worker.call('list_projects') == []
    assert await worker.call('list_tasks') == []


@pytest.mark.asyncio
async def test_human_workflow_requeue_assignment_and_acceptance(http_client):
    await http_client.post('/api/login', json={'username': 'admin', 'password': 'pw'})
    agents = {}
    secrets = {}
    for name in ('codex', 'reviewer', 'other'):
        created = (await http_client.post('/api/tokens', json={'agent_name': name})).json()
        secrets[name] = created['token']
        agents[name] = WireAgent(http_client, created['token'], name)
        await agents[name].initialize()
    task = (await http_client.post('/api/tasks', json={'title': 'Manual workflow', 'status': 'ready'})).json()
    task_id = task['id']
    async def decision(action, **values):
        return await http_client.post(f'/api/tasks/{task_id}/workflow', json={'action': action, **values})
    assert (await decision('accept')).status_code == 409
    assert (await decision('start')).json()['status'] == 'in_progress'
    assert (await agents['codex'].call('claim_task', {'task_id': task_id, 'agent': 'codex'}))['ok']
    requeued = await decision('ready')
    assert requeued.json()['status'] == 'ready'
    assert requeued.json()['claimed_by'] is None
    await agents['codex'].call('request_review', {'task_id': task_id, 'agent': 'codex', 'summary': 'Stale owner'}, error=True)
    assert (await decision('start')).status_code == 200
    bad = await decision('review', comment='Implementation complete', reviewer='unknown-agent')
    assert bad.status_code == 409
    assigned = await decision('review', comment='Implementation complete', reviewer='reviewer')
    assert assigned.json()['review_assigned_to'] == 'reviewer'
    assert assigned.json()['reviewer'] is None
    assert await agents['other'].call('get_next_review') is None
    assert (await agents['reviewer'].call('get_next_review'))['id'] == task_id
    assert not (await agents['other'].call('claim_review', {'task_id': task_id, 'agent': 'other'}))['ok']
    assert (await agents['reviewer'].call('claim_review', {'task_id': task_id, 'agent': 'reviewer'}))['ok']
    approved = await agents['reviewer'].call('submit_review', {'task_id': task_id, 'agent': 'reviewer', 'decision': 'APPROVE', 'comment': 'Verified criteria'})
    assert approved['status'] == 'acceptance'
    # A real bearer client without the human session cannot use the new endpoint.
    async with AsyncClient(transport=http_client._transport, base_url='http://localhost', headers={'Authorization': f'Bearer {secrets["other"]}'}) as bearer:
        assert (await bearer.post(f'/api/tasks/{task_id}/workflow', json={'action': 'accept'})).status_code == 403
    assert (await decision('return')).status_code == 409
    returned = await decision('return', comment='Fix empty input')
    assert returned.json()['status'] == 'in_progress'
    assert returned.json()['claimed_by'] is None
    assert (await decision('review', comment='Fix implemented', reviewer='reviewer')).status_code == 200
    # Human may verify and accept directly without waiting for an AI verdict.
    accepted = await decision('accept', comment='Personally verified')
    assert accepted.json()['status'] == 'done'
    assert accepted.json()['review_assigned_to'] is None
    assert (await decision('accept')).status_code == 409
    assert not (await agents['reviewer'].call('claim_review', {'task_id': task_id, 'agent': 'reviewer'}))['ok']
    history = (await http_client.get(f'/api/tasks/{task_id}/progress')).json()
    decisions = [p['payload'].get('decision') for p in history]
    assert 'REQUEUE' in decisions and 'SEND_REVIEW' in decisions and 'ACCEPT' in decisions and 'RETURN' in decisions
    comments = (await http_client.get(f'/api/tasks/{task_id}/comments')).json()
    assert any('Personally verified' in c['content'] for c in comments)
