"""search_documents tool: semantic retrieval over the learner's own files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agent.tools.base import AgentTool, ToolContext, ToolResult
from app.services.embeddings import embed_query
from app.services.retriever import owned_ready_documents, search_chunks


def _resolve_scope(ctx: ToolContext, requested: list[Any]) -> list[str]:
    """Map the planner's document filter onto the learner's selected documents.

    Models regularly pass a filename or an invented id instead of the real UUID, and a
    strict ``id IN (...)`` filter would then silently remove every passage. Unknown values
    are dropped; when nothing resolves, the request's selected documents are used.
    """
    selection = list(ctx.document_ids)
    wanted = [str(value).strip() for value in requested if isinstance(value, str) and value.strip()]
    if not wanted:
        return selection

    allowed = set(selection)
    resolved = [value for value in wanted if value in allowed]
    if resolved:
        return list(dict.fromkeys(resolved))

    documents = owned_ready_documents(ctx.db, ctx.user_id, selection or None)
    by_name: dict[str, str] = {}
    for document in documents:
        by_name[document.id] = document.id
        by_name[document.filename.strip().lower()] = document.id
        by_name[Path(document.filename).stem.strip().lower()] = document.id
    for value in wanted:
        match = by_name.get(value.lower())
        if match and match in allowed:
            resolved.append(match)

    # No usable filter: search everything that was selected for this request.
    return list(dict.fromkeys(resolved)) or selection


async def search_documents(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    query = str(args.get("query") or "").strip()[:500]
    if not query:
        return ToolResult(content="Error: 'query' is required.", ok=False, summary="Search failed")

    requested = args.get("document_ids") or ctx.document_ids
    if not isinstance(requested, list):
        requested = ctx.document_ids

    query_embedding = embed_query(query)
    scope = _resolve_scope(ctx, requested)
    chunks = search_chunks(
        db=ctx.db,
        user_id=ctx.user_id,
        query_embedding=query_embedding,
        document_ids=scope or None,
        query_text=query,
    )
    if not chunks and scope and set(scope) != set(ctx.document_ids):
        # A narrower filter found nothing; widen to the request's selected documents
        # rather than telling the learner their material does not cover the topic.
        chunks = search_chunks(
            db=ctx.db,
            user_id=ctx.user_id,
            query_embedding=query_embedding,
            document_ids=ctx.document_ids or None,
            query_text=query,
        )
    if not chunks:
        return ToolResult(
            content=(
                "No matching passages found. Either no documents are ready, or none of the "
                "learner's documents cover this topic."
            ),
            ok=False,
            summary="No matching passages",
        )

    citations = ctx.add_evidence(chunks)
    by_chunk = {citation.chunk_id: citation for citation in citations}
    lines = []
    for chunk in chunks[:5]:
        citation = by_chunk[chunk.chunk_id]
        excerpt = chunk.content[:280].replace("\n", " ").strip()
        lines.append(
            f"[{citation.number}] {citation.document_name}, page {citation.page_number}"
            f"{', section: ' + citation.section_title if citation.section_title else ''}"
            f" (similarity {chunk.similarity:.2f})\n    {excerpt}"
        )
    best = max(chunk.similarity for chunk in chunks)
    return ToolResult(
        content="Retrieved passages:\n" + "\n".join(lines) + f"\nBest similarity: {best:.2f}",
        ok=True,
        summary=f"Found {len(chunks)} passage{'s' if len(chunks) != 1 else ''}",
    )


search_documents_tool = AgentTool(
    name="search_documents",
    description=(
        "Search the learner's uploaded study material for passages relevant to a query. "
        "Use it when the question refers to that material: a chapter or section heading from "
        "the document list, or wording like 'my notes' or 'the lecture'. Do not use it for "
        "general facts or definitions the learner did not tie to their files. "
        "Returns numbered passages with file name, page number and section heading."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Focused search query, e.g. 'database normalization third normal form'.",
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional subset of document IDs, using the ids shown in the document list. "
                    "Omit to search all selected documents."
                ),
            },
        },
        "required": ["query"],
    },
    handler=search_documents,
    activity="Searching your documents",
)
