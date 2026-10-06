import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from agent_kanban.auth import decrypt_token
from agent_kanban.models import OpenRouterSettings
from agent_kanban.routes import openrouter
from agent_kanban.server import create_app


async def configure(client):
    return await client.put(
        "/api/openrouter/settings", json={"model": "test/model", "api_key": "secret-test-key"}
    )


async def test_settings_encrypted_and_blank_preserves_key(authed_client, session):
    response = await configure(authed_client)
    assert response.json() == {"model": "test/model", "has_key": True, "has_management_key": False}
    stored = await session.get(OpenRouterSettings, 1)
    assert stored.api_key_ciphertext != "secret-test-key"
    assert decrypt_token(stored.api_key_ciphertext) == "secret-test-key"
    response = await authed_client.put(
        "/api/openrouter/settings", json={"model": "another/model", "api_key": ""}
    )
    assert response.json()["has_key"]
    assert "secret-test-key" not in (await authed_client.get("/api/openrouter/settings")).text
    response = await authed_client.put(
        "/api/openrouter/settings", json={"model": "another/model", "clear_key": True}
    )
    assert not response.json()["has_key"]


async def test_unauthenticated_access(db_url):
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        for method, path in [("GET", "settings"), ("GET", "balance"), ("POST", "draft")]:
            response = await client.request(
                method, "/api/openrouter/" + path, json={} if method == "POST" else None
            )
            assert response.status_code == 401


async def test_draft_context_and_no_task_creation(authed_client, monkeypatch):
    await configure(authed_client)
    generated = dict(
        title="Task",
        description="Spec",
        acceptance_criteria="- Works",
        agent_instructions="Run tests",
    )
    mock = AsyncMock(return_value={"choices": [{"message": {"content": json.dumps(generated)}}]})
    monkeypatch.setattr(openrouter, "provider", mock)
    response = await authed_client.post(
        "/api/openrouter/draft",
        json={"description": "Simple request", "project_instructions": "Use existing architecture"},
    )
    assert response.status_code == 200
    assert response.json() == generated
    payload = mock.call_args.args[3]
    assert payload["model"] == "test/model"
    assert "Use existing architecture" in payload["messages"][1]["content"]
    assert (await authed_client.get("/api/tasks")).json() == []


async def test_missing_key_and_invalid_output(authed_client, monkeypatch):
    response = await authed_client.post("/api/openrouter/draft", json={"title": "Task"})
    assert response.status_code == 409
    await configure(authed_client)
    monkeypatch.setattr(
        openrouter,
        "provider",
        AsyncMock(return_value={"choices": [{"message": {"content": "not json"}}]}),
    )
    assert (
        await authed_client.post("/api/openrouter/draft", json={"title": "Task"})
    ).status_code == 502


async def test_balance_with_restricted_credits(authed_client, monkeypatch):
    from fastapi import HTTPException

    await configure(authed_client)
    monkeypatch.setattr(
        openrouter,
        "provider",
        AsyncMock(
            side_effect=[
                {"data": {"limit_remaining": 4, "usage": 1}},
                HTTPException(502, "restricted"),
            ]
        ),
    )
    response = await authed_client.get("/api/openrouter/balance")
    assert response.json() == {"balance": None, "key_remaining": 4, "usage": 1}


async def test_provider_error_does_not_leak_secrets(monkeypatch):
    import httpx

    config = OpenRouterSettings(api_key_ciphertext=openrouter.encrypt_token("private-key"))
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": "private-key"})
    )
    original = httpx.AsyncClient
    monkeypatch.setattr(
        openrouter.httpx, "AsyncClient", lambda **kw: original(transport=transport, **kw)
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        await openrouter.provider(config, "GET", "/key")
    assert "private-key" not in error.value.detail


async def test_startup_runs_migrations_before_bootstrap(db_url, monkeypatch):
    from agent_kanban import cli, server

    calls = []
    monkeypatch.setattr(cli, "_run_migrations", lambda: calls.append("migrate"))

    async def bootstrap():
        calls.append("bootstrap")

    monkeypatch.setattr(server, "_bootstrap_admin", bootstrap)
    app = create_app()
    async with app.router.lifespan_context(app):
        assert calls == ["migrate", "bootstrap"]


async def test_failed_migration_prevents_startup(db_url, monkeypatch):
    from agent_kanban import cli

    def fail():
        raise RuntimeError("migration failed")

    monkeypatch.setattr(cli, "_run_migrations", fail)
    app = create_app()
    with pytest.raises(RuntimeError, match="migration failed"):
        async with app.router.lifespan_context(app):
            pytest.fail("Server started despite failed migration")


async def test_criteria_only_keeps_other_fields(authed_client, monkeypatch):
    await configure(authed_client)
    monkeypatch.setattr(
        openrouter,
        "provider",
        AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "acceptance_criteria": "- Observable behavior",
                                    "description": "changed",
                                }
                            )
                        }
                    }
                ]
            }
        ),
    )
    response = await authed_client.post(
        "/api/openrouter/draft",
        json={
            "mode": "criteria",
            "description": "Original",
            "agent_instructions": "Original instructions",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "title": "",
        "description": "Original",
        "acceptance_criteria": "- Observable behavior",
        "agent_instructions": "Original instructions",
    }


async def test_management_key_is_encrypted_and_not_returned(authed_client, session):
    response = await authed_client.put(
        "/api/openrouter/settings",
        json={
            "model": "test/model",
            "api_key": "inference-key",
            "management_key": "management-secret",
        },
    )
    assert response.json()["has_management_key"]
    assert "management-secret" not in response.text
    stored = await session.get(OpenRouterSettings, 1)
    assert decrypt_token(stored.management_key_ciphertext) == "management-secret"
    assert "management-secret" not in stored.management_key_ciphertext


async def test_image_links_are_preserved(authed_client, monkeypatch):
    await configure(authed_client)
    monkeypatch.setattr(
        openrouter,
        "provider",
        AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                dict(
                                    title="Task",
                                    description="No images",
                                    acceptance_criteria="Works",
                                    agent_instructions="",
                                )
                            )
                        }
                    }
                ]
            }
        ),
    )
    response = await authed_client.post(
        "/api/openrouter/draft", json={"description": "Look at ![screen](/api/artifacts/1/content)"}
    )
    assert response.status_code == 502


async def test_non_admin_can_draft_but_cannot_access_settings(authed_client, monkeypatch):
    await configure(authed_client)
    await authed_client.post(
        "/api/users", json={"username": "member", "password": "password123", "is_admin": False}
    )
    await authed_client.post("/api/logout")
    await authed_client.post("/api/login", json={"username": "member", "password": "password123"})
    assert (await authed_client.get("/api/openrouter/settings")).status_code == 403
    assert (await authed_client.get("/api/openrouter/balance")).status_code == 403
    assert (
        await authed_client.put("/api/openrouter/settings", json={"model": "other"})
    ).status_code == 403
    monkeypatch.setattr(
        openrouter,
        "provider",
        AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                dict(
                                    title="Task",
                                    description="Spec",
                                    acceptance_criteria="Works",
                                    agent_instructions="",
                                )
                            )
                        }
                    }
                ]
            }
        ),
    )
    assert (
        await authed_client.post("/api/openrouter/draft", json={"title": "Task"})
    ).status_code == 200


async def test_management_key_used_only_for_credits(monkeypatch):
    import httpx

    config = OpenRouterSettings(
        api_key_ciphertext=openrouter.encrypt_token("inference"),
        management_key_ciphertext=openrouter.encrypt_token("management"),
    )
    seen = []

    def respond(request):
        seen.append((request.url.path, request.headers["Authorization"]))
        return httpx.Response(200, json={"data": {}})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
    )
    await openrouter.provider(config, "GET", "/key")
    await openrouter.provider(config, "GET", "/credits")
    assert seen == [("/api/v1/key", "Bearer inference"), ("/api/v1/credits", "Bearer management")]


async def test_real_startup_migrations_are_idempotent(db_url):
    for _ in range(2):
        app = create_app()
        async with app.router.lifespan_context(app):
            pass
