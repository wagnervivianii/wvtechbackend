from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_UPLOAD_EXTENSIONS = {
    '.pdf',
    '.xls',
    '.xlsx',
    '.csv',
    '.ppt',
    '.pptx',
    '.doc',
    '.docx',
    '.txt',
}

ALLOWED_UPLOAD_MIME_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/csv',
    'text/plain',
    'application/csv',
    'application/octet-stream',
}

DANGEROUS_EXTENSION_FRAGMENTS = {
    '.bat',
    '.cmd',
    '.com',
    '.dll',
    '.exe',
    '.html',
    '.htm',
    '.js',
    '.jsp',
    '.php',
    '.ps1',
    '.py',
    '.sh',
    '.svg',
    '.vbs',
}

OFFICE_OPEN_XML_EXTENSIONS = {'.docx', '.xlsx', '.pptx'}
LEGACY_OFFICE_EXTENSIONS = {'.doc', '.xls', '.ppt'}
TEXT_EXTENSIONS = {'.csv', '.txt'}


@dataclass(frozen=True, slots=True)
class SafeUploadMetadata:
    file_name: str
    file_extension: str
    mime_type: str | None


def sanitize_upload_filename(file_name: str) -> str:
    raw_name = Path(file_name or 'arquivo').name.strip().replace('\x00', '')
    if not raw_name:
        raw_name = 'arquivo'

    normalized = unicodedata.normalize('NFKD', raw_name)
    ascii_name = normalized.encode('ascii', 'ignore').decode('ascii')
    safe_name = re.sub(r'[^A-Za-z0-9._ -]+', '_', ascii_name).strip(' ._-')

    if not safe_name:
        safe_name = 'arquivo'

    if len(safe_name) > 180:
        path = Path(safe_name)
        stem = path.stem[:120] or 'arquivo'
        suffix = path.suffix[:20]
        safe_name = f'{stem}{suffix}'

    return safe_name


def _extension_parts(file_name: str) -> list[str]:
    return [suffix.lower() for suffix in Path(file_name).suffixes]


def _validate_extension(file_name: str) -> str:
    extension = Path(file_name).suffix.strip().lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Tipo de arquivo não permitido. Use PDF, Excel, PowerPoint, Word, CSV ou TXT.',
        )

    parts = _extension_parts(file_name)
    if any(part in DANGEROUS_EXTENSION_FRAGMENTS for part in parts[:-1]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Nome de arquivo com extensão insegura.',
        )

    return extension


def _validate_mime_type(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    normalized = mime_type.split(';', 1)[0].strip().lower()
    if normalized and normalized not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Tipo MIME do arquivo não permitido.',
        )
    return normalized or None


def _looks_like_text_file(file_bytes: bytes) -> bool:
    sample = file_bytes[:4096]
    if b'\x00' in sample:
        return False
    try:
        sample.decode('utf-8')
        return True
    except UnicodeDecodeError:
        try:
            sample.decode('latin-1')
            return True
        except UnicodeDecodeError:
            return False


def _validate_file_signature(extension: str, file_bytes: bytes) -> None:
    header = file_bytes[:8]

    if extension == '.pdf' and not header.startswith(b'%PDF'):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='O conteúdo do arquivo não parece ser um PDF válido.',
        )

    if extension in OFFICE_OPEN_XML_EXTENSIONS and not header.startswith(b'PK'):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='O conteúdo do arquivo não parece ser um documento Office válido.',
        )

    if extension in LEGACY_OFFICE_EXTENSIONS and not (
        header.startswith(b'\xd0\xcf\x11\xe0') or header.startswith(b'PK')
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='O conteúdo do arquivo não parece ser um documento Office válido.',
        )

    if extension in TEXT_EXTENSIONS and not _looks_like_text_file(file_bytes):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='O conteúdo do arquivo não parece ser texto válido.',
        )


def validate_upload_payload(upload: UploadFile, file_bytes: bytes) -> SafeUploadMetadata:
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='O arquivo enviado está vazio.',
        )

    if len(file_bytes) > settings.google_drive_direct_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail='O arquivo excede o limite configurado para upload direto ao Google Drive.',
        )

    safe_name = sanitize_upload_filename(upload.filename or 'arquivo')
    extension = _validate_extension(safe_name)
    mime_type = _validate_mime_type(upload.content_type)
    _validate_file_signature(extension, file_bytes)

    return SafeUploadMetadata(
        file_name=safe_name,
        file_extension=extension,
        mime_type=mime_type,
    )
