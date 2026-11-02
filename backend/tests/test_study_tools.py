"""Quiz and summary endpoints with a stubbed LLM (TC-06, TC-07)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.llm_service import llm_service


def _quiz_payload(count: int = 5) -> dict:
    return {
        "topic": "SQL Joins",
        "questions": [
            {
                "question": f"Question {index}: which join matches rows in both tables?",
                "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "RIGHT JOIN"],
                "correct_option": 0,
                "explanation": "An INNER JOIN keeps rows that satisfy the join condition.",
                "source_numbers": [1],
            }
            for index in range(1, count + 1)
        ],
    }


@pytest.fixture
def llm_enabled(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "retrieval_min_similarity", -1.0)
    yield


def test_quiz_endpoint_returns_five_valid_questions(client, auth, ready_document, llm_enabled):
    complete_json = AsyncMock(return_value=json.dumps(_quiz_payload()))
    with patch.object(llm_service, "complete_json", complete_json):
        response = client.post(
            "/api/v1/study/quiz",
            headers=auth["headers"],
            json={"topic": "SQL joins", "num_questions": 5},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["questions"]) == 5
    assert payload["attempt_id"]
    for question in payload["questions"]:
        assert len(question["options"]) == 4
        assert 0 <= question["correct_option"] < 4
        assert question["explanation"]
        assert question["source_ids"]
    assert payload["citations"]


def test_quiz_retries_when_schema_is_invalid(client, auth, ready_document, llm_enabled):
    bad = json.dumps(
        {
            "topic": "SQL joins",
            "questions": [
                {
                    "question": "Only one question here?",
                    "options": ["A", "B", "C", "D"],
                    "correct_option": 0,
                    "explanation": "Incomplete.",
                    "source_numbers": [1],
                }
            ],
        }
    )
    complete_json = AsyncMock(side_effect=[bad, json.dumps(_quiz_payload())])
    with patch.object(llm_service, "complete_json", complete_json):
        response = client.post(
            "/api/v1/study/quiz",
            headers=auth["headers"],
            json={"topic": "SQL joins"},
        )

    assert response.status_code == 200
    assert complete_json.await_count == 2
    assert len(response.json()["questions"]) == 5


def test_quiz_fails_cleanly_when_validation_never_passes(
    client, auth, ready_document, llm_enabled
):
    complete_json = AsyncMock(return_value=json.dumps({"topic": "x", "questions": []}))
    with patch.object(llm_service, "complete_json", complete_json):
        response = client.post(
            "/api/v1/study/quiz",
            headers=auth["headers"],
            json={"topic": "SQL joins"},
        )
    assert response.status_code == 422
    assert "Expected exactly 5 questions" in response.json()["detail"]


def test_quiz_requires_documents(client, auth, llm_enabled):
    response = client.post(
        "/api/v1/study/quiz", headers=auth["headers"], json={"topic": "SQL joins"}
    )
    assert response.status_code == 422
    assert "No relevant material" in response.json()["detail"]


def test_summary_endpoint_returns_section_with_citations(
    client, auth, ready_document, llm_enabled
):
    markdown = "## Overview\nNormalization reduces redundancy [1].\n\n## Key concepts\n- 1NF [1]"
    complete = AsyncMock(
        return_value=type(
            "Response",
            (),
            {"choices": [type("Choice", (), {"message": type("Message", (), {"content": markdown})()})()]},
        )()
    )
    with patch.object(llm_service, "complete", complete):
        response = client.post(
            "/api/v1/study/summary",
            headers=auth["headers"],
            json={"chapter": "Chapter 3 Normalization"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["chapter"].startswith("Chapter 3")
    assert "Normalization" in payload["markdown"]
    assert payload["citations"]
    assert all(citation["page_number"] >= 1 for citation in payload["citations"])


def test_summary_reports_unknown_section(client, auth, ready_document, llm_enabled):
    response = client.post(
        "/api/v1/study/summary",
        headers=auth["headers"],
        json={"chapter": "Chapter 47 Quantum Computing"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "was not found" in detail
