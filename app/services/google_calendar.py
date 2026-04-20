from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import secrets
import time
from urllib import error, parse, request
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.booking_request import BookingRequest


class GoogleCalendarIntegrationError(RuntimeError):
    """Base de falhas da integração Google Calendar / Meet."""


class GoogleCalendarIntegrationNotConfiguredError(GoogleCalendarIntegrationError):
    """Credenciais obrigatórias ausentes."""


class GoogleCalendarMeetingCreationError(GoogleCalendarIntegrationError):
    """Falha ao criar evento ou conferência do Google Meet."""


class GoogleCalendarMeetingCancellationError(GoogleCalendarIntegrationError):
    """Falha ao cancelar evento da integração Google."""


@dataclass(frozen=True, slots=True)
class GoogleCalendarMeetingResult:
    event_id: str
    meet_url: str
    html_link: str | None


CALENDAR_API_BASE = 'https://www.googleapis.com/calendar/v3'


def _ensure_google_calendar_configured() -> None:
    missing = []
    if not settings.google_oauth_client_id:
        missing.append('GOOGLE_OAUTH_CLIENT_ID')
    if not settings.google_oauth_client_secret:
        missing.append('GOOGLE_OAUTH_CLIENT_SECRET')
    if not settings.google_oauth_refresh_token:
        missing.append('GOOGLE_OAUTH_REFRESH_TOKEN')

    if missing:
        raise GoogleCalendarIntegrationNotConfiguredError(
            'Integração Google Calendar/Meet não configurada. Defina: ' + ', '.join(missing) + '.'
        )


def _build_booking_datetime(booking: BookingRequest) -> tuple[datetime, datetime]:
    if booking.booking_date is None or booking.start_time is None or booking.end_time is None:
        raise GoogleCalendarMeetingCreationError(
            'A solicitação não possui data e horário completos para gerar o evento no Google Meet.'
        )

    tz = ZoneInfo(settings.app_timezone)
    start_at = datetime.combine(booking.booking_date, booking.start_time, tzinfo=tz)
    end_at = datetime.combine(booking.booking_date, booking.end_time, tzinfo=tz)

    if end_at <= start_at:
        raise GoogleCalendarMeetingCreationError(
            'A solicitação possui um intervalo de horário inválido para geração do evento.'
        )

    return start_at, end_at


def _http_json_request(
    *,
    url: str,
    method: str = 'GET',
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
) -> dict:
    body = None
    request_headers = {'Accept': 'application/json'}
    if headers:
        request_headers.update(headers)

    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        request_headers['Content-Type'] = 'application/json'

    req = request.Request(url=url, data=body, headers=request_headers, method=method)

    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8')
    except error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        message = raw or exc.reason
        if method == 'DELETE':
            raise GoogleCalendarMeetingCancellationError(
                f'Google API retornou erro {exc.code} ao cancelar evento: {message}'
            ) from exc
        raise GoogleCalendarMeetingCreationError(
            f'Google API retornou erro {exc.code}: {message}'
        ) from exc
    except error.URLError as exc:
        if method == 'DELETE':
            raise GoogleCalendarMeetingCancellationError(
                f'Não foi possível comunicar com a Google API para cancelar o evento: {exc.reason}'
            ) from exc
        raise GoogleCalendarMeetingCreationError(
            f'Não foi possível comunicar com a Google API: {exc.reason}'
        ) from exc

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _refresh_google_access_token() -> str:
    _ensure_google_calendar_configured()

    form_payload = parse.urlencode(
        {
            'client_id': settings.google_oauth_client_id,
            'client_secret': settings.google_oauth_client_secret,
            'refresh_token': settings.google_oauth_refresh_token,
            'grant_type': 'refresh_token',
        }
    ).encode('utf-8')

    req = request.Request(
        url=settings.google_oauth_token_url,
        data=form_payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8')
    except error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        raise GoogleCalendarMeetingCreationError(
            f'Falha ao renovar token Google ({exc.code}): {raw or exc.reason}'
        ) from exc
    except error.URLError as exc:
        raise GoogleCalendarMeetingCreationError(
            f'Não foi possível renovar o token Google: {exc.reason}'
        ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GoogleCalendarMeetingCreationError(
            'Resposta inválida ao renovar token Google.'
        ) from exc

    access_token = payload.get('access_token')
    if not isinstance(access_token, str) or not access_token.strip():
        raise GoogleCalendarMeetingCreationError(
            'A resposta de autenticação Google não retornou access_token válido.'
        )

    return access_token


def refresh_google_workspace_access_token() -> str:
    return _refresh_google_access_token()


def _extract_meet_url(event_payload: dict) -> str | None:
    hangout_link = event_payload.get('hangoutLink')
    if isinstance(hangout_link, str) and hangout_link.strip():
        return hangout_link.strip()

    conference_data = event_payload.get('conferenceData')
    if not isinstance(conference_data, dict):
        return None

    entry_points = conference_data.get('entryPoints')
    if isinstance(entry_points, list):
        for entry in entry_points:
            if not isinstance(entry, dict):
                continue
            if entry.get('entryPointType') != 'video':
                continue
            uri = entry.get('uri')
            if isinstance(uri, str) and uri.strip():
                return uri.strip()

    return None


def _poll_event_until_meet_ready(*, access_token: str, event_id: str) -> GoogleCalendarMeetingResult:
    calendar_id = parse.quote(settings.google_calendar_id, safe='')
    event_url = f'{CALENDAR_API_BASE}/calendars/{calendar_id}/events/{parse.quote(event_id, safe="")}'

    attempts = max(settings.google_meet_retry_attempts, 1)
    delay = max(settings.google_meet_retry_delay_seconds, 0.2)

    for attempt in range(attempts):
        if attempt:
            time.sleep(delay)

        payload = _http_json_request(
            url=event_url,
            headers={'Authorization': f'Bearer {access_token}'},
        )

        meet_url = _extract_meet_url(payload)
        if meet_url:
            event_id_value = payload.get('id') or event_id
            html_link = payload.get('htmlLink') if isinstance(payload.get('htmlLink'), str) else None
            return GoogleCalendarMeetingResult(
                event_id=str(event_id_value),
                meet_url=meet_url,
                html_link=html_link,
            )

        conference_data = payload.get('conferenceData')
        if isinstance(conference_data, dict):
            create_request = conference_data.get('createRequest')
            if isinstance(create_request, dict):
                status_data = create_request.get('status')
                if isinstance(status_data, dict) and status_data.get('statusCode') == 'failure':
                    raise GoogleCalendarMeetingCreationError(
                        'A Google API informou falha ao gerar a conferência do Google Meet.'
                    )

    raise GoogleCalendarMeetingCreationError(
        'O evento foi criado, mas o link do Google Meet não ficou pronto dentro do tempo esperado.'
    )


def _delete_event_best_effort(*, access_token: str, event_id: str) -> None:
    calendar_id = parse.quote(settings.google_calendar_id, safe='')
    query_string = parse.urlencode({'sendUpdates': 'none'})
    event_url = f'{CALENDAR_API_BASE}/calendars/{calendar_id}/events/{parse.quote(event_id, safe="")}?{query_string}'
    try:
        _http_json_request(
            url=event_url,
            method='DELETE',
            headers={'Authorization': f'Bearer {access_token}'},
        )
    except GoogleCalendarIntegrationError:
        return


def create_google_meet_event_for_booking(*, booking: BookingRequest, meeting_notes: str | None) -> GoogleCalendarMeetingResult:
    access_token = _refresh_google_access_token()
    start_at, end_at = _build_booking_datetime(booking)

    calendar_id = parse.quote(settings.google_calendar_id, safe='')
    query_string = parse.urlencode(
        {
            'conferenceDataVersion': '1',
            'sendUpdates': settings.google_calendar_send_updates,
        }
    )
    url = f'{CALENDAR_API_BASE}/calendars/{calendar_id}/events?{query_string}'

    event_summary = f'{settings.google_calendar_event_summary_prefix} | {booking.name}'
    description_lines = [
        'Solicitação aprovada automaticamente pelo painel administrativo da WV Tech Solutions.',
        f'Contato: {booking.name}',
        f'E-mail: {booking.email}',
        f'Telefone: {booking.phone}',
        f'Assunto: {booking.subject_summary}',
    ]
    if meeting_notes:
        description_lines.extend(['', 'Observações internas:', meeting_notes])

    payload = {
        'summary': event_summary,
        'description': '\n'.join(description_lines),
        'start': {'dateTime': start_at.isoformat(), 'timeZone': settings.app_timezone},
        'end': {'dateTime': end_at.isoformat(), 'timeZone': settings.app_timezone},
        'attendees': [{'email': booking.email, 'displayName': booking.name}],
        'conferenceData': {
            'createRequest': {
                'requestId': secrets.token_urlsafe(18),
                'conferenceSolutionKey': {'type': 'hangoutsMeet'},
            }
        },
    }

    created_event = _http_json_request(
        url=url,
        method='POST',
        headers={'Authorization': f'Bearer {access_token}'},
        payload=payload,
    )

    event_id = created_event.get('id')
    if not isinstance(event_id, str) or not event_id.strip():
        raise GoogleCalendarMeetingCreationError(
            'A Google API não retornou um event_id válido para a reunião criada.'
        )

    try:
        return _poll_event_until_meet_ready(access_token=access_token, event_id=event_id)
    except GoogleCalendarMeetingCreationError:
        _delete_event_best_effort(access_token=access_token, event_id=event_id)
        raise


def cancel_google_event_for_booking(*, event_id: str) -> None:
    access_token = _refresh_google_access_token()
    calendar_id = parse.quote(settings.google_calendar_id, safe='')
    query_string = parse.urlencode({'sendUpdates': 'none'})
    event_url = f'{CALENDAR_API_BASE}/calendars/{calendar_id}/events/{parse.quote(event_id, safe="")}?{query_string}'
    _http_json_request(
        url=event_url,
        method='DELETE',
        headers={'Authorization': f'Bearer {access_token}'},
    )