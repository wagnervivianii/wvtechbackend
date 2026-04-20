from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import re
from urllib import error, parse, request
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.booking_request import BookingRequest
from app.services.google_calendar import refresh_google_workspace_access_token

MEET_API_BASE = 'https://meet.googleapis.com/v2'
MEETING_CODE_RE = re.compile(r'([a-z]{3}-[a-z]{4}-[a-z]{3})', re.IGNORECASE)


class GoogleMeetArtifactsIntegrationError(RuntimeError):
    """Falha genérica ao sincronizar artefatos do Google Meet."""


class GoogleMeetArtifactsNotConfiguredError(GoogleMeetArtifactsIntegrationError):
    """Credenciais obrigatórias ausentes para a integração Google Meet."""


@dataclass(frozen=True, slots=True)
class GoogleMeetConferenceRecordRef:
    name: str
    meeting_code: str | None
    start_time: datetime | None
    end_time: datetime | None


@dataclass(frozen=True, slots=True)
class GoogleMeetRecordingRef:
    name: str
    state: str
    start_time: datetime | None
    end_time: datetime | None
    drive_file_id: str | None
    export_uri: str | None


@dataclass(frozen=True, slots=True)
class GoogleMeetTranscriptRef:
    name: str
    state: str
    start_time: datetime | None
    end_time: datetime | None
    document_id: str | None
    export_uri: str | None


@dataclass(frozen=True, slots=True)
class GoogleMeetSmartNoteRef:
    name: str
    state: str
    start_time: datetime | None
    end_time: datetime | None
    document_id: str | None
    export_uri: str | None


@dataclass(frozen=True, slots=True)
class GoogleMeetTranscriptEntryRef:
    name: str
    participant: str | None
    text: str | None
    language_code: str | None
    start_time: datetime | None
    end_time: datetime | None


@dataclass(frozen=True, slots=True)
class GoogleMeetArtifactSyncBundle:
    conference_record: GoogleMeetConferenceRecordRef | None
    recordings: tuple[GoogleMeetRecordingRef, ...]
    transcripts: tuple[GoogleMeetTranscriptRef, ...]
    smart_notes: tuple[GoogleMeetSmartNoteRef, ...]


def _ensure_google_meet_artifacts_configured() -> None:
    missing: list[str] = []
    if not settings.google_oauth_client_id:
        missing.append('GOOGLE_OAUTH_CLIENT_ID')
    if not settings.google_oauth_client_secret:
        missing.append('GOOGLE_OAUTH_CLIENT_SECRET')
    if not settings.google_oauth_refresh_token:
        missing.append('GOOGLE_OAUTH_REFRESH_TOKEN')

    if missing:
        raise GoogleMeetArtifactsNotConfiguredError(
            'Integração Google Meet não configurada. Defina: ' + ', '.join(missing) + '.'
        )


def _http_json_request(*, url: str, access_token: str) -> dict:
    req = request.Request(
        url=url,
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
        },
        method='GET',
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8')
    except error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        raise GoogleMeetArtifactsIntegrationError(
            f'Google Meet retornou erro {exc.code}: {raw or exc.reason}'
        ) from exc
    except error.URLError as exc:
        raise GoogleMeetArtifactsIntegrationError(
            f'Não foi possível comunicar com a Google Meet API: {exc.reason}'
        ) from exc

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _parse_rfc3339(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith('Z'):
        normalized = normalized[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _booking_window(booking: BookingRequest) -> tuple[datetime | None, datetime | None]:
    if booking.booking_date is None:
        return None, None

    tz = ZoneInfo(settings.app_timezone)
    if booking.start_time is not None:
        start_at = datetime.combine(booking.booking_date, booking.start_time, tzinfo=tz)
    else:
        start_at = datetime.combine(booking.booking_date, datetime.min.time(), tzinfo=tz)

    if booking.end_time is not None:
        end_at = datetime.combine(booking.booking_date, booking.end_time, tzinfo=tz)
    else:
        end_at = start_at + timedelta(hours=1)

    return start_at, end_at


def extract_meeting_code_from_meet_url(meet_url: str | None) -> str | None:
    if not meet_url:
        return None
    match = MEETING_CODE_RE.search(meet_url)
    if not match:
        return None
    return match.group(1).lower()


def _list_paginated(*, url: str, access_token: str, items_key: str) -> list[dict]:
    items: list[dict] = []
    next_page_token: str | None = None

    while True:
        query_connector = '&' if '?' in url else '?'
        paged_url = url
        if next_page_token:
            paged_url = f'{url}{query_connector}pageToken={parse.quote(next_page_token, safe="")}'

        payload = _http_json_request(url=paged_url, access_token=access_token)
        page_items = payload.get(items_key)
        if isinstance(page_items, list):
            items.extend(item for item in page_items if isinstance(item, dict))

        next_token = payload.get('nextPageToken')
        if not isinstance(next_token, str) or not next_token.strip():
            break
        next_page_token = next_token.strip()

    return items


def _serialize_conference_record(item: dict, *, meeting_code: str | None) -> GoogleMeetConferenceRecordRef | None:
    name = item.get('name')
    if not isinstance(name, str) or not name.strip():
        return None

    space = item.get('space') if isinstance(item.get('space'), dict) else {}
    record_meeting_code = space.get('meetingCode') if isinstance(space.get('meetingCode'), str) else meeting_code

    return GoogleMeetConferenceRecordRef(
        name=name.strip(),
        meeting_code=record_meeting_code,
        start_time=_parse_rfc3339(item.get('startTime')),
        end_time=_parse_rfc3339(item.get('endTime')),
    )


def _pick_best_conference_record(
    records: list[GoogleMeetConferenceRecordRef],
    *,
    booking: BookingRequest,
) -> GoogleMeetConferenceRecordRef | None:
    if not records:
        return None

    booking_start, _ = _booking_window(booking)
    if booking_start is None:
        return sorted(records, key=lambda item: item.start_time or datetime.min.replace(tzinfo=ZoneInfo(settings.app_timezone)), reverse=True)[0]

    def sort_key(item: GoogleMeetConferenceRecordRef) -> tuple[int, float]:
        if item.start_time is None:
            return (1, float('inf'))
        delta = abs((item.start_time.astimezone(booking_start.tzinfo) - booking_start).total_seconds())
        return (0, delta)

    nearby = [
        item
        for item in records
        if item.start_time is not None
        and abs((item.start_time.astimezone(booking_start.tzinfo) - booking_start).total_seconds()) <= 36 * 3600
    ]
    candidates = nearby or records
    return sorted(candidates, key=sort_key)[0]


def find_best_conference_record_for_booking(booking: BookingRequest) -> GoogleMeetConferenceRecordRef | None:
    _ensure_google_meet_artifacts_configured()
    meeting_code = extract_meeting_code_from_meet_url(booking.meet_url)
    if not meeting_code:
        return None

    access_token = refresh_google_workspace_access_token()
    filter_expr = f'space.meeting_code = "{meeting_code}"'
    query_string = parse.urlencode({'filter': filter_expr, 'pageSize': '20'})
    items = _list_paginated(
        url=f'{MEET_API_BASE}/conferenceRecords?{query_string}',
        access_token=access_token,
        items_key='conferenceRecords',
    )
    records = [
        record
        for item in items
        if (record := _serialize_conference_record(item, meeting_code=meeting_code)) is not None
    ]
    return _pick_best_conference_record(records, booking=booking)


def _serialize_recording(item: dict) -> GoogleMeetRecordingRef | None:
    name = item.get('name')
    if not isinstance(name, str) or not name.strip():
        return None
    drive_destination = item.get('driveDestination') if isinstance(item.get('driveDestination'), dict) else {}
    return GoogleMeetRecordingRef(
        name=name.strip(),
        state=item.get('state') if isinstance(item.get('state'), str) else 'STATE_UNSPECIFIED',
        start_time=_parse_rfc3339(item.get('startTime')),
        end_time=_parse_rfc3339(item.get('endTime')),
        drive_file_id=drive_destination.get('file') if isinstance(drive_destination.get('file'), str) else None,
        export_uri=drive_destination.get('exportUri') if isinstance(drive_destination.get('exportUri'), str) else None,
    )


def _serialize_transcript(item: dict) -> GoogleMeetTranscriptRef | None:
    name = item.get('name')
    if not isinstance(name, str) or not name.strip():
        return None
    docs_destination = item.get('docsDestination') if isinstance(item.get('docsDestination'), dict) else {}
    return GoogleMeetTranscriptRef(
        name=name.strip(),
        state=item.get('state') if isinstance(item.get('state'), str) else 'STATE_UNSPECIFIED',
        start_time=_parse_rfc3339(item.get('startTime')),
        end_time=_parse_rfc3339(item.get('endTime')),
        document_id=docs_destination.get('document') if isinstance(docs_destination.get('document'), str) else None,
        export_uri=docs_destination.get('exportUri') if isinstance(docs_destination.get('exportUri'), str) else None,
    )


def _serialize_smart_note(item: dict) -> GoogleMeetSmartNoteRef | None:
    name = item.get('name')
    if not isinstance(name, str) or not name.strip():
        return None
    docs_destination = item.get('docsDestination') if isinstance(item.get('docsDestination'), dict) else {}
    return GoogleMeetSmartNoteRef(
        name=name.strip(),
        state=item.get('state') if isinstance(item.get('state'), str) else 'STATE_UNSPECIFIED',
        start_time=_parse_rfc3339(item.get('startTime')),
        end_time=_parse_rfc3339(item.get('endTime')),
        document_id=docs_destination.get('document') if isinstance(docs_destination.get('document'), str) else None,
        export_uri=docs_destination.get('exportUri') if isinstance(docs_destination.get('exportUri'), str) else None,
    )


def _serialize_transcript_entry(item: dict) -> GoogleMeetTranscriptEntryRef | None:
    name = item.get('name')
    if not isinstance(name, str) or not name.strip():
        return None
    return GoogleMeetTranscriptEntryRef(
        name=name.strip(),
        participant=item.get('participant') if isinstance(item.get('participant'), str) else None,
        text=item.get('text') if isinstance(item.get('text'), str) else None,
        language_code=item.get('languageCode') if isinstance(item.get('languageCode'), str) else None,
        start_time=_parse_rfc3339(item.get('startTime')),
        end_time=_parse_rfc3339(item.get('endTime')),
    )


def list_recordings_for_conference_record(conference_record_name: str) -> tuple[GoogleMeetRecordingRef, ...]:
    _ensure_google_meet_artifacts_configured()
    access_token = refresh_google_workspace_access_token()
    items = _list_paginated(
        url=f'{MEET_API_BASE}/{parse.quote(conference_record_name, safe="/")}/recordings?pageSize=100',
        access_token=access_token,
        items_key='recordings',
    )
    return tuple(
        recording
        for item in items
        if (recording := _serialize_recording(item)) is not None
    )


def list_transcripts_for_conference_record(conference_record_name: str) -> tuple[GoogleMeetTranscriptRef, ...]:
    _ensure_google_meet_artifacts_configured()
    access_token = refresh_google_workspace_access_token()
    items = _list_paginated(
        url=f'{MEET_API_BASE}/{parse.quote(conference_record_name, safe="/")}/transcripts?pageSize=100',
        access_token=access_token,
        items_key='transcripts',
    )
    return tuple(
        transcript
        for item in items
        if (transcript := _serialize_transcript(item)) is not None
    )


def list_smart_notes_for_conference_record(conference_record_name: str) -> tuple[GoogleMeetSmartNoteRef, ...]:
    _ensure_google_meet_artifacts_configured()
    access_token = refresh_google_workspace_access_token()
    items = _list_paginated(
        url=f'{MEET_API_BASE}/{parse.quote(conference_record_name, safe="/")}/smartNotes?pageSize=100',
        access_token=access_token,
        items_key='smartNotes',
    )
    return tuple(
        note
        for item in items
        if (note := _serialize_smart_note(item)) is not None
    )


def list_transcript_entries(transcript_name: str) -> tuple[GoogleMeetTranscriptEntryRef, ...]:
    _ensure_google_meet_artifacts_configured()
    access_token = refresh_google_workspace_access_token()
    items = _list_paginated(
        url=f'{MEET_API_BASE}/{parse.quote(transcript_name, safe="/")}/entries?pageSize=100',
        access_token=access_token,
        items_key='entries',
    )
    return tuple(
        entry
        for item in items
        if (entry := _serialize_transcript_entry(item)) is not None
    )


def build_transcript_text(entries: tuple[GoogleMeetTranscriptEntryRef, ...]) -> str | None:
    if not entries:
        return None

    lines: list[str] = []
    local_tz = ZoneInfo(settings.app_timezone)
    for entry in entries:
        text = (entry.text or '').strip()
        if not text:
            continue
        if entry.start_time:
            stamp = entry.start_time.astimezone(local_tz).strftime('%H:%M:%S')
            lines.append(f'[{stamp}] {text}')
        else:
            lines.append(text)

    joined = "\n".join(lines).strip()
    return joined or None
