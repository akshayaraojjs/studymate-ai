"""Authentication and ownership checks (TC-12)."""
from __future__ import annotations

import uuid

from tests.conftest import upload_text


def test_register_login_and_me(client):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"name": "Ada Learner", "email": email, "password": "secret-pass-1"},
    )
    assert register.status_code == 201
    body = register.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == email
    assert body["user"]["name"] == "Ada Learner"

    duplicate = client.post(
        "/api/v1/auth/register",
        json={"name": "Ada Again", "email": email, "password": "secret-pass-1"},
    )
    assert duplicate.status_code == 409

    wrong = client.post("/api/v1/auth/login", json={"email": email, "password": "nope-nope"})
    assert wrong.status_code == 401

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-pass-1"})
    assert login.status_code == 200

    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == body["user"]["id"]


def test_password_is_hashed(client, auth):
    from app.db.models import User
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == auth["email"]).first()
        assert user is not None
        assert user.password_hash != auth["password"]
        assert user.password_hash.startswith("$2")
    finally:
        db.close()


def test_rejects_invalid_registration_input(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "A", "email": "not-an-email", "password": "short"},
    )
    assert response.status_code == 422


def test_requires_authentication(client):
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get("/api/v1/conversations").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    bad = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401


def test_cross_user_document_access_is_denied(client, auth, ready_document):
    other = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Other Learner",
            "email": f"other-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    document_id = ready_document["id"]

    assert client.get(f"/api/v1/documents/{document_id}", headers=other_headers).status_code == 404
    assert client.delete(f"/api/v1/documents/{document_id}", headers=other_headers).status_code == 404
    search = client.post(
        f"/api/v1/documents/{document_id}/search",
        headers=other_headers,
        json={"query": "normalization"},
    )
    assert search.status_code == 404

    assert client.get("/api/v1/documents", headers=other_headers).json() == []


def test_upload_requires_auth(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 401


def test_conversation_history_is_scoped_to_owner(client, auth):
    upload_text(client, auth["headers"])
    other = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Third Learner",
            "email": f"third-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get("/api/v1/conversations", headers=other_headers).json() == []

    missing = client.get(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000000/messages",
        headers=other_headers,
    )
    assert missing.status_code == 404
