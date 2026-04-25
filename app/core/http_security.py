from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        headers = MutableHeaders(response.headers)

        headers.setdefault('X-Content-Type-Options', 'nosniff')
        headers.setdefault('X-Frame-Options', 'DENY')
        headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        headers.setdefault('X-Robots-Tag', 'noindex, nofollow')

        if request.url.scheme == 'https' or settings.app_env == 'production':
            headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

        return response
