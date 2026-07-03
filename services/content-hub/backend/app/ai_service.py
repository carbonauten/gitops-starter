from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from .config import Settings, get_settings
from .schemas import SearchResult

logger = logging.getLogger(__name__)


def ai_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if settings.azure_openai_endpoint.strip() and settings.azure_openai_api_key.strip():
        return bool(settings.azure_openai_deployment.strip())
    return bool(settings.openai_api_key.strip())


def _chat_completion(messages: list[dict[str, str]], *, max_tokens: int = 700) -> str | None:
    settings = get_settings()
    if not ai_configured(settings):
        return None

    try:
        if settings.azure_openai_endpoint.strip() and settings.azure_openai_api_key.strip():
            url = (
                f"{settings.azure_openai_endpoint.rstrip('/')}"
                f"/openai/deployments/{settings.azure_openai_deployment}"
                f"/chat/completions?api-version=2024-06-01"
            )
            headers = {"api-key": settings.azure_openai_api_key.strip(), "Content-Type": "application/json"}
            body: dict[str, Any] = {
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": max_tokens,
            }
        else:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.openai_api_key.strip()}",
                "Content-Type": "application/json",
            }
            body = {
                "model": settings.openai_model.strip() or "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": max_tokens,
            }

        with httpx.Client(timeout=35.0) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        return str(content).strip() or None
    except Exception:  # noqa: BLE001
        logger.exception("AI chat completion failed")
        return None


def expand_search_query(question: str, language: str = "de") -> str:
    prompt = (
        "Extract the best short keyword search query (max 6 words) from the user question. "
        f"Reply with the query only, in language {language}.\n\n"
        f"Question: {question.strip()}"
    )
    expanded = _chat_completion(
        [
            {"role": "system", "content": "You extract concise search keywords. Reply with plain text only."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=40,
    )
    if not expanded:
        return question.strip()
    return expanded.strip().strip(chr(34)).strip(chr(39))


def generate_search_answer(
    question: str,
    results: list[SearchResult],
    *,
    language: str = "de",
) -> str | None:
    if not results:
        return None

    context_blocks = []
    for index, item in enumerate(results[:8], start=1):
        context_blocks.append(
            f"[{index}] type={item.type} title={item.title}\n"
            f"status={item.status or '-'} snippet={item.snippet or '-'}"
        )
    context = "\n\n".join(context_blocks)
    system = (
        "You are a helpful assistant for an internal content platform (articles, files, certificates). "
        "Answer using ONLY the provided sources. If the answer is not in the sources, say you could not find it. "
        f"Respond in language code {language}. Be concise (max 6 sentences). "
        "Reference source numbers like [1] when relevant."
    )
    user = f"Question: {question.strip()}\n\nSources:\n{context}"
    return _chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=500,
    )


def suggest_follow_up_queries(question: str, results: list[SearchResult], language: str = "de") -> list[str]:
    if not ai_configured():
        titles = [item.title for item in results[:3] if item.title]
        return titles

    titles = ", ".join(item.title for item in results[:5])
    prompt = (
        f"Given question '{question}' and result titles [{titles}], "
        f"suggest 3 short follow-up search queries in {language}. "
        'Return JSON array of strings only, e.g. ["query1","query2"].'
    )
    raw = _chat_completion(
        [
            {"role": "system", "content": "Return valid JSON array of strings only."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=120,
    )
    if not raw:
        return []
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:3]
    except json.JSONDecodeError:
        return []
    return []
