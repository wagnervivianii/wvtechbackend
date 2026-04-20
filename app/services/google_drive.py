from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from urllib import error, parse, request

from app.core.config import settings
from app.services.google_calendar import refresh_google_workspace_access_token

DRIVE_API_BASE = 'https://www.googleapis.com/drive/v3'
FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'
CLIENT_MEET_ARTIFACTS_FOLDER_NAME = '01_meet_artifacts'
CLIENT_UPLOADS_FOLDER_NAME = '02_client_uploads'
CLIENT_GENERATED_DOCUMENTS_FOLDER_NAME = '03_generated_documents'
CLIENT_ARCHIVE_FOLDER_NAME = '99_archive'


class GoogleDriveIntegrationError(RuntimeError):
    """Falha genérica ao integrar com o Google Drive."""


class GoogleDriveIntegrationNotConfiguredError(GoogleDriveIntegrationError):
    """Configuração obrigatória ausente para provisionar pastas no Drive."""


@dataclass(frozen=True, slots=True)
class GoogleDriveFolderRef:
    folder_id: str
    folder_name: str
    web_view_link: str | None


@dataclass(frozen=True, slots=True)
class GoogleDriveWorkspaceFolders:
    root: GoogleDriveFolderRef
    meet_artifacts: GoogleDriveFolderRef
    client_uploads: GoogleDriveFolderRef
    generated_documents: GoogleDriveFolderRef
    archive: GoogleDriveFolderRef


def is_google_drive_workspace_storage_configured() -> bool:
    return bool(
        settings.google_drive_auto_create_client_folders
        and settings.google_drive_clients_root_folder_id
        and settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_oauth_refresh_token
    )


def _ensure_google_drive_configured() -> None:
    missing: list[str] = []

    if not settings.google_drive_auto_create_client_folders:
        missing.append('GOOGLE_DRIVE_AUTO_CREATE_CLIENT_FOLDERS=true')
    if not settings.google_drive_clients_root_folder_id:
        missing.append('GOOGLE_DRIVE_CLIENTS_ROOT_FOLDER_ID')
    if not settings.google_oauth_client_id:
        missing.append('GOOGLE_OAUTH_CLIENT_ID')
    if not settings.google_oauth_client_secret:
        missing.append('GOOGLE_OAUTH_CLIENT_SECRET')
    if not settings.google_oauth_refresh_token:
        missing.append('GOOGLE_OAUTH_REFRESH_TOKEN')

    if missing:
        raise GoogleDriveIntegrationNotConfiguredError(
            'Estrutura Google Drive do cliente não configurada. Defina: ' + ', '.join(missing) + '.'
        )


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
        raise GoogleDriveIntegrationError(
            f'Google Drive retornou erro {exc.code}: {raw or exc.reason}'
        ) from exc
    except error.URLError as exc:
        raise GoogleDriveIntegrationError(
            f'Não foi possível comunicar com a Google Drive API: {exc.reason}'
        ) from exc

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _escape_drive_query_literal(value: str) -> str:
    return value.replace('\\', '\\\\').replace("'", "\\'")


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_text).strip('-')
    return slug or 'cliente'


def _build_client_root_folder_name(*, workspace_id: int, primary_contact_name: str) -> str:
    slug = _slugify(primary_contact_name)[:48]
    return f'cliente_{workspace_id:04d}_{slug}'


def _folder_web_url(folder_id: str) -> str:
    return f'https://drive.google.com/drive/folders/{folder_id}'


def _find_folder_by_name(
    *,
    access_token: str,
    parent_folder_id: str,
    folder_name: str,
) -> GoogleDriveFolderRef | None:
    query = (
        f"name = '{_escape_drive_query_literal(folder_name)}' "
        f"and '{_escape_drive_query_literal(parent_folder_id)}' in parents "
        f"and mimeType = '{FOLDER_MIME_TYPE}' and trashed = false"
    )
    query_string = parse.urlencode(
        {
            'q': query,
            'pageSize': '1',
            'fields': 'files(id,name,webViewLink)',
            'supportsAllDrives': 'true',
            'includeItemsFromAllDrives': 'true',
        }
    )
    payload = _http_json_request(
        url=f'{DRIVE_API_BASE}/files?{query_string}',
        headers={'Authorization': f'Bearer {access_token}'},
    )

    files = payload.get('files')
    if not isinstance(files, list) or not files:
        return None

    file_data = files[0]
    folder_id = file_data.get('id')
    folder_name = file_data.get('name')
    if not isinstance(folder_id, str) or not folder_id.strip():
        return None
    if not isinstance(folder_name, str) or not folder_name.strip():
        folder_name = 'folder'

    web_view_link = file_data.get('webViewLink') if isinstance(file_data.get('webViewLink'), str) else None
    return GoogleDriveFolderRef(
        folder_id=folder_id.strip(),
        folder_name=folder_name.strip(),
        web_view_link=web_view_link or _folder_web_url(folder_id.strip()),
    )


def _create_folder(
    *,
    access_token: str,
    parent_folder_id: str,
    folder_name: str,
) -> GoogleDriveFolderRef:
    query_string = parse.urlencode(
        {
            'supportsAllDrives': 'true',
            'fields': 'id,name,webViewLink',
        }
    )
    payload = _http_json_request(
        url=f'{DRIVE_API_BASE}/files?{query_string}',
        method='POST',
        headers={'Authorization': f'Bearer {access_token}'},
        payload={
            'name': folder_name,
            'mimeType': FOLDER_MIME_TYPE,
            'parents': [parent_folder_id],
        },
    )

    folder_id = payload.get('id')
    folder_name_value = payload.get('name')
    if not isinstance(folder_id, str) or not folder_id.strip():
        raise GoogleDriveIntegrationError(
            'A Google Drive API não retornou um id válido para a pasta criada.'
        )

    if not isinstance(folder_name_value, str) or not folder_name_value.strip():
        folder_name_value = folder_name

    web_view_link = payload.get('webViewLink') if isinstance(payload.get('webViewLink'), str) else None
    return GoogleDriveFolderRef(
        folder_id=folder_id.strip(),
        folder_name=folder_name_value.strip(),
        web_view_link=web_view_link or _folder_web_url(folder_id.strip()),
    )


def _ensure_folder(
    *,
    access_token: str,
    parent_folder_id: str,
    folder_name: str,
) -> GoogleDriveFolderRef:
    existing = _find_folder_by_name(
        access_token=access_token,
        parent_folder_id=parent_folder_id,
        folder_name=folder_name,
    )
    if existing is not None:
        return existing
    return _create_folder(
        access_token=access_token,
        parent_folder_id=parent_folder_id,
        folder_name=folder_name,
    )


def ensure_client_workspace_drive_folders(
    *,
    workspace_id: int,
    primary_contact_name: str,
    existing_root_folder_id: str | None = None,
) -> GoogleDriveWorkspaceFolders:
    _ensure_google_drive_configured()
    access_token = refresh_google_workspace_access_token()

    root_parent_folder_id = existing_root_folder_id or settings.google_drive_clients_root_folder_id
    root_folder_name = (
        _build_client_root_folder_name(
            workspace_id=workspace_id,
            primary_contact_name=primary_contact_name,
        )
        if not existing_root_folder_id
        else None
    )

    if existing_root_folder_id:
        root_folder = GoogleDriveFolderRef(
            folder_id=existing_root_folder_id,
            folder_name=root_folder_name or 'workspace_root',
            web_view_link=_folder_web_url(existing_root_folder_id),
        )
        root_details = _http_json_request(
            url=f"{DRIVE_API_BASE}/files/{parse.quote(existing_root_folder_id, safe='')}?{parse.urlencode({'fields': 'id,name,webViewLink', 'supportsAllDrives': 'true'})}",
            headers={'Authorization': f'Bearer {access_token}'},
        )
        folder_name_value = root_details.get('name') if isinstance(root_details.get('name'), str) else None
        web_view_link = root_details.get('webViewLink') if isinstance(root_details.get('webViewLink'), str) else None
        root_folder = GoogleDriveFolderRef(
            folder_id=existing_root_folder_id,
            folder_name=folder_name_value or 'workspace_root',
            web_view_link=web_view_link or _folder_web_url(existing_root_folder_id),
        )
    else:
        root_folder = _ensure_folder(
            access_token=access_token,
            parent_folder_id=root_parent_folder_id,
            folder_name=root_folder_name,
        )

    meet_artifacts = _ensure_folder(
        access_token=access_token,
        parent_folder_id=root_folder.folder_id,
        folder_name=CLIENT_MEET_ARTIFACTS_FOLDER_NAME,
    )
    client_uploads = _ensure_folder(
        access_token=access_token,
        parent_folder_id=root_folder.folder_id,
        folder_name=CLIENT_UPLOADS_FOLDER_NAME,
    )
    generated_documents = _ensure_folder(
        access_token=access_token,
        parent_folder_id=root_folder.folder_id,
        folder_name=CLIENT_GENERATED_DOCUMENTS_FOLDER_NAME,
    )
    archive = _ensure_folder(
        access_token=access_token,
        parent_folder_id=root_folder.folder_id,
        folder_name=CLIENT_ARCHIVE_FOLDER_NAME,
    )

    return GoogleDriveWorkspaceFolders(
        root=root_folder,
        meet_artifacts=meet_artifacts,
        client_uploads=client_uploads,
        generated_documents=generated_documents,
        archive=archive,
    )
