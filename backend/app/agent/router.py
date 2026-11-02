"""Lightweight intent routing for unambiguous requests.

The model still chooses tools for everything else, but a request that explicitly asks
for a quiz or for a chapter/page summary is routed deterministically. This removes a
well-known failure mode where the planner answers "Summarize Chapter 3" with semantic
search, or treats "Explain X" as a summary request.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SUMMARY_RE = re.compile(r"\b(summar(?:y|ise|ize)|overview|outline|recap)\b", re.IGNORECASE)
QUIZ_RE = re.compile(
    r"\b(quiz|practice\s+(?:questions|test|problems)|test\s+me|questions?)\b", re.IGNORECASE
)
QUIZ_REQUEST_RE = re.compile(
    r"\b(create|make|generate|give|write|build|another|new|quiz me)\b", re.IGNORECASE
)
PAGE_RANGE_RE = re.compile(
    r"(?:pages?|pp?\.)\s*(\d+)\s*(?:-|–|to)\s*(\d+)", re.IGNORECASE
)
PAGE_SINGLE_RE = re.compile(r"(?:page|p\.)\s*(\d+)", re.IGNORECASE)
NUMBER_WORDS = {
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "ten": 10,
}


@dataclass
class Intent:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


def _page_range(text: str) -> tuple[int | None, int | None]:
    match = PAGE_RANGE_RE.search(text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = PAGE_SINGLE_RE.search(text)
    if match:
        page = int(match.group(1))
        return page, page
    return None, None


def _chapter(text: str) -> str | None:
    match = re.search(r"\bchapter\s+(\d{1,2}|[ivxlcdm]{1,6})\b", text, re.IGNORECASE)
    if match:
        return match.group(0)
    match = re.search(
        r"\b(?:the\s+)?chapter\s+(?:on|about|titled|called)\s+([^.,;?]{2,60})",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" \"'")
    return None


def _question_count(text: str) -> int:
    match = re.search(r"\b(\d{1,2})\s+(?:practice\s+)?(?:quiz\s+)?questions?\b", text, re.IGNORECASE)
    if match:
        return max(3, min(8, int(match.group(1))))
    lowered = text.lower()
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b\s+(?:practice\s+)?(?:quiz\s+)?questions?\b", lowered):
            return value
    return 5


def _quiz_topic(text: str) -> str | None:
    match = re.search(
        r"\b(?:quiz|questions?)\s+(?:on|about|for|regarding|covering)\s+(.{2,120})",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" .?!\"'")
    match = re.search(r"\b(?:on|about|regarding|covering)\s+(.{2,120})", text, re.IGNORECASE)
    if match:
        return match.group(1).strip(" .?!\"'")

    topic = re.sub(
        r"^\s*(?:please\s+)?(?:create|make|generate|give|write|build)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    topic = re.sub(
        r"\b(?:\d{1,2}|three|four|five|six|seven|eight|ten)?\s*(?:practice\s+)?(?:quiz\s+)?questions?\b",
        "",
        topic,
        flags=re.IGNORECASE,
    )
    topic = re.sub(r"^\s*(?:on|about|regarding|covering)\s+", "", topic, flags=re.IGNORECASE)
    topic = topic.strip(" .?!\"'")
    return topic if len(topic) >= 3 else None


def detect_intent(message: str) -> Intent | None:
    """Return a deterministic tool route for explicit quiz/summary requests."""
    text = (message or "").strip()
    if not text:
        return None

    if SUMMARY_RE.search(text):
        page_start, page_end = _page_range(text)
        chapter = _chapter(text)
        if chapter or page_start is not None:
            arguments: dict[str, Any] = {"page_start": page_start, "page_end": page_end}
            if chapter:
                arguments["chapter"] = chapter
            return Intent(tool="summarize_chapter", arguments=arguments)

    if QUIZ_RE.search(text) and QUIZ_REQUEST_RE.search(text):
        topic = _quiz_topic(text)
        if topic:
            return Intent(
                tool="generate_quiz",
                arguments={"topic": topic, "num_questions": _question_count(text)},
            )
    return None
