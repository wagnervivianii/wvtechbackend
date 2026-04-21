from __future__ import annotations

import logging

from app.core.config import settings
from app.integrations.meta_whatsapp.client import MetaWhatsAppClient
from app.integrations.meta_whatsapp.exceptions import MetaWhatsAppConfigurationError
from app.integrations.meta_whatsapp.schemas import WhatsAppSendResult
from app.integrations.meta_whatsapp.templates import WhatsAppTemplateBuilder


logger = logging.getLogger(__name__)


class WhatsAppDispatcher:
    """Camada genérica de envio, reutilizável por qualquer domínio."""

    def __init__(self) -> None:
        self._client = MetaWhatsAppClient(
            api_base_url=settings.meta_whatsapp_api_base_url,
            api_version=settings.meta_whatsapp_api_version,
            phone_number_id=settings.meta_whatsapp_phone_number_id,
            access_token=settings.meta_whatsapp_access_token,
            timeout_seconds=settings.meta_whatsapp_request_timeout_seconds,
        )

    def send_template(
        self,
        *,
        recipient_phone: str,
        template_name: str,
        language_code: str | None = None,
        body_values: list[str] | tuple[str, ...] = (),
        button_payloads: list[dict] | tuple[dict, ...] = (),
    ) -> WhatsAppSendResult:
        if not settings.meta_whatsapp_enabled:
            return WhatsAppSendResult(
                message_id=None,
                status='disabled',
                recipient_phone=recipient_phone,
                raw_response={'reason': 'meta_whatsapp_disabled'},
            )

        request_data = WhatsAppTemplateBuilder.build_template_message(
            recipient_phone=recipient_phone,
            template_name=template_name,
            language_code=language_code or settings.meta_whatsapp_default_language_code,
            body_values=body_values,
            button_payloads=button_payloads,
        )

        if settings.meta_whatsapp_dry_run:
            logger.info(
                'WhatsApp dry-run habilitado. template=%s recipient=%s body_values=%s button_payloads=%s',
                template_name,
                recipient_phone,
                body_values,
                button_payloads,
            )
            return WhatsAppSendResult(
                message_id=None,
                status='dry_run',
                recipient_phone=recipient_phone,
                raw_response=request_data.to_payload(),
            )

        self._client.validate_configuration()
        return self._client.send_template_message(request_data)

    def assert_ready(self) -> None:
        if not settings.meta_whatsapp_enabled:
            raise MetaWhatsAppConfigurationError(
                'Integração WhatsApp da Meta desabilitada por configuração.',
            )
        self._client.validate_configuration()
