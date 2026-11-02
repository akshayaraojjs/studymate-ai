"""generate_quiz tool: evidence-grounded, schema-validated multiple-choice quizzes."""
from __future__ import annotations

import json
from typing import Any

from app.agent.evidence import render_evidence
from app.agent.prompts import QUIZ_PROMPT
from app.agent.tools.base import AgentTool, ToolContext, ToolResult
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import QuizAttempt
from app.services.citation_service import Citation
from app.services.embeddings import embed_query
from app.services.llm_service import LLMError, llm_service
from app.services.retriever import search_chunks

logger = get_logger(__name__)

DEFAULT_QUESTIONS = 5
OPTIONS_PER_QUESTION = 4


class QuizValidationError(ValueError):
    pass


def _validate_quiz(payload: Any, required: int, citations: list[Citation]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise QuizValidationError("Top-level JSON must be an object.")
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise QuizValidationError("'questions' must be a list.")
    if len(questions) != required:
        raise QuizValidationError(f"Expected exactly {required} questions, received {len(questions)}.")

    by_number = {citation.number: citation for citation in citations}
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            raise QuizValidationError(f"Question {index} is not an object.")
        question = str(item.get("question") or "").strip()
        if len(question) < 8:
            raise QuizValidationError(f"Question {index} is missing text.")
        options = item.get("options")
        if not isinstance(options, list) or len(options) != OPTIONS_PER_QUESTION:
            raise QuizValidationError(f"Question {index} must have exactly {OPTIONS_PER_QUESTION} options.")
        options = [str(option).strip() for option in options]
        if any(not option for option in options):
            raise QuizValidationError(f"Question {index} has an empty option.")
        if len(set(options)) != OPTIONS_PER_QUESTION:
            raise QuizValidationError(f"Question {index} has duplicate options.")
        correct = item.get("correct_option")
        if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct < OPTIONS_PER_QUESTION:
            raise QuizValidationError(f"Question {index} has an invalid correct_option.")
        explanation = str(item.get("explanation") or "").strip()
        if not explanation:
            raise QuizValidationError(f"Question {index} is missing an explanation.")

        raw_sources = item.get("source_numbers") or []
        if not isinstance(raw_sources, list):
            raw_sources = []
        source_numbers: set[int] = set()
        for value in raw_sources:
            try:
                number = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if number in by_number:
                source_numbers.add(number)
        cleaned.append(
            {
                "id": index,
                "question": question,
                "options": options,
                "correct_option": correct,
                "explanation": explanation,
                "source_numbers": sorted(source_numbers),
                "source_ids": [by_number[num].chunk_id for num in source_numbers],
            }
        )

    topic = str(payload.get("topic") or "").strip()[:150]
    return {"topic": topic, "questions": cleaned}


async def generate_quiz(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    topic = str(args.get("topic") or "").strip()[:200]
    if not topic:
        return ToolResult(content="Error: 'topic' is required.", ok=False, summary="Quiz not generated")

    requested = args.get("document_ids") or ctx.document_ids
    if not isinstance(requested, list):
        requested = ctx.document_ids

    try:
        required = int(args.get("num_questions") or DEFAULT_QUESTIONS)
    except (TypeError, ValueError):
        required = DEFAULT_QUESTIONS
    required = max(3, min(8, required))

    chunks = search_chunks(
        db=ctx.db,
        user_id=ctx.user_id,
        query_embedding=embed_query(topic),
        document_ids=[str(doc_id) for doc_id in requested] or None,
        top_k=8,
    )
    if not chunks:
        return ToolResult(
            content=(
                "No relevant material was found, so no quiz was generated. Tell the learner to "
                "upload or select a document that covers this topic."
            ),
            ok=False,
            summary="No source material for the quiz",
        )

    citations = ctx.add_evidence(chunks)
    best_similarity = max(chunk.similarity for chunk in chunks)
    if best_similarity < settings.retrieval_min_similarity:
        return ToolResult(
            content=(
                f"The best matching passage is weak (similarity {best_similarity:.2f}), so no quiz "
                "was generated. Ask the learner to confirm the topic or upload material that covers it."
            ),
            ok=False,
            summary="Evidence too weak for a quiz",
        )

    messages = [
        {"role": "system", "content": QUIZ_PROMPT.format(num_questions=required)},
        {
            "role": "user",
            "content": f"Topic: {topic}\n\n{render_evidence(chunks, citations)}",
        },
    ]

    quiz: dict[str, Any] | None = None
    last_error = "No quiz was produced."
    for attempt in range(2):
        try:
            raw = await llm_service.complete_json(messages, temperature=0.3, max_tokens=2500)
        except LLMError as exc:
            return ToolResult(
                content=f"Quiz generation failed: {exc}",
                ok=False,
                summary="Quiz generation failed",
            )
        try:
            quiz = _validate_quiz(json.loads(raw), required, citations)
            break
        except (json.JSONDecodeError, QuizValidationError) as exc:
            last_error = str(exc)
            logger.warning("Quiz response rejected (attempt %s): %s", attempt + 1, last_error)
            messages.append({"role": "assistant", "content": raw[:4000]})
            messages.append(
                {
                    "role": "user",
                    "content": f"Invalid response ({last_error}). Return corrected JSON only.",
                }
            )

    if quiz is None:
        return ToolResult(
            content=f"Quiz generation failed validation: {last_error}",
            ok=False,
            summary="Quiz validation failed",
        )

    quiz["citations"] = [citation.to_dict() for citation in citations]
    ctx.quiz = quiz

    attempt_row = QuizAttempt(
        user_id=ctx.user_id,
        document_id=(requested[0] if len(requested) == 1 else None),
        topic=quiz["topic"] or topic,
        questions_json=json.dumps(
            {"topic": quiz["topic"] or topic, "questions": quiz["questions"], "citations": quiz["citations"]}
        ),
    )
    ctx.db.add(attempt_row)
    ctx.db.commit()
    quiz["attempt_id"] = attempt_row.id

    return ToolResult(
        content=(
            f"Generated a {len(quiz['questions'])}-question quiz on '{quiz['topic'] or topic}'. "
            "It is displayed to the learner in the quiz panel."
        ),
        ok=True,
        summary=f"Generated a {len(quiz['questions'])}-question quiz",
    )


generate_quiz_tool = AgentTool(
    name="generate_quiz",
    description=(
        "Create a multiple-choice practice quiz grounded in the learner's documents. "
        "Use when the learner asks for practice questions, a quiz, or to test their knowledge."
    ),
    parameters={
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Topic or concept the quiz should cover, e.g. 'SQL joins'.",
            },
            "num_questions": {
                "type": "integer",
                "description": "Number of questions (default 5).",
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional subset of document IDs to draw from.",
            },
        },
        "required": ["topic"],
    },
    handler=generate_quiz,
    activity="Generating a quiz",
)
