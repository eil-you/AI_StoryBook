"""Integration tests for /auth endpoints (register, login, logout)."""

import pytest
from fastapi.testclient import TestClient

_REGISTER_URL = "/auth/register"
_LOGIN_URL = "/auth/login"
_LOGOUT_URL = "/auth/logout"

_EMAIL = "user@example.com"
_PASSWORD = "securepassword1"


# ===========================================================================
# POST /auth/register
# ===========================================================================


def test_register_returns_201_with_user_info(client: TestClient):
    resp = client.post(_REGISTER_URL, json={"email": _EMAIL, "password": _PASSWORD})

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == _EMAIL
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email_returns_409(client: TestClient):
    payload = {"email": _EMAIL, "password": _PASSWORD}
    client.post(_REGISTER_URL, json=payload)

    resp = client.post(_REGISTER_URL, json=payload)

    assert resp.status_code == 409


def test_register_invalid_email_returns_422(client: TestClient):
    resp = client.post(_REGISTER_URL, json={"email": "not-an-email", "password": _PASSWORD})

    assert resp.status_code == 422


def test_register_missing_password_returns_422(client: TestClient):
    resp = client.post(_REGISTER_URL, json={"email": _EMAIL})

    assert resp.status_code == 422


# ===========================================================================
# POST /auth/login
# ===========================================================================


def test_login_returns_access_token(client: TestClient):
    client.post(_REGISTER_URL, json={"email": _EMAIL, "password": _PASSWORD})

    resp = client.post(_LOGIN_URL, json={"email": _EMAIL, "password": _PASSWORD})

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


def test_login_wrong_password_returns_401(client: TestClient):
    client.post(_REGISTER_URL, json={"email": _EMAIL, "password": _PASSWORD})

    resp = client.post(_LOGIN_URL, json={"email": _EMAIL, "password": "wrongpassword"})

    assert resp.status_code == 401


def test_login_nonexistent_email_returns_401(client: TestClient):
    resp = client.post(_LOGIN_URL, json={"email": "ghost@example.com", "password": _PASSWORD})

    assert resp.status_code == 401


def test_login_invalid_email_format_returns_422(client: TestClient):
    resp = client.post(_LOGIN_URL, json={"email": "bad-email", "password": _PASSWORD})

    assert resp.status_code == 422


# ===========================================================================
# POST /auth/logout
# ===========================================================================


def test_logout_returns_204(client: TestClient):
    resp = client.post(_LOGOUT_URL)

    assert resp.status_code == 204


# ===========================================================================
# 인증이 필요한 엔드포인트 보호 검증
# ===========================================================================


def test_protected_endpoint_without_token_returns_401(client: TestClient):
    """토큰 없이 보호된 엔드포인트에 접근하면 401을 반환합니다."""
    resp = client.post("/api/v1/stories/generate", json={})

    assert resp.status_code in (401, 403)


def test_protected_endpoint_with_invalid_token_returns_401(client: TestClient):
    """잘못된 토큰으로 접근하면 401을 반환합니다."""
    resp = client.post(
        "/api/v1/stories/generate",
        json={},
        headers={"Authorization": "Bearer invalidtoken"},
    )

    assert resp.status_code in (401, 403)


def test_protected_endpoint_with_valid_token_passes_auth(client: TestClient, auth_headers: dict):
    """유효한 토큰으로 접근하면 인증이 통과됩니다 (422 = 바디 검증 실패, not 401/403)."""
    resp = client.post("/api/v1/stories/generate", json={}, headers=auth_headers)

    # 인증은 통과했으므로 401/403이 아닌 422(바디 검증 실패)가 와야 합니다.
    assert resp.status_code == 422
