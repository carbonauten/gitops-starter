from __future__ import annotations

ARTICLE_TEMPLATES = {
    "weekly_report": {
        "title": {
            "de": "Wochenbericht",
            "en": "Weekly Report",
            "zh-CN": "周报",
        },
        "content": {
            "de": "<h2>Zusammenfassung</h2><p></p><h2>Erledigt</h2><ul><li></li></ul><h2>Geplant</h2><ul><li></li></ul>",
            "en": "<h2>Summary</h2><p></p><h2>Completed</h2><ul><li></li></ul><h2>Planned</h2><ul><li></li></ul>",
            "zh-CN": "<h2>总结</h2><p></p><h2>已完成</h2><ul><li></li></ul><h2>计划</h2><ul><li></li></ul>",
        },
    },
    "announcement": {
        "title": {
            "de": "Ankündigung",
            "en": "Announcement",
            "zh-CN": "公告",
        },
        "content": {
            "de": "<h2>Wichtige Mitteilung</h2><p></p><h2>Details</h2><p></p>",
            "en": "<h2>Important Notice</h2><p></p><h2>Details</h2><p></p>",
            "zh-CN": "<h2>重要通知</h2><p></p><h2>详情</h2><p></p>",
        },
    },
    "protocol": {
        "title": {
            "de": "Protokoll",
            "en": "Meeting Protocol",
            "zh-CN": "会议记录",
        },
        "content": {
            "de": "<h2>Teilnehmer</h2><p></p><h2>Tagesordnung</h2><ol><li></li></ol><h2>Beschlüsse</h2><ul><li></li></ul>",
            "en": "<h2>Attendees</h2><p></p><h2>Agenda</h2><ol><li></li></ol><h2>Decisions</h2><ul><li></li></ul>",
            "zh-CN": "<h2>参会人员</h2><p></p><h2>议程</h2><ol><li></li></ol><h2>决议</h2><ul><li></li></ul>",
        },
    },
}


def get_template(template_id: str, language: str) -> dict[str, str] | None:
    template = ARTICLE_TEMPLATES.get(template_id)
    if not template:
        return None
    lang = language if language in template["title"] else "en"
    return {
        "id": template_id,
        "title": template["title"][lang],
        "content": template["content"][lang],
    }


def list_templates(language: str) -> list[dict[str, str]]:
    items = []
    for template_id in ARTICLE_TEMPLATES:
        item = get_template(template_id, language)
        if item:
            items.append(item)
    return items
