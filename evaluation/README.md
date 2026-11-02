# Evaluation

A small, reproducible evaluation of the agent against real uploaded material.

```
evaluation/
├── questions.json                 # 21 cases with expected tools/keywords/pages
├── make_sample_pdf.py             # builds the 4-chapter sample PDF
├── sample_documents/
│   ├── database-notes.pdf         # generated sample, 4 pages / 4 chapters
│   ├── database-notes.txt         # same material as plain text
│   └── prompt-injection.txt       # adversarial document
└── run_evaluation.py              # harness
```

## Run it

1. Start the backend with a valid `GROQ_API_KEY`.
2. From the repository root:

```bash
backend/.venv/Scripts/python evaluation/run_evaluation.py          # all 21 cases
backend/.venv/Scripts/python evaluation/run_evaluation.py --limit 5  # smoke run
```

The harness registers a throwaway account, uploads the sample PDF plus the adversarial document,
streams each question through `/api/v1/chat/stream`, and writes `evaluation/results.json`.

## What is measured

| Check | Meaning |
| --- | --- |
| `tool_selection` | The expected tool was used (or no tool, when none is required) |
| `keyword_match` | At least one reference keyword appears in the answer |
| `citation_page` / `has_citations` | The answer cites a retrieved passage on the expected page |
| `abstention` | For unanswerable questions, the answer declines instead of inventing content |
| `refusal` | Injection/environment probes are refused without leaking prompt or secrets |
| `redirect` | Off-topic requests are redirected to study help |
| `quiz_schema` | A quiz event contains 5 questions, 4 options, a valid index and an explanation |
| `latency_ms` | Median time to first streamed token and median total response time |

Metrics are printed as pass/total so you can judge a small sample honestly. Do not quote an
accuracy figure that was not produced by an actual run.

`results.json` is generated output and is git-ignored. On a free Groq key the quota can run out
mid-suite; those turns surface as `error: The AI provider rate limit was reached`, are counted as
failures, and should be re-run rather than interpreted as model errors.

## Adding cases

Append to `questions.json`:

```json
{
  "id": "Q21",
  "question": "…",
  "expected_tools": ["search_documents"],
  "keywords": ["…"],
  "expected_pages": [2],
  "expect_abstain": false,
  "expect_refusal": false,
  "expect_redirect": false,
  "requires_quiz": false
}
```

`expected_tools: []` means the case expects a direct answer with no tool call. Only include
`keywords` that the source material genuinely supports.
