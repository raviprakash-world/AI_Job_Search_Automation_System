import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.rate_limit import login_rate_limiter, register_rate_limiter


async def test_register_creates_account_and_returns_tokens(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "password123", "name": "New User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_register_duplicate_email_is_rejected(client: AsyncClient):
    payload = {"email": "dupe@example.com", "password": "password123", "name": "Dupe"}
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_login_with_correct_credentials(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "password123", "name": "Login User"},
    )
    resp = await client.post("/api/auth/login", json={"email": "login@example.com", "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_with_wrong_password_is_rejected(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "wrong@example.com", "password": "password123", "name": "Wrong Pass"},
    )
    resp = await client.post("/api/auth/login", json={"email": "wrong@example.com", "password": "nope12345"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_error"


async def test_me_requires_valid_token(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401

    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


async def test_register_rejects_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short", "name": "Short"},
    )
    assert resp.status_code == 422


async def test_refresh_token_issues_a_new_access_token(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "refresh@example.com", "password": "password123", "name": "Refresh User"},
    )
    refresh_token = resp.json()["refresh_token"]

    refreshed = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert "access_token" in body and "refresh_token" in body

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "refresh@example.com"


async def test_refresh_rejects_an_access_token(client: AsyncClient, auth_headers: dict):
    access_token = auth_headers["Authorization"].removeprefix("Bearer ")
    resp = await client.post("/api/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


async def test_refresh_rejects_garbage_token(client: AsyncClient):
    resp = await client.post("/api/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401


@pytest.fixture
def _rate_limiting_enabled():
    settings = get_settings()
    settings.enable_rate_limiting = True
    login_rate_limiter.reset()
    register_rate_limiter.reset()
    yield
    settings.enable_rate_limiting = False
    login_rate_limiter.reset()
    register_rate_limiter.reset()


async def test_login_is_rate_limited_after_repeated_failures(client: AsyncClient, _rate_limiting_enabled):
    await client.post(
        "/api/auth/register",
        json={"email": "limited@example.com", "password": "password123", "name": "Limited"},
    )
    for _ in range(login_rate_limiter.max_attempts):
        resp = await client.post(
            "/api/auth/login", json={"email": "limited@example.com", "password": "wrong-password"}
        )
        assert resp.status_code == 401

    over_limit = await client.post(
        "/api/auth/login", json={"email": "limited@example.com", "password": "wrong-password"}
    )
    assert over_limit.status_code == 429
    assert over_limit.json()["error"]["code"] == "rate_limited"

    # a different email from the same client is unaffected
    unaffected = await client.post(
        "/api/auth/login", json={"email": "someone-else@example.com", "password": "wrong-password"}
    )
    assert unaffected.status_code == 401
