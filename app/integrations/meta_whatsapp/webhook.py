import hashlib
import hmac

from app.integrations.meta_whatsapp.exceptions import MetaWhatsAppWebhookVerificationError
import hashlib
import hmac

from app.integrations.meta_whatsapp.schemas import WhatsAppWebhookParseResult
import hashlib
import hmac

from app.integrations.meta_whatsapp.types import (
    WhatsAppWebhookMessageEvent,
    WhatsAppWebhookStatusEvent,
)


class MetaWebhookVerifier:
    @staticmethod
    def verify_subscription(*, mode: str | None, verify_token: str | None, challenge: str | None, expected_token: str) -> str:
        if mode != 'subscribe':
            raise MetaWhatsAppWebhookVerificationError('Modo de verificação inválido para o webhook da Meta.')
        if not expected_token:
            raise MetaWhatsAppWebhookVerificationError('Token esperado do webhook da Meta não configurado.')
        if verify_token != expected_token:
            raise MetaWhatsAppWebhookVerificationError('Token de verificação do webhook da Meta não confere.')
        if not challenge:
            raise MetaWhatsAppWebhookVerificationError('Challenge do webhook da Meta ausente.')
        return challenge

    @staticmethod
    def verify_payload_signature(*, raw_body: bytes, signature_header: str | None, app_secret: str) -> None:
        if not app_secret:
            return

        if not signature_header or not signature_header.startswith('sha256='):
            raise MetaWhatsAppWebhookVerificationError('Assinatura do webhook da Meta ausente ou inválida.')

        expected_signature = hmac.new(
            app_secret.encode('utf-8'),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        provided_signature = signature_header.removeprefix('sha256=').strip()

        if not hmac.compare_digest(expected_signature, provided_signature):
            raise MetaWhatsAppWebhookVerificationError('Assinatura do webhook da Meta não confere.')


class MetaWebhookParser:
    @staticmethod
    def parse(payload: dict | None) -> WhatsAppWebhookParseResult:
        if not payload:
            return WhatsAppWebhookParseResult(raw_payload={})

        message_events: list[WhatsAppWebhookMessageEvent] = []
        status_events: list[WhatsAppWebhookStatusEvent] = []

        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})

                contacts_by_wa_id = {
                    item.get('wa_id'): item
                    for item in value.get('contacts', [])
                    if item.get('wa_id')
                }

                for message in value.get('messages', []):
                    from_phone = message.get('from')
                    contact = contacts_by_wa_id.get(from_phone) if from_phone else None
                    text_payload = message.get('text') or {}
                    text_body = text_payload.get('body')

                    message_events.append(
                        WhatsAppWebhookMessageEvent(
                            wa_id=(contact.get('wa_id') if contact else from_phone),
                            message_id=message.get('id'),
                            from_phone=from_phone,
                            message_type=message.get('type'),
                            text_body=text_body,
                            raw=message,
                        )
                    )

                for status_item in value.get('statuses', []):
                    conversation = status_item.get('conversation') or {}
                    pricing = status_item.get('pricing') or {}
                    status_events.append(
                        WhatsAppWebhookStatusEvent(
                            wa_id=status_item.get('recipient_id'),
                            message_id=status_item.get('id'),
                            status=status_item.get('status'),
                            recipient_id=status_item.get('recipient_id'),
                            conversation_id=conversation.get('id'),
                            pricing_category=pricing.get('category'),
                            raw=status_item,
                        )
                    )

        return WhatsAppWebhookParseResult(
            message_events=tuple(message_events),
            status_events=tuple(status_events),
            raw_payload=payload,
        )
