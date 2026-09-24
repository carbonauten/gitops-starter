"""Microsoft 365 admin intents for Ask Carbonauten (IT master only).

Prefers LLM tool/function calling when AI is configured; falls back to regex intents.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import HTTPException

from .ai_service import LANG_NAMES, ai_configured, chat_completion_raw
from .graph_directory_service import (
    assign_license,
    create_directory_user,
    find_user_in_list,
    list_available_licenses,
    list_directory_users,
    remove_license,
    reset_directory_password,
    set_directory_user_enabled,
)

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

LIST_HINTS = (
    "m365",
    "microsoft 365",
    "microsoft365",
    "entra",
    "azure ad",
    "verzeichnis",
    "directory",
    "konten",
    "accounts",
    "benutzer",
    "user",
    "mitarbeiter",
    "lizenz",
    "license",
    "租户",
    "账号",
    "许可证",
)
LIST_VERBS = ("liste", "list", "zeige", "show", "welche", "which", "übersicht", "overview", "alle", "all", "有哪些")
DISABLE_VERBS = ("sperre", "deaktiv", "disable", "block", "abschalten", "停用", "禁用", "锁定")
ENABLE_VERBS = ("aktivier", "entsperr", "enable", "unlock", "einschalten", "启用", "解锁")
CREATE_VERBS = (
    "lege ",
    "anlegen",
    "erstell",
    "create user",
    "neuen benutzer",
    "new user",
    "neuen user",
    "lege user",
    "新建",
    "创建用户",
)
RESET_VERBS = ("passwort", "password", "reset", "zurücksetzen", "reset password", "密码")
LICENSE_VERBS = ("lizenz", "license", "zuweisen", "assign", "entfernen", "remove", "entzieh")

M365_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_m365_users",
            "description": "List or search Microsoft 365 / Entra directory users in the carbonauten tenant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional name, UPN, department, or job title filter.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_m365_user",
            "description": "Create a new Microsoft 365 user and return a temporary password.",
            "parameters": {
                "type": "object",
                "properties": {
                    "display_name": {"type": "string"},
                    "user_principal_name": {
                        "type": "string",
                        "description": "UPN / email, e.g. anna@carbonauten.com",
                    },
                    "job_title": {"type": "string"},
                    "department": {"type": "string"},
                },
                "required": ["display_name", "user_principal_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_m365_user_enabled",
            "description": "Enable or disable sign-in for a Microsoft 365 user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "UPN, email, display name, or user id.",
                    },
                    "account_enabled": {"type": "boolean"},
                },
                "required": ["user", "account_enabled"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_m365_user_password",
            "description": "Reset a Microsoft 365 user password and return a temporary password.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "UPN, email, display name, or user id.",
                    }
                },
                "required": ["user"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_m365_licenses",
            "description": "List available Microsoft 365 license SKUs with free/used seats.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_m365_license",
            "description": "Assign a Microsoft 365 license SKU to a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user": {"type": "string"},
                    "sku": {
                        "type": "string",
                        "description": "SKU id or license display name.",
                    },
                },
                "required": ["user", "sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_m365_license",
            "description": "Remove a Microsoft 365 license SKU from a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user": {"type": "string"},
                    "sku": {
                        "type": "string",
                        "description": "SKU id or license display name.",
                    },
                },
                "required": ["user", "sku"],
            },
        },
    },
]


def looks_like_m365_admin_question(question: str) -> bool:
    text = (question or "").lower()
    if not text:
        return False
    mentions_directory = any(hint in text for hint in LIST_HINTS)
    mentions_action = any(
        verb in text for verb in (*DISABLE_VERBS, *ENABLE_VERBS, *CREATE_VERBS, *RESET_VERBS, *LICENSE_VERBS)
    )
    return mentions_directory or (
        mentions_action and ("@" in text or "user" in text or "benutzer" in text or "konto" in text or "lizenz" in text)
    )


def parse_directory_intent(question: str) -> dict[str, str]:
    """Regex fallback when AI/tool calling is unavailable."""
    text = (question or "").strip()
    lower = text.lower()
    email_match = EMAIL_RE.search(text)
    email = email_match.group(0) if email_match else ""
    if any(verb in lower for verb in CREATE_VERBS):
        name = ""
        quoted = re.search(r"[\"“„']([^\"”']+)[\"”']", text)
        if quoted:
            name = quoted.group(1).strip()
        elif email:
            local = email.split("@", 1)[0].replace(".", " ").replace("_", " ")
            name = local.title()
        return {"action": "create", "email": email, "name": name, "query": "", "sku": ""}
    if any(verb in lower for verb in RESET_VERBS) and (email or "passwort" in lower or "password" in lower):
        return {"action": "reset_password", "email": email, "name": "", "query": email, "sku": ""}
    if any(verb in lower for verb in DISABLE_VERBS):
        return {"action": "disable", "email": email, "name": "", "query": email, "sku": ""}
    if any(verb in lower for verb in ENABLE_VERBS):
        return {"action": "enable", "email": email, "name": "", "query": email, "sku": ""}
    license_mutate = any(verb in lower for verb in ("zuweisen", "assign", "entfernen", "remove", "entzieh"))
    if license_mutate and any(token in lower for token in ("lizenz", "license", "sku")):
        action = "remove_license" if any(v in lower for v in ("entfernen", "remove", "entzieh")) else "assign_license"
        return {"action": action, "email": email, "name": "", "query": email, "sku": ""}
    if any(token in lower for token in ("lizenz", "license", "sku")):
        return {"action": "list_licenses", "email": email, "name": "", "query": "", "sku": ""}
    query = email
    if not query:
        leftover = re.sub(
            r"(m365|microsoft 365|entra|azure ad|verzeichnis|directory|benutzer|user|mitarbeiter|konten|accounts|"
            r"liste|list|zeige|show|welche|which|übersicht|overview|alle|all|gibt|es|ist|sind|im|tenant|"
            r"租户|账号|许可证)",
            " ",
            lower,
        )
        leftover = re.sub(r"[?!.,]", " ", leftover)
        leftover = re.sub(r"\s+", " ", leftover).strip()
        if leftover and leftover not in {"die", "der", "das", "the", "a"}:
            query = leftover
    return {"action": "list", "email": email, "name": "", "query": query, "sku": ""}


def _format_user_line(row: dict[str, Any]) -> str:
    status = "aktiv" if row.get("account_enabled") else "gesperrt"
    licenses = ", ".join(row.get("licenses") or []) or "keine Lizenz"
    title = row.get("job_title") or "-"
    return (
        f"- {row.get('display_name')} <{row.get('user_principal_name')}> · "
        f"{title} · {status} · {licenses}"
    )


def build_directory_answer(
    *,
    language: str,
    action: str,
    users: list[dict[str, Any]],
    target: dict[str, Any] | None = None,
    temporary_password: str = "",
    licenses: list[dict[str, Any]] | None = None,
    error: str = "",
) -> str:
    lang = language or "de"
    if error:
        if lang.startswith("zh"):
            return f"M365-操作失败：{error}"
        if lang.startswith("en"):
            return f"M365 action failed: {error}"
        return f"M365-Aktion fehlgeschlagen: {error}"

    if action == "list":
        if not users:
            if lang.startswith("zh"):
                return "未找到 Microsoft 365 用户。"
            if lang.startswith("en"):
                return "No Microsoft 365 users matched that query."
            return "Keine Microsoft-365-Benutzer gefunden."
        lines = "\n".join(_format_user_line(row) for row in users[:40])
        if lang.startswith("zh"):
            return f"租户中有 {len(users)} 个 Microsoft 365 用户：\n{lines}"
        if lang.startswith("en"):
            return f"{len(users)} Microsoft 365 users in the tenant:\n{lines}"
        return f"{len(users)} Microsoft-365-Benutzer im Tenant:\n{lines}"

    if action == "list_licenses":
        rows = licenses or []
        if not rows:
            if lang.startswith("zh"):
                return "未找到可用许可证。"
            if lang.startswith("en"):
                return "No licenses found."
            return "Keine Lizenzen gefunden."
        lines = "\n".join(
            f"- {row.get('name')} · frei {row.get('available')} / {row.get('total')} (SKU {row.get('sku_id')})"
            for row in rows[:40]
        )
        if lang.startswith("zh"):
            return f"可用许可证：\n{lines}"
        if lang.startswith("en"):
            return f"Available licenses:\n{lines}"
        return f"Verfügbare Lizenzen:\n{lines}"

    name = (target or {}).get("display_name") or ""
    upn = (target or {}).get("user_principal_name") or ""
    if action == "disable":
        if lang.startswith("zh"):
            return f"已停用 {name} ({upn}) 的登录。"
        if lang.startswith("en"):
            return f"Sign-in disabled for {name} ({upn})."
        return f"Anmeldung für {name} ({upn}) ist jetzt gesperrt."
    if action == "enable":
        if lang.startswith("zh"):
            return f"已启用 {name} ({upn}) 的登录。"
        if lang.startswith("en"):
            return f"Sign-in enabled for {name} ({upn})."
        return f"Anmeldung für {name} ({upn}) ist wieder aktiv."
    if action == "create":
        if lang.startswith("zh"):
            return f"已创建用户 {name} ({upn})。临时密码：{temporary_password}"
        if lang.startswith("en"):
            return (
                f"Created user {name} ({upn}). Temporary password: {temporary_password}. "
                "They must change it at next sign-in."
            )
        return (
            f"Benutzer {name} ({upn}) wurde angelegt. "
            f"Temporäres Passwort: {temporary_password}. Beim nächsten Login muss es geändert werden."
        )
    if action == "reset_password":
        if lang.startswith("zh"):
            return f"已重置 {name} ({upn}) 的密码。临时密码：{temporary_password}"
        if lang.startswith("en"):
            return f"Password reset for {name} ({upn}). Temporary password: {temporary_password}"
        return f"Passwort für {name} ({upn}) zurückgesetzt. Temporäres Passwort: {temporary_password}"
    if action == "assign_license":
        if lang.startswith("zh"):
            return f"已为 {name} ({upn}) 分配许可证。"
        if lang.startswith("en"):
            return f"License assigned to {name} ({upn})."
        return f"Lizenz für {name} ({upn}) zugewiesen."
    if action == "remove_license":
        if lang.startswith("zh"):
            return f"已从 {name} ({upn}) 移除许可证。"
        if lang.startswith("en"):
            return f"License removed from {name} ({upn})."
        return f"Lizenz von {name} ({upn}) entfernt."
    return ""


async def _resolve_user(needle: str) -> dict[str, Any]:
    needle = (needle or "").strip()
    if not needle:
        raise HTTPException(status_code=404, detail="not_found")
    users = await list_directory_users(query=needle)
    target = find_user_in_list(users, needle)
    if not target:
        target = find_user_in_list(await list_directory_users(), needle)
    if not target:
        raise HTTPException(status_code=404, detail="not_found")
    return target


async def _resolve_sku(sku: str) -> str:
    value = (sku or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="validation_error")
    licenses = await list_available_licenses()
    for row in licenses:
        if row.get("sku_id") == value:
            return value
    lowered = value.lower()
    for row in licenses:
        name = str(row.get("name") or "").lower()
        if lowered == name or lowered in name:
            return str(row["sku_id"])
    raise HTTPException(status_code=404, detail="license_not_found")


async def _execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "list_m365_users":
        users = await list_directory_users(query=str(arguments.get("query") or ""))
        return {"action": "list", "users": users, "user": None, "temporary_password": "", "licenses": []}

    if name == "create_m365_user":
        upn = str(arguments.get("user_principal_name") or "").strip()
        display_name = str(arguments.get("display_name") or "").strip() or (upn.split("@", 1)[0] if upn else "")
        if not upn:
            raise HTTPException(status_code=400, detail="validation_error")
        target, temporary_password = await create_directory_user(
            display_name=display_name,
            user_principal_name=upn,
            job_title=str(arguments.get("job_title") or ""),
            department=str(arguments.get("department") or ""),
        )
        return {
            "action": "create",
            "users": [target],
            "user": target,
            "temporary_password": temporary_password,
            "licenses": [],
        }

    if name == "set_m365_user_enabled":
        target = await _resolve_user(str(arguments.get("user") or ""))
        enabled = bool(arguments.get("account_enabled"))
        target = await set_directory_user_enabled(target["id"], enabled)
        return {
            "action": "enable" if enabled else "disable",
            "users": [target],
            "user": target,
            "temporary_password": "",
            "licenses": [],
        }

    if name == "reset_m365_user_password":
        target = await _resolve_user(str(arguments.get("user") or ""))
        target, temporary_password = await reset_directory_password(target["id"])
        return {
            "action": "reset_password",
            "users": [target],
            "user": target,
            "temporary_password": temporary_password,
            "licenses": [],
        }

    if name == "list_m365_licenses":
        licenses = await list_available_licenses()
        return {"action": "list_licenses", "users": [], "user": None, "temporary_password": "", "licenses": licenses}

    if name == "assign_m365_license":
        target = await _resolve_user(str(arguments.get("user") or ""))
        sku_id = await _resolve_sku(str(arguments.get("sku") or ""))
        target = await assign_license(target["id"], sku_id)
        return {
            "action": "assign_license",
            "users": [target],
            "user": target,
            "temporary_password": "",
            "licenses": [],
        }

    if name == "remove_m365_license":
        target = await _resolve_user(str(arguments.get("user") or ""))
        sku_id = await _resolve_sku(str(arguments.get("sku") or ""))
        target = await remove_license(target["id"], sku_id)
        return {
            "action": "remove_license",
            "users": [target],
            "user": target,
            "temporary_password": "",
            "licenses": [],
        }

    raise HTTPException(status_code=400, detail="unknown_tool")


def _parse_tool_arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _handle_with_function_calling(question: str, *, language: str) -> dict[str, Any] | None:
    lang_name = LANG_NAMES.get(language, language)
    system = (
        "You are Ask Carbonauten for carbonauten GmbH IT masters. "
        "Use the provided Microsoft 365 directory tools to fulfill admin requests. "
        "Prefer calling a tool over guessing. Never invent users or licenses. "
        f"After tools run, the system will format the final reply in {lang_name}."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": question.strip()},
    ]
    first = chat_completion_raw(
        messages,
        max_tokens=600,
        tools=M365_TOOLS,
        tool_choice="auto",
        temperature=0.0,
    )
    if not first:
        return None

    tool_calls = first.get("tool_calls") or []
    if not tool_calls:
        content = str(first.get("content") or "").strip()
        if not content:
            return None
        return {
            "action": "chat",
            "answer": content,
            "users": [],
            "temporary_password": "",
            "user": None,
            "licenses": [],
            "mode": "function_calling",
        }

    # Execute the first actionable tool call (directory mutations are single-step for safety).
    call = tool_calls[0]
    tool_name = str(call.get("name") or "")
    args = _parse_tool_arguments(str(call.get("arguments") or "{}"))
    try:
        executed = await _execute_tool(tool_name, args)
    except HTTPException as exc:
        answer = build_directory_answer(
            language=language,
            action=tool_name or "chat",
            users=[],
            error=str(exc.detail),
        )
        return {
            "action": tool_name or "chat",
            "answer": answer,
            "users": [],
            "temporary_password": "",
            "user": None,
            "licenses": [],
            "mode": "function_calling",
        }

    answer = build_directory_answer(
        language=language,
        action=executed["action"],
        users=executed.get("users") or [],
        target=executed.get("user"),
        temporary_password=executed.get("temporary_password") or "",
        licenses=executed.get("licenses") or [],
    )
    return {
        "action": executed["action"],
        "answer": answer,
        "users": executed.get("users") or [],
        "temporary_password": executed.get("temporary_password") or "",
        "user": executed.get("user"),
        "licenses": executed.get("licenses") or [],
        "mode": "function_calling",
    }


async def _handle_with_regex(question: str, *, language: str) -> dict[str, Any]:
    intent = parse_directory_intent(question)
    action = intent["action"]
    users = await list_directory_users(query=intent.get("query") or "")
    target = None
    temporary_password = ""
    licenses: list[dict[str, Any]] = []
    try:
        if action in {"disable", "enable", "reset_password"}:
            needle = intent.get("email") or intent.get("query") or ""
            target = await _resolve_user(needle)
            if action == "disable":
                target = await set_directory_user_enabled(target["id"], False)
            elif action == "enable":
                target = await set_directory_user_enabled(target["id"], True)
            else:
                target, temporary_password = await reset_directory_password(target["id"])
        elif action == "create":
            if not intent.get("email"):
                raise HTTPException(status_code=400, detail="validation_error")
            target, temporary_password = await create_directory_user(
                display_name=intent.get("name") or intent["email"].split("@", 1)[0],
                user_principal_name=intent["email"],
            )
            users = [target]
        elif action == "list_licenses":
            licenses = await list_available_licenses()
        elif action in {"assign_license", "remove_license"}:
            needle = intent.get("email") or intent.get("query") or ""
            target = await _resolve_user(needle)
            sku_id = await _resolve_sku(intent.get("sku") or "")
            if action == "assign_license":
                target = await assign_license(target["id"], sku_id)
            else:
                target = await remove_license(target["id"], sku_id)
        else:
            target = None
    except HTTPException as exc:
        answer = build_directory_answer(
            language=language,
            action=action,
            users=[],
            error=str(exc.detail),
        )
        return {
            "action": action,
            "answer": answer,
            "users": [],
            "temporary_password": "",
            "user": None,
            "licenses": [],
            "mode": "regex",
        }

    answer = build_directory_answer(
        language=language,
        action=action,
        users=users if action == "list" else ([target] if target else []),
        target=target,
        temporary_password=temporary_password,
        licenses=licenses,
    )
    return {
        "action": action,
        "answer": answer,
        "users": users if action == "list" else ([target] if target else []),
        "temporary_password": temporary_password,
        "user": target,
        "licenses": licenses,
        "mode": "regex",
    }


async def handle_directory_question(question: str, *, language: str = "de") -> dict[str, Any]:
    if ai_configured():
        try:
            via_tools = await _handle_with_function_calling(question, language=language)
            if via_tools:
                return via_tools
        except Exception:  # noqa: BLE001
            logger.exception("M365 function calling failed; falling back to regex intents")
    return await _handle_with_regex(question, language=language)
