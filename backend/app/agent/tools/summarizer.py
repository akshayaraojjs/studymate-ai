"""summarize_chapter tool: locate a section, then summarise only that section."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func

from app.agent.evidence import render_evidence
from app.agent.prompts import SUMMARY_PROMPT, SUMMARY_REQUEST
from app.agent.tools.base import AgentTool, ToolContext, ToolResult
from app.db.models import DocumentChunk
from app.services.llm_service import LLMError, llm_service
from app.services.retriever import RetrievedChunk, owned_ready_documents

MAX_SECTION_CHUNKS = 12
_PAGE_RANGE_RE = re.compile(r"(?:pages?|pp?\.)\s*(\d+)\s*(?:-|–|to)\s*(\d+)", re.IGNORECASE)
_PAGE_SINGLE_RE = re.compile(r"(?:page|p\.)\s*(\d+)", re.IGNORECASE)


def locate_section(
    ctx: ToolContext,
    chapter: str,
    document_ids: list[str],
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[RetrievedChunk]:
    """Find chunks belonging to the requested chapter/section, scoped to the user."""
    documents = owned_ready_documents(ctx.db, ctx.user_id, document_ids or None)
    if not documents:
        return []
    allowed_ids = [document.id for document in documents]
    filenames = {document.id: document.filename for document in documents}

    query = ctx.db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(allowed_ids))
    if page_start is not None:
        query = query.filter(DocumentChunk.page_number >= page_start)
    if page_end is not None:
        query = query.filter(DocumentChunk.page_number <= page_end)

    chapter = chapter.strip()
    chunks: list[DocumentChunk] = []
    if chapter:
        lowered = chapter.lower()
        heading_matches = (
            query.filter(func.lower(DocumentChunk.section_title).contains(lowered))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
            .limit(MAX_SECTION_CHUNKS)
            .all()
        )
        if heading_matches:
            chunks = heading_matches
        else:
            # Also accept a heading that stayed inside the chunk text, but only when the
            # whole phrase matches. A single shared word is not enough to identify a chapter.
            chunks = (
                query.filter(func.lower(DocumentChunk.content).contains(lowered))
                .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
                .limit(MAX_SECTION_CHUNKS)
                .all()
            )
    elif page_start is not None or page_end is not None:
        chunks = query.order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(
            MAX_SECTION_CHUNKS
        ).all()

    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_name=filenames.get(chunk.document_id, "document"),
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            similarity=1.0,
        )
        for chunk in chunks
    ]


async def summarize_chapter(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    chapter = str(args.get("chapter") or args.get("chapter_or_topic") or "").strip()[:200]
    requested = args.get("document_ids") or ctx.document_ids
    if not isinstance(requested, list):
        requested = ctx.document_ids
    requested = [str(doc_id) for doc_id in requested if isinstance(doc_id, str)]

    def as_page(value: Any) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    page_start = as_page(args.get("page_start"))
    page_end = as_page(args.get("page_end"))

    # Tolerate a planner that puts "page 2" or "pages 2-4" into the chapter field.
    if page_start is None and page_end is None and chapter:
        range_match = _PAGE_RANGE_RE.search(chapter)
        single_match = _PAGE_SINGLE_RE.search(chapter)
        if range_match:
            page_start = as_page(range_match.group(1))
            page_end = as_page(range_match.group(2))
            chapter = _PAGE_RANGE_RE.sub("", chapter).strip(" .,-")
        elif single_match:
            page_start = as_page(single_match.group(1))
            page_end = page_start
            chapter = _PAGE_SINGLE_RE.sub("", chapter).strip(" .,-")

    if not chapter and page_start is None and page_end is None:
        return ToolResult(
            content="No chapter or page range was provided.",
            ok=False,
            summary="No chapter specified",
        )

    chunks = locate_section(ctx, chapter, requested, page_start, page_end)

    if not chunks and chapter and (page_start is not None or page_end is not None):
        # "page 2 of my notes" leaves noise in the chapter field; the page range wins.
        chunks = locate_section(ctx, "", requested, page_start, page_end)

    if not chunks:
        target = chapter or f"pages {page_start}-{page_end}"
        return ToolResult(
            content=f"'{target}' was not found in the learner's documents.",
            ok=False,
            summary="Chapter not found",
        )

    citations = ctx.add_evidence(chunks)
    messages = [
        {"role": "system", "content": SUMMARY_PROMPT},
        {
            "role": "user",
            "content": SUMMARY_REQUEST.format(
                chapter=chapter or f"pages {page_start}-{page_end}",
                evidence=render_evidence(chunks, citations),
            ),
        },
    ]
    try:
        response = await llm_service.complete(messages, temperature=0.2, max_tokens=1800)
    except LLMError as exc:
        return ToolResult(content=f"Summarisation failed: {exc}", ok=False, summary="Summarisation failed")

    markdown = (response.choices[0].message.content or "").strip()
    if not markdown:
        return ToolResult(content="Summarisation returned no content.", ok=False, summary="Empty summary")

    ctx.summary = {
        "chapter": chapter or f"pages {page_start}-{page_end}",
        "markdown": markdown,
        "citations": [citation.to_dict() for citation in citations],
    }
    return ToolResult(
        content=(
            f"Summary of '{chapter or f'pages {page_start}-{page_end}'}':\n\n{markdown}\n\n"
            "Present this summary to the learner, keeping the citation numbers."
        ),
        ok=True,
        summary=f"Summarised {chapter or 'the page range'}",
    )


summarize_chapter_tool = AgentTool(
    name="summarize_chapter",
    description=(
        "Summarise one chapter, section or page range of the learner's documents. Provide the "
        "chapter name/heading, or a page range. Use when the learner asks for a summary or an "
        "overview of part of their material."
    ),
    parameters={
        "type": "object",
        "properties": {
            "chapter": {
                "type": "string",
                "description": "Chapter number, heading or section name, e.g. 'Chapter 3' or 'Normalization'.",
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional subset of document IDs.",
            },
            "page_start": {"type": "integer", "description": "First page of the range (optional)."},
            "page_end": {"type": "integer", "description": "Last page of the range (optional)."},
        },
        "required": [],
    },
    handler=summarize_chapter,
    activity="Summarising the section",
)
