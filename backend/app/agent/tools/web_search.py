"""web_search tool.

Uses DuckDuckGo's HTML endpoint by default (no API key) or Tavily when configured.
Only the configured provider is contacted; the model cannot choose URLs to fetch.
Results are treated as untrusted external evidence and returned with their URLs.
"""
from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.agent.tools.base import AgentTool, ToolContext, ToolResult
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
MAX_RESULTS = 5

_RESULT_LINK_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL
)
_SNIPPET_RE = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")


class WebSearchError(RuntimeError):
    pass


def _clean_html(value: str) -> str:
    return html.unescape(_TAG_RE.sub("", value)).strip()


def _unwrap_redirect(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return url


async def _duckduckgo_search(query: str) -> list[dict[str, str]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(
        timeout=settings.web_search_timeout_seconds, follow_redirects=True, headers=headers
    ) as client:
        response = await client.post("https://html.duckduckgo.com/html/", data={"q": query})
    if response.status_code != 200:
        raise WebSearchError(f"Search provider returned HTTP {response.status_code}.")

    links = _RESULT_LINK_RE.findall(response.text)
    snippets = _SNIPPET_RE.findall(response.text)
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, (href, title_html) in enumerate(links):
        url = _unwrap_redirect(href)
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        snippet = _clean_html(snippets[index]) if index < len(snippets) else ""
        results.append({"title": _clean_html(title_html), "url": url, "snippet": snippet})
        if len(results) >= MAX_RESULTS:
            break
    return results


async def _tavily_search(query: str) -> list[dict[str, str]]:
    if not settings.web_search_api_key:
        raise WebSearchError("WEB_SEARCH_API_KEY is not configured for Tavily.")
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.web_search_api_key,
                "query": query,
                "max_results": MAX_RESULTS,
                "search_depth": "basic",
            },
        )
    if response.status_code != 200:
        raise WebSearchError(f"Tavily returned HTTP {response.status_code}.")
    payload = response.json()
    return [
        {
            "title": str(item.get("title", ""))[:200],
            "url": str(item.get("url", "")),
            "snippet": str(item.get("content", ""))[:400],
        }
        for item in payload.get("results", [])[:MAX_RESULTS]
    ]


async def web_search(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    query = str(args.get("query") or "").strip()[:300]
    if not query:
        return ToolResult(content="Error: 'query' is required.", ok=False, summary="Web search failed")

    try:
        if settings.web_search_provider.lower() == "tavily":
            results = await _tavily_search(query)
        else:
            results = await _duckduckgo_search(query)
    except (WebSearchError, httpx.HTTPError) as exc:
        logger.warning("Web search failed: %s", exc)
        return ToolResult(
            content=(
                "Web search is unavailable right now. Answer from the learner's material or "
                "state that you could not verify current information."
            ),
            ok=False,
            summary="Web search unavailable",
        )

    if not results:
        return ToolResult(content="No web results found.", ok=False, summary="No web results")

    seen_urls = {source["url"] for source in ctx.external_sources}
    for result in results:
        if result["url"] not in seen_urls:
            ctx.external_sources.append(result)
            seen_urls.add(result["url"])

    lines = [
        f"- {result['title']} — {result['url']}\n  {result['snippet']}" for result in results
    ]
    return ToolResult(
        content=(
            "External web results (untrusted; not the learner's material). Cite them as "
            "markdown links with their URLs:\n" + "\n".join(lines)
        ),
        ok=True,
        summary=f"Found {len(results)} web result{'s' if len(results) != 1 else ''}",
    )


web_search_tool = AgentTool(
    name="web_search",
    description=(
        "Search the public web for current or external information, or as a fallback when the "
        "uploaded material does not cover a topic. Returns titles, URLs and snippets. Use only "
        "when freshness or outside context is genuinely needed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query, 2-12 words."}
        },
        "required": ["query"],
    },
    handler=web_search,
    activity="Searching the web",
)
