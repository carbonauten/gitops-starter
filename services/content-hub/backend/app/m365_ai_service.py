"""Rule-based Microsoft 365 admin intents for Ask Carbonauten (IT master only)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from .graph_directory_service import (
    create_directory_user,
    find_user_in_list,
    list_directory_users,
    reset_directory_password,
    set_directory_user_enabled,
)

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
    "租户",
    "账号",
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


def looks_like_m365_admin_question(question: str) -> bool:
    text = (question or "").lower()
    if not text:
        return False
    mentions_directory = any(hint in text for hint in LIST_HINTS)
    mentions_action = any(verb in text for verb in (*DISABLE_VERBS, *ENABLE_VERBS, *CREATE_VERBS, *RESET_VERBS))
    return mentions_directory or (mentions_action and ("@" in text or "user" in text or "benutzer" in text or "konto" in text))


def parse_directory_intent(question: str) -> dict[str, str]:
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
        return {"action": "create", "email": email, "name": name, "query": ""}
    if any(verb in lower for verb in RESET_VERBS) and (email or "passwort" in lower or "password" in lower):
        return {"action": "reset_password", "email": email, "name": "", "query": email}
    if any(verb in lower for verb in DISABLE_VERBS):
        return {"action": "disable", "email": email, "name": "", "query": email}
    if any(verb in lower for verb in ENABLE_VERBS):
        return {"action": "enable", "email": email, "name": "", "query": email}
    query = email
    if not query:
        leftover = re.sub(
            r"(m365|microsoft 365|entra|azure ad|verzeichnis|directory|benutzer|user|mitarbeiter|konten|accounts|"
            r"liste|list|zeige|show|welche|which|übersicht|overview|alle|all|gibt|es|ist|sind|im|tenant|租户|账号)",
            " ",
            lower,
        )
        leftover = re.sub(r"[?!.,]", " ", leftover)
        leftover = re.sub(r"\s+", " ", leftover).strip()
        if leftover and leftover not in {"die", "der", "das", "the", "a"}:
            query = leftover
    return {"action": "list", "email": email, "name": "", "query": query}


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
        extra = f" Temporary password: {temporary_password}" if temporary_password else ""
        if lang.startswith("zh"):
            return f"已创建用户 {name} ({upn})。临时密码：{temporary_password}"
        if lang.startswith("en"):
            return f"Created user {name} ({upn}).{extra} They must change it at next sign-in."
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
    return ""


async def handle_directory_question(question: str, *, language: str = "de") -> dict[str, Any]:
    intent = parse_directory_intent(question)
    action = intent["action"]
    users = await list_directory_users(query=intent.get("query") or "")
    target = None
    temporary_password = ""
    try:
        if action in {"disable", "enable", "reset_password"}:
            needle = intent.get("email") or intent.get("query") or ""
            target = find_user_in_list(users if intent.get("query") else await list_directory_users(), needle)
            if not target and needle:
                target = find_user_in_list(await list_directory_users(), needle)
            if not target:
                raise HTTPException(status_code=404, detail="not_found")
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
        }

    answer = build_directory_answer(
        language=language,
        action=action,
        users=users if action == "list" else ([target] if target else []),
        target=target,
        temporary_password=temporary_password,
    )
    return {
        "action": action,
        "answer": answer,
        "users": users if action == "list" else ([target] if target else []),
        "temporary_password": temporary_password,
        "user": target,
    }
