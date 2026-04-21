from dataclasses import dataclass, field

from app.integrations.meta_whatsapp.types import (
    WhatsAppTemplateButtonPayload,
    WhatsAppTemplateTextParameter,
)


@dataclass(frozen=True, slots=True)
class WhatsAppTemplateMessageRequest:
    recipient_phone: str
    template_name: str
    language_code: str = 'pt_BR'
    body_parameters: tuple[WhatsAppTemplateTextParameter, ...] = ()
    button_payloads: tuple[WhatsAppTemplateButtonPayload, ...] = ()

    def to_payload(self) -> dict:
        components: list[dict] = []

        if self.body_parameters:
            components.append(
                {
                    'type': 'body',
                    'parameters': [
                        {
                            'type': 'text',
                            'text': item.text,
                        }
                        for item in self.body_parameters
                    ],
                }
            )

        for item in self.button_payloads:
            components.append(
                {
                    'type': 'button',
                    'sub_type': item.subtype,
                    'index': str(item.index),
                    'parameters': [
                        {
                            'type': 'payload',
                            'payload': item.payload,
                        }
                    ],
                }
            )

        template_payload = {
            'name': self.template_name,
            'language': {
                'code': self.language_code,
            },
        }

        if components:
            template_payload['components'] = components

        return {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': self.recipient_phone,
            'type': 'template',
            'template': template_payload,
        }


@dataclass(frozen=True, slots=True)
class WhatsAppSendResult:
    message_id: str | None
    status: str
    recipient_phone: str
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WhatsAppWebhookParseResult:
    message_events: tuple = ()
    status_events: tuple = ()
    raw_payload: dict = field(default_factory=dict)

    @property
    def has_events(self) -> bool:
        return bool(self.message_events or self.status_events)
