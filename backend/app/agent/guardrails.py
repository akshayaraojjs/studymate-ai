"""Backend guardrails for prompt-injection and secret-exfiltration requests.

Prompt instructions alone cannot guarantee refusal, so requests that explicitly ask to
override the assistant's rules or disclose prompts, credentials or environment values
never reach the model. They get a fixed, safe response instead.
"""
from __future__ import annotations

import re

INJECTION_PATTERNS = [
    re.compile(
        r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+instructions", re.IGNORECASE
    ),
    re.compile(
        r"disregard\s+(the\s+|all\s+)?(system|previous|above|prior)\s+(prompt|instructions|rules)",
        re.IGNORECASE,
    ),
    re.compile(r"ignore\s+(your|the)\s+(rules|guidelines|instructions|guardrails)", re.IGNORECASE),
    re.compile(
        r"(reveal|show|print|repeat|dump|output|tell\s+me)\s+.{0,40}"
        r"(system\s+prompt|your\s+instructions|your\s+rules|hidden\s+prompt)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(reveal|show|print|dump|output|list)\s+.{0,40}"
        r"(environment\s+variables|env\s+vars|\.env|api\s*[_\- ]?key|secret\s*[_\- ]?key|database\s*url)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(jailbreak|developer\s+mode|dan\s+mode|unrestricted\s+mode)\b", re.IGNORECASE),
    re.compile(r"act\s+as\s+(an?\s+)?(unrestricted|unfiltered|uncensored)", re.IGNORECASE),
    re.compile(r"\bprompt\s+injection\b.*\b(example|try|execute|run)\b", re.IGNORECASE),
]

REFUSAL_MESSAGE = (
    "I can't reveal system prompts, credentials or server configuration, and I can't override "
    "my instructions — including instructions that arrive inside an uploaded document. "
    "I can help you study your material: ask a question about it, or ask for a quiz or a "
    "chapter summary."
)


def detect_unsafe_request(message: str) -> str | None:
    """Return the fixed refusal text when a message attempts prompt/secret exfiltration."""
    text = (message or "").strip()
    if not text:
        return None
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return REFUSAL_MESSAGE
    return None
