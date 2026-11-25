from __future__ import annotations

import logging
import uuid
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

# Minimal CalDAV client (RFC 4791 + RFC 5397 principal discovery), built on
# plain httpx + stdlib XML rather than the `caldav` PyPI package - this only
# ever needs "find my default calendar, then PUT one event into it", which
# doesn't warrant a new dependency. Generic by design (not mailbox.org-
# specific) so any standards-compliant CalDAV server can reuse it.

_NS = {
    "d": "DAV:",
    "c": "urn:ietf:params:xml:ns:caldav",
}


def _propfind(url: str, *, auth: tuple[str, str], body: str, depth: str = "0") -> ElementTree.Element | None:
    try:
        response = httpx.request(
            "PROPFIND",
            url,
            auth=auth,
            headers={"Content-Type": "application/xml; charset=utf-8", "Depth": depth},
            content=body,
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("CalDAV PROPFIND failed for %s: %s", url, exc)
        return None
    if response.status_code not in (207, 200):
        logger.warning("CalDAV PROPFIND unexpected status %s for %s", response.status_code, url)
        return None
    try:
        return ElementTree.fromstring(response.text)
    except ElementTree.ParseError:
        return None


def _href_text(root: ElementTree.Element, xpath: str) -> str | None:
    el = root.find(xpath, _NS)
    return el.text.strip() if el is not None and el.text else None


def _absolute(base_url: str, href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    from urllib.parse import urljoin

    return urljoin(base_url, href)


def discover_calendar_url(base_url: str, *, username: str, password: str) -> str | None:
    """Walks current-user-principal -> calendar-home-set -> the first child
    collection whose resourcetype is caldav:calendar, returning its full
    URL, or None if any step fails (server unreachable, wrong credentials,
    unexpected layout)."""
    auth = (username, password)

    root = _propfind(
        base_url,
        auth=auth,
        body=(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
        ),
    )
    if root is None:
        return None
    principal_href = _href_text(root, ".//d:response/d:propstat/d:prop/d:current-user-principal/d:href")
    if not principal_href:
        return None
    principal_url = _absolute(base_url, principal_href)

    root = _propfind(
        principal_url,
        auth=auth,
        body=(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:prop><c:calendar-home-set/></d:prop></d:propfind>"
        ),
    )
    if root is None:
        return None
    home_href = _href_text(root, ".//d:response/d:propstat/d:prop/c:calendar-home-set/d:href")
    if not home_href:
        return None
    home_url = _absolute(base_url, home_href)

    root = _propfind(
        home_url,
        auth=auth,
        depth="1",
        body=(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:displayname/></d:prop></d:propfind>'
        ),
    )
    if root is None:
        return None
    for response_el in root.findall(".//d:response", _NS):
        resourcetype = response_el.find(".//d:propstat/d:prop/d:resourcetype", _NS)
        if resourcetype is None:
            continue
        is_calendar = resourcetype.find("c:calendar", _NS) is not None
        is_collection_only = resourcetype.find("d:collection", _NS) is not None
        if is_calendar and is_collection_only:
            href = _href_text(response_el, "d:href")
            if href:
                return _absolute(base_url, href)
    return None


def create_event(calendar_url: str, *, username: str, password: str, ics: bytes, uid: str | None = None) -> bool:
    event_uid = uid or f"{uuid.uuid4()}"
    target = f"{calendar_url.rstrip('/')}/{event_uid}.ics"
    try:
        response = httpx.put(
            target,
            auth=(username, password),
            headers={"Content-Type": "text/calendar; charset=utf-8"},
            content=ics,
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("CalDAV PUT failed for %s: %s", target, exc)
        return False
    return response.status_code in (200, 201, 204)
