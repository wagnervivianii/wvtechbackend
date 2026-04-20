from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def is_admin_auth_configured() -> bool:
    return bool(
        settings.admin_username
        and settings.admin_password
        and settings.admin_token_secret
    )


def is_client_auth_configured() -> bool:
    return bool(settings.client_auth_token_secret)


def verify_admin_credentials(username: str, password: str) -> bool:
    if not is_admin_auth_configured():
        return False

    normalized_username = username.strip()
    return secrets.compare_digest(
        normalized_username,
        settings.admin_username,
    ) and secrets.compare_digest(
        password,
        settings.admin_password,
    )


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _create_signed_token(*, payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_segment = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")

    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    signature_segment = _b64url_encode(signature)

    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _decode_signed_token(*, token: str, secret: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        ) from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    provided_signature = _b64url_decode(signature_segment)

    if not hmac.compare_digest(expected_signature, provided_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        )

    try:
        return json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        ) from exc


def create_admin_access_token() -> str:
    now = int(time.time())
    payload = {
        "sub": settings.admin_username,
        "role": "admin",
        "iss": settings.admin_token_issuer,
        "iat": now,
        "exp": now + (settings.admin_token_ttl_minutes * 60),
    }
    return _create_signed_token(payload=payload, secret=settings.admin_token_secret)


def decode_admin_access_token(token: str) -> dict[str, Any]:
    if not is_admin_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação administrativa não configurada.",
        )

    payload = _decode_signed_token(token=token, secret=settings.admin_token_secret)

    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token administrativo expirado.",
        )

    if payload.get("iss") != settings.admin_token_issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token administrativo inválido.",
        )

    if payload.get("sub") != settings.admin_username or payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token administrativo inválido.",
        )

    return payload


def create_client_access_token(*, account_id: int, workspace_id: int, email: str) -> str:
    if not is_client_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação do cliente não configurada.",
        )

    now = int(time.time())
    payload = {
        "sub": str(account_id),
        "workspace_id": workspace_id,
        "email": email,
        "role": "client",
        "iss": settings.client_auth_token_issuer,
        "iat": now,
        "exp": now + (settings.client_auth_token_ttl_minutes * 60),
    }
    return _create_signed_token(payload=payload, secret=settings.client_auth_token_secret)


def decode_client_access_token(token: str) -> dict[str, Any]:
    if not is_client_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação do cliente não configurada.",
        )

    payload = _decode_signed_token(token=token, secret=settings.client_auth_token_secret)

    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão do cliente expirada.",
        )

    if payload.get("iss") != settings.client_auth_token_issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão do cliente inválida.",
        )

    if payload.get("role") != "client":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão do cliente inválida.",
        )

    return payload


def create_client_google_state_token(*, redirect_uri: str, invite_token: str | None = None) -> str:
    if not is_client_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação do cliente não configurada.",
        )

    now = int(time.time())
    payload = {
        "iss": f"{settings.client_auth_token_issuer}-google-state",
        "iat": now,
        "exp": now + (settings.client_google_state_ttl_minutes * 60),
        "redirect_uri": redirect_uri,
        "invite_token": invite_token,
        "nonce": secrets.token_urlsafe(12),
    }
    return _create_signed_token(payload=payload, secret=settings.client_auth_token_secret)


def decode_client_google_state_token(token: str) -> dict[str, Any]:
    payload = _decode_signed_token(token=token, secret=settings.client_auth_token_secret)
    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State inválido ou expirado.",
        )
    if payload.get("iss") != f"{settings.client_auth_token_issuer}-google-state":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State inválido ou expirado.",
        )
    return payload


def get_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = settings.client_password_hash_iterations
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode('utf-8')}${base64.b64encode(derived).decode('utf-8')}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        scheme, iterations_text, salt_b64, hash_b64 = password_hash.split('$', 3)
        if scheme != 'pbkdf2_sha256':
            return False
        salt = base64.b64decode(salt_b64.encode('utf-8'))
        expected = base64.b64decode(hash_b64.encode('utf-8'))
        iterations = int(iterations_text)
    except (ValueError, TypeError):
        return False

    provided = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return hmac.compare_digest(provided, expected)


def require_admin_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais administrativas não informadas.",
        )

    return decode_admin_access_token(credentials.credentials)


def require_client_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Credenciais do cliente não informadas.',
        )

    return decode_client_access_token(credentials.credentials)