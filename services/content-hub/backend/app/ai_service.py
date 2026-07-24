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


LANG_NAMES = {
    "de": "German",
    "en": "English",
    "zh-CN": "Simplified Chinese",
    "zh": "Simplified Chinese",
}


def generate_search_answer(
    question: str,
    results: list[SearchResult],
    *,
    language: str = "de",
    enriched_context: list[str] | None = None,
) -> str | None:
    if not results and not enriched_context:
        return None

    context_blocks = list(enriched_context or [])
    if not context_blocks:
        for index, item in enumerate(results[:8], start=1):
            context_blocks.append(
                f"[{index}] type={item.type} title={item.title}\n"
                f"status={item.status or '-'} snippet={item.snippet or '-'}"
            )
    context = "\n\n".join(context_blocks)
    lang_name = LANG_NAMES.get(language, language)
    system = (
        "You are Ask Carbonauten, the internal knowledge assistant for Carbonauten. "
        "Answer using ONLY the provided company sources (articles, files, certificates). "
        "Never invent facts outside the sources. If the answer is not in the sources, say so clearly. "
        f"Respond in {lang_name}. Be concise (max 6 sentences). "
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


def translate_article(
    *,
    title: str,
    content: str,
    target_language: str,
    source_language: str | None = None,
) -> dict[str, str] | None:
    target = LANG_NAMES.get(target_language, target_language)
    source_hint = ""
    if source_language:
        source_hint = f" The source language is {LANG_NAMES.get(source_language, source_language)}."
    system = (
        "You translate internal company content for Carbonauten. "
        "Preserve HTML structure and tags exactly. Translate visible text only. "
        "Return valid JSON with keys title and content only."
    )
    user = (
        f"Translate the following article into {target}.{source_hint}\n\n"
        f"TITLE:\n{title}\n\nCONTENT_HTML:\n{content}"
    )
    raw = _chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=2500,
    )
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    translated_title = str(parsed.get("title", "")).strip()
    translated_content = str(parsed.get("content", "")).strip()
    if not translated_title and not translated_content:
        return None
    return {
        "title": translated_title or title,
        "content": translated_content or content,
        "target_language": target_language,
    }


def summarize_article(
    *,
    title: str,
    content: str,
    language: str = "de",
) -> str | None:
    lang_name = LANG_NAMES.get(language, language)
    plain = re.sub(r"<[^>]+>", " ", content or "")
    plain = " ".join(plain.split())
    system = (
        "You write short internal summaries for Carbonauten employees. "
        f"Respond in {lang_name}. Use 3-5 bullet points. No preamble."
    )
    user = f"Title: {title}\n\nContent:\n{plain[:6000]}"
    return _chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=400,
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
