from dataclasses import dataclass, field
from enum import StrEnum


class WhatsAppMessageDirection(StrEnum):
    INBOUND = 'inbound'
    OUTBOUND = 'outbound'


class WhatsAppEventKind(StrEnum):
    MESSAGE = 'message'
    STATUS = 'status'
    UNKNOWN = 'unknown'


@dataclass(frozen=True, slots=True)
class WhatsAppTemplateTextParameter:
    text: str


@dataclass(frozen=True, slots=True)
class WhatsAppTemplateButtonPayload:
    subtype: str = 'quick_reply'
    index: int = 0
    payload: str = ''


@dataclass(frozen=True, slots=True)
class WhatsAppWebhookMessageEvent:
    wa_id: str | None
    message_id: str | None
    from_phone: str | None
    message_type: str | None
    text_body: str | None
    direction: WhatsAppMessageDirection = WhatsAppMessageDirection.INBOUND
    event_kind: WhatsAppEventKind = WhatsAppEventKind.MESSAGE
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WhatsAppWebhookStatusEvent:
    wa_id: str | None
    message_id: str | None
    status: str | None
    recipient_id: str | None
    conversation_id: str | None
    pricing_category: str | None
    event_kind: WhatsAppEventKind = WhatsAppEventKind.STATUS
    raw: dict = field(default_factory=dict)
