import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import rate_limit_whatsapp_webhook
from app.db.session import get_db
from app.integrations.meta_whatsapp.exceptions import MetaWhatsAppWebhookVerificationError
from app.integrations.meta_whatsapp.webhook import MetaWebhookParser, MetaWebhookVerifier
from app.services.booking_whatsapp import BookingWhatsAppService


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix='/integrations/whatsapp',
    tags=['whatsapp-meta'],
)


@router.get('/webhook')
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias='hub.mode'),
    hub_verify_token: str | None = Query(default=None, alias='hub.verify_token'),
    hub_challenge: str | None = Query(default=None, alias='hub.challenge'),
) -> Response:
    try:
        challenge = MetaWebhookVerifier.verify_subscription(
            mode=hub_mode,
            verify_token=hub_verify_token,
            challenge=hub_challenge,
            expected_token=settings.meta_whatsapp_webhook_verify_token,
        )
    except MetaWhatsAppWebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return Response(content=challenge, media_type='text/plain')


@router.post('/webhook')
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    rate_limit_whatsapp_webhook(request)
    raw_body = await request.body()

    try:
        MetaWebhookVerifier.verify_payload_signature(
            raw_body=raw_body,
            signature_header=request.headers.get('x-hub-signature-256'),
            app_secret=settings.meta_whatsapp_app_secret,
        )
    except MetaWhatsAppWebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        payload = json.loads(raw_body.decode('utf-8')) if raw_body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Payload JSON inválido.',
        ) from exc

    parsed = MetaWebhookParser.parse(payload)
    processed_changes = BookingWhatsAppService().process_webhook_events(
        db=db,
        parse_result=parsed,
    )

    logger.info(
        'Webhook WhatsApp recebido. message_events=%s status_events=%s has_events=%s processed_changes=%s',
        len(parsed.message_events),
        len(parsed.status_events),
        parsed.has_events,
        processed_changes,
    )

    return {
        'status': 'received',
        'message_events': len(parsed.message_events),
        'status_events': len(parsed.status_events),
        'processed_changes': processed_changes,
    }
