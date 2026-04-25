from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException, status

from app.core.config import settings


def _normalized_origin(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    return f'{scheme}://{netloc}'


def _allowed_redirect_origins() -> set[str]:
    origins = {
        _normalized_origin(settings.public_app_base_url),
        _normalized_origin(settings.client_portal_base_url),
    }
    return {origin for origin in origins if origin}


def validate_public_redirect_uri(redirect_uri: str) -> str:
    value = redirect_uri.strip()
    parsed = urlparse(value)

    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='URL de retorno inválida.',
        )

    if settings.app_env.lower() == 'production' and parsed.scheme != 'https':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='URL de retorno inválida.',
        )

    origin = _normalized_origin(value)
    if origin not in _allowed_redirect_origins():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='URL de retorno não autorizada.',
        )

    return value
