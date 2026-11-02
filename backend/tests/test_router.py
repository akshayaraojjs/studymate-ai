"""Intent router and tool-routing guard tests."""
from __future__ import annotations

from app.agent.router import detect_intent


def test_routes_explicit_quiz_requests():
    intent = detect_intent("Create five practice questions on SQL joins.")
    assert intent is not None
    assert intent.tool == "generate_quiz"
    assert intent.arguments["topic"].lower().startswith("sql joins")
    assert intent.arguments["num_questions"] == 5

    intent = detect_intent("Write five quiz questions about database indexes.")
    assert intent is not None and intent.tool == "generate_quiz"
    assert "indexes" in intent.arguments["topic"].lower()


def test_routes_explicit_summary_requests():
    intent = detect_intent("Summarize Chapter 3.")
    assert intent is not None
    assert intent.tool == "summarize_chapter"
    assert intent.arguments["chapter"].lower() == "chapter 3"

    intent = detect_intent("Summarize page 2 of my notes.")
    assert intent is not None
    assert intent.arguments["page_start"] == 2 and intent.arguments["page_end"] == 2

    intent = detect_intent("Give me an overview of the chapter on indexing.")
    assert intent is not None
    assert intent.arguments["chapter"].lower() == "indexing"


def test_topic_questions_are_not_routed_as_summaries():
    assert detect_intent("Explain database normalization from my notes.") is None
    assert detect_intent("What does third normal form remove?") is None
    assert detect_intent("Calculate the accuracy if 85 of 100 predictions are correct.") is None
    assert detect_intent("What is the capital of France?") is None
    assert detect_intent("Summarize my notes.") is None
