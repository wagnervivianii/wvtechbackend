from app.integrations.meta_whatsapp.schemas import WhatsAppTemplateMessageRequest
from app.integrations.meta_whatsapp.types import (
    WhatsAppTemplateButtonPayload,
    WhatsAppTemplateTextParameter,
)


class WhatsAppTemplateBuilder:
    """Builder genérico para mensagens template da Meta."""

    @staticmethod
    def build_template_message(
        *,
        recipient_phone: str,
        template_name: str,
        language_code: str,
        body_values: list[str] | tuple[str, ...] = (),
        button_payloads: list[dict] | tuple[dict, ...] = (),
    ) -> WhatsAppTemplateMessageRequest:
        return WhatsAppTemplateMessageRequest(
            recipient_phone=recipient_phone,
            template_name=template_name,
            language_code=language_code,
            body_parameters=tuple(
                WhatsAppTemplateTextParameter(text=value)
                for value in body_values
            ),
            button_payloads=tuple(
                WhatsAppTemplateButtonPayload(
                    subtype=str(item.get('subtype', 'quick_reply')),
                    index=int(item.get('index', 0)),
                    payload=str(item.get('payload', '')),
                )
                for item in button_payloads
            ),
        )
