"""Test bootstrap: isolated SQLite database, deterministic embeddings, no LLM calls."""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studymate-test-"))

# Must be set before the settings module is imported.
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["UPLOAD_DIR"] = str(_TMP / "data" / "uploads")
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["GROQ_API_KEY"] = ""
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import init_db  # noqa: E402
from app.main import app  # noqa: E402

SAMPLE_NOTES = """Chapter 1 Introduction to Databases

A database is an organised collection of structured data. A relational database stores
data in tables with rows and columns. SQL is the standard query language used to read
and modify relational data.

Chapter 2 SQL Joins

An INNER JOIN returns rows that have matching values in both tables. A LEFT JOIN returns
all rows from the left table plus matching rows from the right table. A CROSS JOIN
produces the cartesian product of both tables.

Chapter 3 Normalization

Normalization organises relational data to reduce redundancy and avoid update anomalies.
First normal form requires atomic column values. Second normal form removes partial
dependencies on a composite key. Third normal form removes transitive dependencies.
Denormalization intentionally reintroduces redundancy to speed up read queries.
"""

PDF_TEXT = """Chapter 1 Database Foundations

Normalization reduces data redundancy by organising attributes into related tables.
Each normal form removes a specific class of dependency. Third normal form requires that
non-key attributes depend only on the primary key.
"""


@pytest.fixture(scope="session", autouse=True)
def _database():
    init_db()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Keep in-process rate limiter state from leaking between tests."""
    from app.core.ratelimit import _HITS

    _HITS.clear()
    yield
    _HITS.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth(client):
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    password = "password123"
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Test Learner", "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return {
        "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        "user": payload["user"],
        "email": email,
        "password": password,
    }


def upload_text(client, headers, content: str = SAMPLE_NOTES, filename: str = "database-notes.txt"):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
    )


@pytest.fixture
def ready_document(client, auth):
    response = upload_text(client, auth["headers"])
    assert response.status_code == 201, response.text
    document = response.json()
    for _ in range(20):
        detail = client.get(f"/api/v1/documents/{document['id']}", headers=auth["headers"])
        assert detail.status_code == 200
        document = detail.json()
        if document["status"] != "processing":
            break
    assert document["status"] == "ready", document.get("error_message")
    return document


@pytest.fixture
def pdf_bytes() -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((60, 72), PDF_TEXT, fontsize=11)
    data = document.tobytes()
    document.close()
    return data
