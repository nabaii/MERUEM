import pytest


def test_register_and_login(client):
    # Register
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "test@meruem.io", "password": "supersecret123", "full_name": "Test User"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "test@meruem.io"
    assert data["role"] == "client"

    # Login
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "test@meruem.io", "password": "supersecret123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    return token


def test_duplicate_registration(client):
    for _ in range(2):
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@meruem.io", "password": "supersecret123"},
        )
    assert r.status_code == 409


def test_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "wp@meruem.io", "password": "supersecret123"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "wp@meruem.io", "password": "wrongpassword"},
    )
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 403  # HTTPBearer returns 403 when no credentials


def test_me_with_token(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "me@meruem.io", "password": "supersecret123"},
    )
    token_r = client.post(
        "/api/v1/auth/login",
        json={"email": "me@meruem.io", "password": "supersecret123"},
    )
    token = token_r.json()["access_token"]

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@meruem.io"


def test_generate_api_key(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "key@meruem.io", "password": "supersecret123"},
    )
    token_r = client.post(
        "/api/v1/auth/login",
        json={"email": "key@meruem.io", "password": "supersecret123"},
    )
    token = token_r.json()["access_token"]

    r = client.post("/api/v1/auth/api-key", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    key = r.json()["api_key"]
    assert len(key) > 20

    # Verify the API key works as Bearer auth
    r2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {key}"})
    assert r2.status_code == 200
