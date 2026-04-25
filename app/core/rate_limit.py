from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic

from fastapi import HTTPException, Request, status


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    name: str
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, *, key: str, rule: RateLimitRule) -> None:
        now = monotonic()
        bucket_key = f'{rule.name}:{key}'
        bucket = self._hits[bucket_key]
        cutoff = now - rule.window_seconds

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= rule.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail='Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente.',
            )

        bucket.append(now)


_limiter = InMemoryRateLimiter()


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
    if forwarded_for:
        return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return 'unknown'


def _rate_limit(request: Request, rule: RateLimitRule) -> None:
    _limiter.check(key=_client_ip(request), rule=rule)


def rate_limit_admin_login(request: Request) -> None:
    _rate_limit(
        request,
        RateLimitRule(name='admin-login', max_requests=8, window_seconds=10 * 60),
    )


def rate_limit_client_auth(request: Request) -> None:
    _rate_limit(
        request,
        RateLimitRule(name='client-auth', max_requests=12, window_seconds=10 * 60),
    )


def rate_limit_booking_request(request: Request) -> None:
    _rate_limit(
        request,
        RateLimitRule(name='booking-request', max_requests=6, window_seconds=10 * 60),
    )


def rate_limit_client_upload(request: Request) -> None:
    _rate_limit(
        request,
        RateLimitRule(name='client-upload', max_requests=10, window_seconds=30 * 60),
    )


def rate_limit_whatsapp_webhook(request: Request) -> None:
    _rate_limit(
        request,
        RateLimitRule(name='whatsapp-webhook', max_requests=120, window_seconds=60),
    )
