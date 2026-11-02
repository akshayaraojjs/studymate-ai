"""Agent planning, streaming and citation plumbing (TC-04, TC-09, TC-14)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services.llm_service import llm_service


def _tool_call(name: str, arguments: dict, call_id: str = "call_1"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _planner_response(tool_calls=None, content=""):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ]
    )


def _parse_sse(raw: str) -> list[dict]:
    events = []
    for frame in raw.split("\n\n"):
        for line in frame.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


@pytest.fixture
def llm_enabled(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "retrieval_min_similarity", -1.0)
    yield


def test_chat_streams_grounded_answer_with_citations(
    client, auth, ready_document, llm_enabled
):
    async def fake_stream(_messages, **_kwargs):
        yield "Normalization organises data to reduce redundancy "
        yield "and update anomalies [1]."

    complete = AsyncMock(
        side_effect=[
            _planner_response([_tool_call("search_documents", {"query": "normalization"})]),
            _planner_response(content="READY"),
        ]
    )

    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "Explain normalization from my notes."},
        ) as response:
            assert response.status_code == 200
            raw = "".join(response.iter_text())

    events = _parse_sse(raw)
    types = [event["type"] for event in events]
    assert "meta" in types
    assert "sources" in types
    assert "token" in types
    assert types[-1] == "done"

    sources = next(event for event in events if event["type"] == "sources")
    assert sources["citations"]
    citation = sources["citations"][0]
    assert citation["document_name"] == ready_document["filename"]
    assert citation["page_number"] >= 1
    assert citation["chunk_id"]

    done = events[-1]
    assert done["saved"] is True
    assert "[1]" in done["text"]
    assert done["referenced_citations"][0]["chunk_id"] == citation["chunk_id"]
    assert done["tool_name"] == "search_documents"

    # History is persisted and reloadable with citations intact.
    conversation_id = done["conversation_id"]
    history = client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=auth["headers"]
    ).json()
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert history[1]["citations"]
    assert history[1]["tool_name"] == "search_documents"


def test_chat_strips_invented_citation_markers(client, auth, ready_document, llm_enabled):
    async def fake_stream(_messages, **_kwargs):
        yield "Databases use tables [1]. Invented source [7] must go."

    complete = AsyncMock(
        side_effect=[
            _planner_response([_tool_call("search_documents", {"query": "relational database tables"})]),
            _planner_response(content="READY"),
        ]
    )
    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "How are relational databases structured?"},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["type"] == "done"
    assert "[1]" in done["text"]
    assert "[7]" not in done["text"]


def test_calculator_tool_is_selected_for_arithmetic(client, auth, llm_enabled):
    complete = AsyncMock(
        side_effect=[
            _planner_response([_tool_call("calculate", {"expression": "(85 / 100) * 100"})]),
            _planner_response(content="READY"),
        ]
    )

    async def fake_stream(_messages, **_kwargs):
        yield "The accuracy is 85%."

    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "Calculate the accuracy if 85 of 100 predictions are correct."},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["calculations"][0]["result"] == "85"
    assert done["tool_name"] == "calculate"


def test_employee_off_topic_question_can_skip_tools(client, auth, llm_enabled):
    complete = AsyncMock(side_effect=[_planner_response(content="READY")])

    async def fake_stream(_messages, **_kwargs):
        yield "I can help you study your uploaded material. Would you like to continue with one of your course topics?"

    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "Write me a cover letter for a marketing job."},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["type"] == "done"
    assert done["tool_name"] is None


def test_search_recovers_from_invented_document_id(
    client, auth, ready_document, llm_enabled
):
    """A guessed id must not filter out every passage and strand the answer."""

    async def fake_stream(_messages, **_kwargs):
        yield "A database stores structured data in tables [1]."

    complete = AsyncMock(
        side_effect=[
            _planner_response(
                [
                    _tool_call(
                        "search_documents",
                        {
                            "query": "database fundamentals",
                            "document_ids": ["00000000-0000-0000-0000-000000000000"],
                        },
                    )
                ]
            ),
            _planner_response(content="READY"),
        ]
    )
    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "Explain Database Fundamentals."},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["citations"], "search should fall back to the selected documents"
    assert done["citations"][0]["page_number"] >= 1
    assert done["tool_name"] == "search_documents"


def test_search_accepts_a_filename_as_document_filter(
    client, auth, ready_document, llm_enabled
):
    async def fake_stream(_messages, **_kwargs):
        yield "Normalization reduces redundancy [1]."

    complete = AsyncMock(
        side_effect=[
            _planner_response(
                [
                    _tool_call(
                        "search_documents",
                        {
                            "query": "normalization",
                            "document_ids": [ready_document["filename"]],
                        },
                    )
                ]
            ),
            _planner_response(content="READY"),
        ]
    )
    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "Explain normalization."},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["citations"]
    assert done["citations"][0]["document_name"] == ready_document["filename"]


def test_answer_normalises_model_latex(client, auth, llm_enabled):
    """Calculator restatements must reach the browser as plain text, not LaTeX."""

    async def fake_stream(_messages, **_kwargs):
        yield "Result: \\((20 + 50) \\times 60 - \\frac{40}{8} = 4{,}195\\)"

    complete = AsyncMock(
        side_effect=[
            _planner_response([_tool_call("calculate", {"expression": "(20 + 50) * 60 - 40 / 8"})]),
            _planner_response(content="READY"),
        ]
    )
    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "What is (20 + 50) * 60 - 40 / 8?"},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["text"] == "Result: (20 + 50) × 60 - 40/8 = 4,195"
    assert done["calculations"][0]["result"] == "4195"


def test_general_question_does_not_report_a_document_search(
    client, auth, ready_document, llm_enabled
):
    """The planner may answer from general knowledge; no rescue search, no tool credit."""

    async def fake_stream(_messages, **_kwargs):
        yield "BODMAS orders operations: brackets, orders, division, multiplication, addition, subtraction."

    complete = AsyncMock(side_effect=[_planner_response(content="READY")])
    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "What is BODMAS Rule?"},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["type"] == "done"
    assert done["tool_name"] is None
    assert done["citations"] == []


def test_weak_document_matches_are_not_reported_as_a_tool(
    client, auth, ready_document, monkeypatch
):
    """An irrelevant search must not be listed as the tool behind the answer."""
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(settings, "retrieval_min_similarity", 1.1)

    async def fake_stream(_messages, **_kwargs):
        yield "BODMAS orders operations: brackets, orders, division, multiplication, addition, subtraction."

    complete = AsyncMock(
        side_effect=[
            _planner_response([_tool_call("search_documents", {"query": "BODMAS rule"})]),
            _planner_response(content="READY"),
        ]
    )
    with patch.object(llm_service, "complete", complete), patch.object(
        llm_service, "stream", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=auth["headers"],
            json={"message": "What is BODMAS Rule?"},
        ) as response:
            events = _parse_sse("".join(response.iter_text()))

    done = events[-1]
    assert done["type"] == "done"
    assert done["tool_name"] is None


def test_chat_requires_llm_configuration(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    response = client.post(
        "/api/v1/chat/stream",
        headers=auth["headers"],
        json={"message": "Hello"},
    )
    assert response.status_code == 503
