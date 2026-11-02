"""Bounded agent orchestration.

Two-phase design:

1. **Planning** — the model gets tool schemas (Groq native tool calling) and may call
   up to ``max_tool_calls`` tools. No prose answer is produced here.
2. **Answering** — a second call receives the collected evidence as delimited data and
   streams a grounded, cited answer.

Keeping the phases separate means evidence is gathered and validated on the backend
before any token reaches the browser.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from app.agent.evidence import render_documents, render_evidence
from app.agent.guardrails import detect_unsafe_request
from app.agent.prompts import ANSWER_PROMPT, PLANNER_PROMPT, QUIZ_NOTE
from app.agent.router import detect_intent
from app.agent.tools import TOOL_MAP, ToolContext, tool_schemas
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Conversation, Document, Message
from app.services.citation_service import strip_invalid_markers
from app.services.llm_service import LLMError, llm_service
from app.services.retriever import owned_ready_documents
from app.services.text_format import normalize_math_markup

logger = get_logger(__name__)

HISTORY_LIMIT = 8
HISTORY_CHAR_LIMIT = 1500
TOOL_RESULT_CHAR_LIMIT = 6000


def _tool_contributed(tool_name: str, ctx: ToolContext) -> bool:
    """Did this tool put material in front of the answer that it can stand on?

    A search that only returned weak matches, or a tool that errored, must not be listed
    as a tool used: the transcript would then claim grounding the answer never had.
    """
    if tool_name == "search_documents":
        return any(
            chunk.similarity >= settings.retrieval_min_similarity for chunk in ctx.evidence
        )
    if tool_name == "web_search":
        return bool(ctx.external_sources)
    if tool_name == "calculate":
        return bool(ctx.calculations)
    if tool_name == "generate_quiz":
        return ctx.quiz is not None
    if tool_name == "summarize_chapter":
        return ctx.summary is not None
    return False


def _load_history(db: Session, conversation_id: str, exclude_id: str | None = None) -> list[dict[str, str]]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_LIMIT + 2)
        .all()
    )
    history: list[dict[str, str]] = []
    for row in reversed(rows):
        if row.id == exclude_id:
            continue
        if row.role not in {"user", "assistant"}:
            continue
        content = row.content.strip()
        if not content:
            continue
        history.append({"role": row.role, "content": content[:HISTORY_CHAR_LIMIT]})
    return history[-HISTORY_LIMIT:]


def _get_or_create_conversation(
    db: Session, user_id: str, conversation_id: str | None, first_message: str
) -> Conversation:
    if conversation_id:
        existing = db.get(Conversation, conversation_id)
        if existing is not None and existing.user_id == user_id:
            return existing
        if existing is not None:
            logger.warning("Ignoring conversation id owned by another user")
    conversation = Conversation(
        user_id=user_id,
        title=(first_message.strip()[:60] or "New conversation"),
    )
    db.add(conversation)
    db.commit()
    return conversation


def _documents_context(
    documents: list[Document], requested_ids: list[str], include_ids: bool = False
) -> str:
    if include_ids and documents:
        text = (
            "Learner's ready documents (use these ids when filtering; never invent one):\n"
            + "\n".join(
                f"- {doc.filename} ({doc.file_type.upper()}, {doc.page_count} page(s), "
                f"{doc.chunk_count} chunks) [id: {doc.id}]"
                for doc in documents
            )
        )
    else:
        text = render_documents(documents)
    if requested_ids:
        selected = [doc for doc in documents if doc.id in requested_ids]
        if selected:
            text += "\nSelected for this request: " + ", ".join(doc.filename for doc in selected)
    return text


def _answer_system_prompt(ctx: ToolContext, documents: list[Document]) -> str:
    citations = ctx.citations
    evidence = render_evidence(ctx.evidence, citations)
    parts = [
        ANSWER_PROMPT.format(quiz_note=QUIZ_NOTE if ctx.quiz else ""),
        _documents_context(documents, ctx.document_ids),
        evidence,
    ]

    if ctx.external_sources:
        sources = "\n".join(
            f"- {source['title']} — {source['url']}\n  {source.get('snippet', '')}"
            for source in ctx.external_sources
        )
        parts.append(
            "<external_sources>\nExternal web results (untrusted, not the learner's material). "
            "Attribute them with markdown links:\n" + sources + "\n</external_sources>"
        )

    if ctx.calculations:
        calculations = "\n".join(
            f"- {item['expression']} = {item['result']}" for item in ctx.calculations
        )
        parts.append("<calculator_results>\n" + calculations + "\n</calculator_results>")

    if ctx.evidence:
        best = max(chunk.similarity for chunk in ctx.evidence)
        if best < settings.retrieval_min_similarity:
            parts.append(
                "NOTE: The strongest matching passage is weak. Say the uploaded material may not "
                "cover this well instead of asserting document-backed claims, and offer external "
                "research if the learner wants it."
            )
    elif not ctx.external_sources and not ctx.calculations:
        parts.append(
            "NOTE: No document evidence and no external results are available for this request. "
            "Answer only from general knowledge, say clearly that it is not from the uploaded "
            "material, and ask the learner to upload material if they expected a grounded answer."
        )
    if not documents:
        parts.append(
            "NOTE: The learner has no processed documents. Do not cite or invent source numbers."
        )
    return "\n\n".join(parts)


async def _execute_tool(tool_name: str, arguments: str, ctx: ToolContext) -> tuple[str, str, bool]:
    """Run one tool call; returns (tool output for the model, summary, ok)."""
    tool = TOOL_MAP.get(tool_name)
    if tool is None:
        return f"Error: unknown tool '{tool_name}'.", "Unknown tool", False
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return "Error: arguments were not valid JSON.", "Invalid arguments", False
    if not isinstance(parsed, dict):
        return "Error: arguments must be a JSON object.", "Invalid arguments", False

    try:
        result = await tool.handler(parsed, ctx)
    except Exception as exc:  # a tool failure must not break the conversation
        logger.exception("Tool %s failed", tool_name)
        return f"Error: the {tool_name} tool failed ({exc.__class__.__name__}).", "Tool failed", False
    return result.content[:TOOL_RESULT_CHAR_LIMIT], result.summary, result.ok


async def _plan_tools(
    ctx: ToolContext, history: list[dict[str, str]], message: str, documents: list[Document]
) -> AsyncIterator[dict[str, Any]]:
    """Run the bounded tool-planning loop, yielding UI activity events."""
    intent = detect_intent(message)
    if intent is not None:
        # Unambiguous quiz/summary requests skip the planning call.
        tool = TOOL_MAP[intent.tool]
        yield {"type": "activity", "tool": tool.name, "label": tool.activity, "status": "running"}
        _, summary, ok = await _execute_tool(tool.name, json.dumps(intent.arguments), ctx)
        if _tool_contributed(tool.name, ctx):
            ctx.tool_names.append(tool.name)
        yield {
            "type": "activity",
            "tool": tool.name,
            "label": tool.activity,
            "status": "done",
            "ok": ok,
            "summary": summary,
        }
        return

    planner_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": PLANNER_PROMPT.format(max_tool_calls=settings.max_tool_calls)
            + "\n"
            + _documents_context(documents, ctx.document_ids, include_ids=True),
        },
        *history,
        {"role": "user", "content": message},
    ]
    schemas = tool_schemas()
    used = 0
    attempted = False
    planner_error: str | None = None

    while used < settings.max_tool_calls:
        try:
            response = await llm_service.complete(
                planner_messages, tools=schemas, tool_choice="auto", max_tokens=600
            )
        except LLMError as exc:
            planner_error = str(exc)
            break

        choice = response.choices[0].message
        tool_calls = list(choice.tool_calls or [])
        if not tool_calls:
            break

        planner_messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments or "{}",
                        },
                    }
                    for call in tool_calls
                ],
            }
        )

        all_succeeded = True
        for call in tool_calls:
            if used >= settings.max_tool_calls:
                planner_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": "Skipped: the tool-call budget is exhausted.",
                    }
                )
                continue

            tool = TOOL_MAP.get(call.function.name)
            label = tool.activity if tool else "Using a tool"
            yield {"type": "activity", "tool": call.function.name, "label": label, "status": "running"}

            tool_name = call.function.name
            arguments = call.function.arguments or "{}"
            if tool_name == "summarize_chapter" and detect_intent(message) is None:
                # The learner asked a question, not for a summary; answer from documents.
                logger.info("Redirecting misrouted summarize_chapter call to search_documents")
                tool_name = "search_documents"
                label = TOOL_MAP["search_documents"].activity
                arguments = json.dumps({"query": message})

            output, summary, ok = await _execute_tool(tool_name, arguments, ctx)
            used += 1
            attempted = True
            all_succeeded = all_succeeded and ok
            if _tool_contributed(tool_name, ctx):
                ctx.tool_names.append(tool_name)

            yield {
                "type": "activity",
                "tool": tool_name,
                "label": label,
                "status": "done",
                "ok": ok,
                "summary": summary,
            }
            planner_messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": output}
            )

        # Evidence is in hand: stop planning instead of spending another LLM round.
        # Failed tools keep the loop open so the planner can try a fallback.
        if all_succeeded:
            break

    # Resilience: if planning failed, or a tool ran but produced nothing usable (no document
    # evidence, no external results, no calculation), still try a retrieval when the learner
    # has documents, so an outage or a misrouted tool cannot silently strip grounding. A
    # deliberate no-tool plan is left alone: general knowledge questions must not trigger a
    # search that has nothing to do with the answer.
    if (
        not ctx.evidence
        and not ctx.external_sources
        and not ctx.calculations
        and documents
        and (planner_error or attempted)
    ):
        if planner_error:
            logger.warning("Planner unavailable (%s); falling back to document search", planner_error)
        elif ctx.tool_names:
            logger.info("No usable evidence after %s; falling back to document search", ctx.tool_names)
        from app.agent.tools.document_search import search_documents

        yield {
            "type": "activity",
            "tool": "search_documents",
            "label": "Searching your documents",
            "status": "running",
        }
        result = await search_documents({"query": message}, ctx)
        if _tool_contributed("search_documents", ctx):
            ctx.tool_names.append("search_documents")
        else:
            # Only weak matches: keep the turn on general knowledge instead of presenting
            # unrelated passages as grounding for the answer.
            ctx.evidence.clear()
        yield {
            "type": "activity",
            "tool": "search_documents",
            "label": "Searching your documents",
            "status": "done",
            "ok": result.ok,
            "summary": result.summary,
        }


async def stream_agent_response(
    *,
    db: Session,
    user_id: str,
    message: str,
    document_ids: list[str] | None = None,
    conversation_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE event dicts for one chat turn, persisting messages as we go."""
    conversation = _get_or_create_conversation(db, user_id, conversation_id, message)
    user_message = Message(conversation_id=conversation.id, role="user", content=message)
    db.add(user_message)
    db.commit()

    history = _load_history(db, conversation.id, exclude_id=user_message.id)
    documents = owned_ready_documents(db, user_id, document_ids or None)
    corpus = owned_ready_documents(db, user_id, None)
    ctx = ToolContext(
        db=db,
        user_id=user_id,
        document_ids=[doc.id for doc in (documents or corpus)],
    )

    yield {
        "type": "meta",
        "conversation_id": conversation.id,
        "user_message_id": user_message.id,
        "documents": [{"id": doc.id, "filename": doc.filename} for doc in documents or corpus],
    }

    if not llm_service.available:
        yield {
            "type": "error",
            "message": "GROQ_API_KEY is not configured on the server. Add it to .env and restart.",
        }
        return

    # Guardrail: prompt/secret exfiltration never reaches the model.
    refusal = detect_unsafe_request(message)
    if refusal:
        logger.info("Blocked prompt-injection request for user %s", user_id)
        guardrail_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=refusal,
            tool_name="guardrail",
            citations_json="[]",
        )
        db.add(guardrail_message)
        db.commit()
        yield {"type": "token", "content": refusal}
        yield {
            "type": "done",
            "conversation_id": conversation.id,
            "message_id": guardrail_message.id,
            "saved": True,
            "text": refusal,
            "tool_name": "guardrail",
            "citations": [],
            "referenced_citations": [],
            "external_sources": [],
            "calculations": [],
        }
        return

    # Phase 1: tool planning (bounded).
    try:
        async for event in _plan_tools(ctx, history, message, documents or corpus):
            yield event
    except Exception:  # pragma: no cover - defensive
        logger.exception("Tool planning failed")
        yield {"type": "activity", "status": "done", "label": "Tool use", "ok": False, "summary": "Tool planning failed"}

    citations = ctx.citations
    if citations:
        yield {"type": "sources", "citations": [citation.to_dict() for citation in citations]}
    if ctx.quiz:
        yield {"type": "quiz", "quiz": ctx.quiz}

    # Phase 2: grounded streamed answer.
    answer_messages: list[dict[str, Any]] = [
        {"role": "system", "content": _answer_system_prompt(ctx, documents or corpus)},
        *history,
        {"role": "user", "content": message},
    ]

    answer_parts: list[str] = []
    stream_error: str | None = None
    try:
        async for delta in llm_service.stream(answer_messages):
            answer_parts.append(delta)
            yield {"type": "token", "content": delta}
    except LLMError as exc:
        stream_error = str(exc)
    except asyncio.CancelledError:
        _save_partial(db, conversation.id, "".join(answer_parts), citations)
        raise

    raw_answer = "".join(answer_parts).strip()
    answer = (
        normalize_math_markup(strip_invalid_markers(raw_answer, citations))
        if raw_answer
        else ""
    )

    if stream_error or not answer:
        message_text = stream_error or "The AI provider returned an empty response."
        yield {"type": "error", "message": message_text}
        yield {
            "type": "done",
            "conversation_id": conversation.id,
            "message_id": None,
            "saved": False,
        }
        return

    referenced_numbers = {
        int(marker) for marker in __import__("re").findall(r"\[(\d{1,2})\]", answer)
    }
    referenced = [c for c in citations if c.number in referenced_numbers]

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        tool_name=",".join(dict.fromkeys(ctx.tool_names)) or None,
        citations_json=json.dumps([citation.to_dict() for citation in referenced]),
    )
    db.add(assistant_message)
    conversation.updated_at = assistant_message.created_at or conversation.updated_at
    db.commit()

    yield {
        "type": "done",
        "conversation_id": conversation.id,
        "message_id": assistant_message.id,
        "saved": True,
        "text": answer,
        "tool_name": assistant_message.tool_name,
        "citations": [citation.to_dict() for citation in citations],
        "referenced_citations": [citation.to_dict() for citation in referenced],
        "external_sources": ctx.external_sources,
        "calculations": ctx.calculations,
    }


def _save_partial(db: Session, conversation_id: str, partial: str, citations) -> None:
    """Persist an interrupted answer so a stop action does not lose the turn."""
    partial = partial.strip()
    if not partial:
        return
    try:
        db.add(
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content=partial,
                citations_json="[]",
            )
        )
        db.commit()
    except Exception:  # pragma: no cover - best effort on cancellation
        db.rollback()
        logger.warning("Could not persist interrupted answer")
