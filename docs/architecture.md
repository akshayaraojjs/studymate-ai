# Architecture

## Request flow

### 1. Upload and indexing

```
POST /documents/upload
  → validate extension, MIME, %PDF magic, size, page count
  → store file under backend/data/uploads/<uuid>.<ext> (server-side name)
  → create document row (status = processing)
  → BackgroundTasks: process_document(document_id)
        extract pages (PyMuPDF / text decoding)
        clean text (whitespace, de-hyphenation, control chars)
        chunk (heading-aware, 700 tokens, 100 overlap, page + section metadata)
        embed (MiniLM 384 dims, one model for documents and queries)
        insert chunks (pgvector column on PostgreSQL, JSON on SQLite)
        status = ready | failed (+ error_message)
```

The UI polls `GET /documents` while anything is processing. Failed documents stay visible with
their error and can be deleted.

### 2. Chat turn

```
POST /chat/stream
  → authenticate (JWT) → rate limit per user
  → create conversation if needed, persist the user message
  → intent router: explicit quiz / chapter / page-range requests go straight to a tool
  → phase 1: planner call with 5 tool schemas (max 4 calls)
        each tool result is appended to the planner conversation
        activity events are emitted for the UI
  → build evidence block (numbered citations, untrusted delimiters, injection warnings)
  → phase 2: streaming answer with no tools
  → post-process: strip invented citation markers, persist assistant message + referenced sources
  → done event with final text, tools, citations, external sources, calculations
```

The planner never writes the answer; the answerer never calls tools. That keeps evidence and
citations under backend control.

### 3. Retrieval

`search_chunks(db, user_id, query_embedding, document_ids, top_k, query_text)`:

1. Resolve the user's `ready` documents (and optional selected subset). Foreign document ids are
   ignored.
2. PostgreSQL with pgvector: `ORDER BY embedding <=> $1 LIMIT k` through the HNSW cosine index.
3. SQLite, or PostgreSQL without pgvector: load candidate chunks for those documents and rank
   with NumPy cosine similarity (the embedding column is JSON text in that mode).
4. When `query_text` is supplied, re-rank with a section-heading signal: a passage whose heading
   is named in the query is promoted (score floor 0.9), partial heading overlap adds a small
   boost. This keeps an exact chapter title like "Database Fundamentals" ahead of a chunk that
   only discusses the topic, without replacing the vector score.
5. Return `RetrievedChunk` records with filename, page, section, content and similarity.

`search_documents` maps any planner-supplied `document_ids` onto the learner's selected
ready documents, accepting real UUIDs, filenames or file stems, and drops unknown values
instead of filtering the corpus to nothing.

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `api/*` | HTTP surface, auth dependency, rate limits, SSE plumbing |
| `services/document_processor` | Validation, extraction, orchestration of indexing |
| `services/chunker` | Cleaning, heading detection, token-aware chunking with overlap |
| `services/embeddings` | Provider selection (fastembed / hash), batched embedding |
| `services/retriever` | Ownership-scoped vector search for both database backends |
| `services/citation_service` | Numbering evidence, detecting/stripping invalid markers |
| `services/llm_service` | Groq client: completions, JSON mode, streaming, friendly errors |
| `agent/router` | Deterministic routes for explicit quiz/summary requests, so phrasing does not flip tool choice |
| `agent/orchestrator` | Bounded planning loop, evidence assembly, answer streaming, persistence |
| `agent/tools/*` | Five tools with typed schemas and validated execution |
| `agent/evidence` | Evidence/document rendering and injection flagging |

## Design trade-offs

- **BackgroundTasks over Celery.** Small files process in seconds; no queue infrastructure to
  operate. A production deployment would move ingestion to a worker with retries.
- **Local embeddings over a second API provider.** Lower cost, no extra key, identical preprocessing
  for documents and queries. Trade-off: an ONNX model download and CPU work during indexing.
- **Vector storage adapts to the server.** PostgreSQL with pgvector uses a native `vector(384)`
  column and HNSW index; PostgreSQL without the extension and SQLite store the same vectors as
  JSON text and score them in Python. One schema, three environments, no separate vector database.
- **SQLite fallback.** PostgreSQL + pgvector is the primary target (Docker Compose). SQLite exists so
  reviewers without Docker can still run the full workflow; it is documented as a fallback.
- **Two LLM calls per chat turn.** One planning call (plus one call per tool) and one streamed answer.
  Predictable citation validation is worth the extra latency.
- **Strict section lookup.** A chapter summary requires a heading match or an explicit page range;
  the alternative (semantic "closest chunks") silently summarises the wrong section.
- **Intent router + model planning.** Unambiguous "create N questions…" and "summarize Chapter 3 /
  page 2" requests are routed in code; everything else is model-decided. A guard also redirects a
  `summarize_chapter` call back to search when the learner asked a question. This keeps routing
  stable across model updates without turning the agent into a fixed decision tree.
- **Stop planning after a successful tool.** A redundant second planner round is skipped once
  evidence is in hand; a failed tool leaves the loop open for a fallback (for example web search).

## Failure behaviour

| Failure | Behaviour |
| --- | --- |
| Corrupt/encrypted/scanned PDF | Document status `failed` with a specific message |
| No retrieval results | Prompt instructs an honest "material does not cover this" answer |
| Weak retrieval | Prompt requires hedging and offers external research |
| Tool exception | Error text returned to the planner; conversation continues |
| LLM auth/rate limit/timeout | Typed `error` SSE event and no saved assistant message |
| Client stops stream | AbortController cancels the request; partial answer is saved |
| Cross-user document id | 404 on every document/search/conversation endpoint |
| Prompt/secret exfiltration request | Fixed refusal from the guardrail; the model is never called |
| Provider rate limit during evaluation | Typed error event; harness counts the case as failed |
