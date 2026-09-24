from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from .config import Settings, get_settings
from .schemas import SearchResult

logger = logging.getLogger(__name__)


def extract_json_object(raw: str) -> dict[str, Any] | None:
    """Parse a JSON object from model output without greedy brace matching."""
    text = (raw or "").strip()
    if not text:
        return None

    candidates: list[str] = []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.append(text)

    decoder = json.JSONDecoder()
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        start = candidate.find("{")
        if start < 0:
            continue
        try:
            parsed, _end = decoder.raw_decode(candidate[start:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def extract_json_array(raw: str) -> list[Any] | None:
    text = (raw or "").strip()
    if not text:
        return None

    candidates: list[str] = []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.append(text)

    decoder = json.JSONDecoder()
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        start = candidate.find("[")
        if start < 0:
            continue
        try:
            parsed, _end = decoder.raw_decode(candidate[start:])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def ai_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if settings.azure_openai_endpoint.strip() and settings.azure_openai_api_key.strip():
        return bool(settings.azure_openai_deployment.strip())
    return bool(settings.openai_api_key.strip())


def _chat_completion(messages: list[dict[str, str]], *, max_tokens: int = 700) -> str | None:
    result = chat_completion_raw(messages, max_tokens=max_tokens)
    if not result:
        return None
    content = result.get("content")
    return str(content).strip() if content else None


def chat_completion_raw(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 700,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    temperature: float = 0.2,
) -> dict[str, Any] | None:
    """Call chat completions; optionally with tools. Returns assistant message fields."""
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
                "temperature": temperature,
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
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

        if tools:
            body["tools"] = tools
            if tool_choice is not None:
                body["tool_choice"] = tool_choice
            else:
                body["tool_choice"] = "auto"

        with httpx.Client(timeout=45.0) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        normalized_calls: list[dict[str, Any]] = []
        for call in tool_calls:
            function = call.get("function") or {}
            normalized_calls.append(
                {
                    "id": call.get("id") or "",
                    "name": function.get("name") or "",
                    "arguments": function.get("arguments") or "{}",
                }
            )
        return {
            "content": message.get("content"),
            "tool_calls": normalized_calls,
            "raw_message": message,
        }
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
    parsed = extract_json_object(raw)
    if not parsed:
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


REWRITE_TONES = {
    "professional": "clear, professional internal corporate tone",
    "concise": "shorter and more concise; cut fluff while keeping facts",
    "friendly": "friendly and approachable while remaining accurate",
    "formal": "formal and precise compliance-friendly tone",
}


def rewrite_article(
    *,
    title: str,
    content: str,
    tone: str = "professional",
    language: str | None = None,
) -> dict[str, str] | None:
    tone_key = (tone or "professional").strip().lower()
    if tone_key not in REWRITE_TONES:
        tone_key = "professional"
    tone_hint = REWRITE_TONES[tone_key]
    lang_hint = ""
    if language:
        lang_hint = f" Keep the output language as {LANG_NAMES.get(language, language)}."
    system = (
        "You rewrite internal Carbonauten company content. "
        "Preserve HTML structure and tags. Improve clarity and tone only — "
        "do not invent facts, numbers, names, or claims. "
        "Return valid JSON with keys title and content only."
    )
    user = (
        f"Rewrite the article with a {tone_hint}.{lang_hint}\n\n"
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
    parsed = extract_json_object(raw)
    if not parsed:
        return None
    next_title = str(parsed.get("title", "")).strip()
    next_content = str(parsed.get("content", "")).strip()
    if not next_title and not next_content:
        return None
    return {
        "title": next_title or title,
        "content": next_content or content,
        "tone": tone_key,
    }


def draft_article_from_notes(
    *,
    notes: str,
    language: str = "de",
    title_hint: str = "",
) -> dict[str, str] | None:
    lang_name = LANG_NAMES.get(language, language)
    cleaned = " ".join((notes or "").split())
    if not cleaned:
        return None
    system = (
        "You draft internal Carbonauten articles from editor notes. "
        "Write factual, neutral content suitable for employees. "
        "Do not invent metrics, customers, or approvals that are not in the notes. "
        "Return valid JSON with keys title and content. "
        "content must be simple HTML using only <p>, <ul>, <ol>, <li>, <strong>, <em>, <h2>, <h3>."
    )
    hint = f"\nPreferred title hint: {title_hint.strip()}" if title_hint.strip() else ""
    user = (
        f"Language: {lang_name}.{hint}\n\n"
        f"NOTES:\n{cleaned[:8000]}\n\n"
        "Produce a short ready-to-edit article draft."
    )
    raw = _chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=2000,
    )
    if not raw:
        return None
    parsed = extract_json_object(raw)
    if not parsed:
        return None
    next_title = str(parsed.get("title", "")).strip()
    next_content = str(parsed.get("content", "")).strip()
    if not next_title and not next_content:
        return None
    if next_content and not next_content.lstrip().startswith("<"):
        next_content = f"<p>{next_content}</p>"
    return {
        "title": next_title or (title_hint.strip() or "Draft"),
        "content": next_content or "<p></p>",
        "language": language,
    }


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
    parsed = extract_json_array(raw)
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()][:3]
