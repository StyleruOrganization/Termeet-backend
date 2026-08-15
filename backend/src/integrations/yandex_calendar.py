import logging
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin

import httpx

from backend.src.auth.models import OAuthAccount
from backend.src.integrations.yandex_telemost import (
    refresh_yandex_access_token,
)

logger = logging.getLogger(__name__)

CALDAV_BASE = "https://caldav.yandex.ru"
CALENDAR_SCOPE = "calendar:all"
DAV = "DAV:"
CALDAV = "urn:ietf:params:xml:ns:caldav"
NS = {"d": DAV, "c": CALDAV}


@dataclass
class CalendarEvent:
    uid: str
    href: str
    title: str
    start: datetime
    end: datetime


def has_calendar_scope(account: OAuthAccount | None) -> bool:
    if not account or not account.access_token:
        return False
    scopes = account.scopes or ""
    return "calendar:" in scopes


def yandex_login_of(account: OAuthAccount | None, fallback_email: str = "") -> str:
    if account is not None:
        login = (getattr(account, "yandex_login", None) or "").strip()
        email = (getattr(account, "yandex_email", None) or "").strip()
        if email:
            return email
        if login:
            return login
    return (fallback_email or "").strip()


def event_uid(meeting_id, user_id) -> str:
    return f"termeet-{meeting_id}-{user_id}@termeet.tech"


def parse_dt(value: str) -> datetime:
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "T" in text and len(text) >= 15 and "-" not in text[:8]:
        compact = re.sub(r"[^0-9T]", "", text[:15])
        dt = datetime.strptime(compact, "%Y%m%dT%H%M%S")
        return dt.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def caldav_stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(
    uid: str,
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
    url: str = "",
    sequence: int = 0,
) -> str:
    stamp = caldav_stamp(datetime.now(timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Termeet//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"SEQUENCE:{max(0, int(sequence))}",
        f"DTSTAMP:{stamp}",
        f"LAST-MODIFIED:{stamp}",
        f"DTSTART:{caldav_stamp(start)}",
        f"DTEND:{caldav_stamp(end)}",
        f"SUMMARY:{_ics_text(summary)}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{_ics_text(description)}")
    if url:
        lines.append(f"URL:{url}")
    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    return "\r\n".join(lines)


def _ics_text(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _unfold(raw: str) -> str:
    return re.sub(r"\r?\n[ \t]", "", raw or "")


def parse_vevents(ics: str, href: str = "") -> list[CalendarEvent]:
    text = _unfold(ics)
    events: list[CalendarEvent] = []
    blocks = re.findall(
        r"BEGIN:VEVENT(.*?)END:VEVENT", text, flags=re.S | re.I
    )
    for block in blocks:
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            name = key.split(";", 1)[0].upper()
            fields[name] = value.strip()
        start_raw = fields.get("DTSTART")
        end_raw = fields.get("DTEND")
        if not start_raw:
            continue
        start = parse_dt(start_raw)
        if end_raw:
            end = parse_dt(end_raw)
        else:
            end = start + timedelta(hours=1)
        events.append(
            CalendarEvent(
                uid=fields.get("UID") or str(uuid.uuid4()),
                href=href,
                title=fields.get("SUMMARY") or "Событие",
                start=start,
                end=end,
            )
        )
    return events


def events_overlap(
    start: datetime, end: datetime, other_start: datetime, other_end: datetime
) -> bool:
    return start < other_end and end > other_start


async def _dav(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    token: str,
    content: str | None = None,
    extra: dict | None = None,
) -> httpx.Response:
    headers = {
        "Authorization": f"OAuth {token}",
        "Depth": "1",
    }
    if extra:
        headers.update(extra)
    if content is not None and "Content-Type" not in headers:
        headers["Content-Type"] = "application/xml; charset=utf-8"
    return await client.request(method, url, headers=headers, content=content)


def _xml_text(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


async def _discover_calendar(
    client: httpx.AsyncClient, token: str, login: str
) -> str | None:
    if not login:
        return None
    encoded = quote(login, safe="@._-")
    homes = [
        f"{CALDAV_BASE}/principals/users/{encoded}/",
        f"{CALDAV_BASE}/calendars/{encoded}/",
    ]
    find_home = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop><c:calendar-home-set/></d:prop></d:propfind>"
    )
    find_cals = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop><d:resourcetype/><d:displayname/>"
        "<c:supported-calendar-component-set/></d:prop></d:propfind>"
    )

    calendar_homes: list[str] = []
    for home in homes:
        try:
            response = await _dav(
                client, "PROPFIND", home, token, find_home, {"Depth": "0"}
            )
        except Exception:
            continue
        if response.status_code >= 400:
            continue
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            continue
        for home_el in root.findall(".//{%s}calendar-home-set" % CALDAV):
            for href in home_el.findall(".//{%s}href" % DAV):
                value = _xml_text(href)
                if value:
                    calendar_homes.append(urljoin(CALDAV_BASE + "/", value))
        calendar_homes.append(home)

    seen: set[str] = set()
    found: list[str] = []
    for home in calendar_homes:
        if home in seen:
            continue
        seen.add(home)
        try:
            response = await _dav(client, "PROPFIND", home, token, find_cals)
        except Exception:
            continue
        if response.status_code >= 400:
            continue
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            continue
        for response_el in root:
            if _local(response_el.tag) != "response":
                continue
            href = _xml_text(response_el.find("{%s}href" % DAV))
            rtype = response_el.find(".//{%s}resourcetype" % DAV)
            is_cal = False
            if rtype is not None:
                is_cal = any(_local(child.tag) == "calendar" for child in rtype)
            if not href or not is_cal:
                continue
            abs_href = urljoin(CALDAV_BASE + "/", href)
            if not abs_href.endswith("/"):
                abs_href += "/"
            found.append(abs_href)

    if not found:
        return None
    preferred = [item for item in found if "events" in item.lower()]
    return (preferred or found)[0]


async def list_events(
    account: OAuthAccount,
    start: datetime,
    end: datetime,
    fallback_email: str = "",
) -> list[CalendarEvent]:
    if not has_calendar_scope(account):
        return []
    token = await refresh_yandex_access_token(account)
    login = yandex_login_of(account, fallback_email)
    async with httpx.AsyncClient(timeout=20) as client:
        calendar_url = await _discover_calendar(client, token, login)
        if not calendar_url:
            logger.warning("yandex calendar home not found for %s", login)
            return []
        query = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<c:calendar-query xmlns:d="DAV:" '
            'xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:prop><d:getetag/><c:calendar-data/></d:prop>"
            "<c:filter><c:comp-filter name=\"VCALENDAR\">"
            "<c:comp-filter name=\"VEVENT\">"
            f'<c:time-range start="{caldav_stamp(start)}" '
            f'end="{caldav_stamp(end)}"/>'
            "</c:comp-filter></c:comp-filter></c:filter>"
            "</c:calendar-query>"
        )
        response = await _dav(
            client,
            "REPORT",
            calendar_url,
            token,
            query,
            extra={
                "Depth": "1",
                "Content-Type": "application/xml; charset=utf-8",
            },
        )
        if response.status_code >= 400:
            logger.warning(
                "yandex calendar report failed %s %s",
                response.status_code,
                response.text[:300],
            )
            return []
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            return []
        events: list[CalendarEvent] = []
        for response_el in root:
            if _local(response_el.tag) != "response":
                continue
            href = _xml_text(response_el.find("{%s}href" % DAV))
            data = response_el.find(".//{%s}calendar-data" % CALDAV)
            ics = "".join(data.itertext()) if data is not None else ""
            events.extend(parse_vevents(ics, href))
        return events


def _abs_dav(url: str) -> str:
    if url.startswith("http"):
        return url
    return urljoin(CALDAV_BASE + "/", url)


async def _put_ics(
    client: httpx.AsyncClient, token: str, target: str, ics: str
) -> bool:
    response = await _dav(
        client,
        "PUT",
        _abs_dav(target),
        token,
        ics,
        extra={"Content-Type": "text/calendar; charset=utf-8"},
    )
    if response.status_code >= 400:
        logger.warning(
            "yandex calendar put failed %s %s",
            response.status_code,
            response.text[:300],
        )
        return False
    return True


async def _delete_href(
    client: httpx.AsyncClient, token: str, href: str
) -> bool:
    if not (href or "").strip():
        return False
    response = await _dav(client, "DELETE", _abs_dav(href), token)
    if response.status_code >= 400 and response.status_code != 404:
        logger.warning(
            "yandex calendar delete failed %s %s %s",
            response.status_code,
            href,
            response.text[:300],
        )
        return False
    return True


def _xml_escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def _find_href_by_uid(
    client: httpx.AsyncClient,
    token: str,
    calendar_url: str | None,
    uid: str,
) -> str | None:
    if not calendar_url or not uid:
        return None
    query = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<c:calendar-query xmlns:d="DAV:" '
        'xmlns:c="urn:ietf:params:xml:ns:caldav">'
        "<d:prop><d:getetag/><c:calendar-data/></d:prop>"
        "<c:filter><c:comp-filter name=\"VCALENDAR\">"
        "<c:comp-filter name=\"VEVENT\">"
        '<c:prop-filter name="UID">'
        f"<c:text-match>{_xml_escape(uid)}</c:text-match>"
        "</c:prop-filter></c:comp-filter></c:comp-filter></c:filter>"
        "</c:calendar-query>"
    )
    try:
        response = await _dav(
            client,
            "REPORT",
            calendar_url,
            token,
            query,
            extra={
                "Depth": "1",
                "Content-Type": "application/xml; charset=utf-8",
            },
        )
    except Exception:
        return None
    if response.status_code >= 400:
        return None
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return None
    for response_el in root:
        if _local(response_el.tag) != "response":
            continue
        href = _xml_text(response_el.find("{%s}href" % DAV))
        data = response_el.find(".//{%s}calendar-data" % CALDAV)
        ics = "".join(data.itertext()) if data is not None else ""
        for event in parse_vevents(ics, href):
            if event.uid == uid and href:
                return href
    return None


async def upsert_event(
    account: OAuthAccount,
    uid: str,
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
    url: str = "",
    href: str | None = None,
    fallback_email: str = "",
    sequence: int = 0,
) -> str | None:
    if not has_calendar_scope(account):
        return None
    token = await refresh_yandex_access_token(account)
    login = yandex_login_of(account, fallback_email)
    ics = build_ics(
        uid, summary, start, end, description, url, sequence=sequence
    )
    async with httpx.AsyncClient(timeout=20) as client:
        calendar_url = await _discover_calendar(client, token, login)
        found = await _find_href_by_uid(client, token, calendar_url, uid)
        target = found or href or None
        if not target and calendar_url:
            target = f"{calendar_url}{uid}.ics"
        if not target:
            return None
        if await _put_ics(client, token, target, ics):
            return target
        if found and href and found != href:
            if await _put_ics(client, token, href, ics):
                return href
        if found:
            await _delete_href(client, token, found)
        if href and href != found:
            await _delete_href(client, token, href)
        if not calendar_url:
            return None
        fresh = f"{calendar_url}{uid}.ics"
        if await _put_ics(client, token, fresh, ics):
            return fresh
        return None


async def delete_event(
    account: OAuthAccount,
    href: str,
    fallback_email: str = "",
) -> bool:
    if not has_calendar_scope(account) or not (href or "").strip():
        return False
    token = await refresh_yandex_access_token(account)
    async with httpx.AsyncClient(timeout=20) as client:
        return await _delete_href(client, token, href)
