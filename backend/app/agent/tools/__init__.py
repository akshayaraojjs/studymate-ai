"""Tool registry: the five tools the agent can call."""
from __future__ import annotations

from app.agent.tools.base import AgentTool, ToolContext, ToolResult
from app.agent.tools.calculator import calculate_tool
from app.agent.tools.document_search import search_documents_tool
from app.agent.tools.quiz_generator import generate_quiz_tool
from app.agent.tools.summarizer import summarize_chapter_tool
from app.agent.tools.web_search import web_search_tool

ALL_TOOLS: list[AgentTool] = [
    search_documents_tool,
    generate_quiz_tool,
    summarize_chapter_tool,
    web_search_tool,
    calculate_tool,
]

TOOL_MAP: dict[str, AgentTool] = {tool.name: tool for tool in ALL_TOOLS}


def tool_schemas() -> list[dict]:
    return [tool.schema() for tool in ALL_TOOLS]


__all__ = [
    "ALL_TOOLS",
    "TOOL_MAP",
    "AgentTool",
    "ToolContext",
    "ToolResult",
    "tool_schemas",
]
