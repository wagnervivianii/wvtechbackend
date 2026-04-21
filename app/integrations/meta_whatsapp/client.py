from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.integrations.meta_whatsapp.exceptions import (
    MetaWhatsAppConfigurationError,
    MetaWhatsAppRequestError,
)
from app.integrations.meta_whatsapp.schemas import (
    WhatsAppSendResult,
    WhatsAppTemplateMessageRequest,
)


class MetaWhatsAppClient:
    def __init__(
        self,
        *,
        api_base_url: str,
        api_version: str,
        phone_number_id: str,
        access_token: str,
        timeout_seconds: float,
    ) -> None:
        self._api_base_url = api_base_url.rstrip('/')
        self._api_version = api_version.strip().strip('/')
        self._phone_number_id = phone_number_id.strip()
        self._access_token = access_token.strip()
        self._timeout_seconds = timeout_seconds

    def validate_configuration(self) -> None:
        if not self._api_base_url:
            raise MetaWhatsAppConfigurationError('API base URL da Meta não configurada.')
        if not self._api_version:
            raise MetaWhatsAppConfigurationError('Versão da API da Meta não configurada.')
        if not self._phone_number_id:
            raise MetaWhatsAppConfigurationError('Phone Number ID da Meta não configurado.')
        if not self._access_token:
            raise MetaWhatsAppConfigurationError('Access token da Meta não configurado.')

    def send_template_message(self, request_data: WhatsAppTemplateMessageRequest) -> WhatsAppSendResult:
        self.validate_configuration()

        payload = request_data.to_payload()
        response_data = self._post_json(
            f'/{self._api_version}/{self._phone_number_id}/messages',
            payload,
        )

        messages = response_data.get('messages') or []
        first_message = messages[0] if messages else {}

        return WhatsAppSendResult(
            message_id=first_message.get('id'),
            status='accepted',
            recipient_phone=request_data.recipient_phone,
            raw_response=response_data,
        )

    def _post_json(self, path: str, payload: dict) -> dict:
        url = f'{self._api_base_url}{path}'
        request = Request(
            url=url,
            data=json.dumps(payload).encode('utf-8'),
            method='POST',
            headers={
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json',
            },
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                content = response.read().decode('utf-8')
        except HTTPError as exc:
            response_body = exc.read().decode('utf-8', errors='ignore')
            raise MetaWhatsAppRequestError(
                'A API da Meta respondeu com erro ao enviar mensagem WhatsApp.',
                status_code=exc.code,
                response_body=response_body,
            ) from exc
        except URLError as exc:
            raise MetaWhatsAppRequestError(
                'Não foi possível alcançar a API da Meta no envio do WhatsApp.',
            ) from exc

        if not content:
            return {}

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise MetaWhatsAppRequestError(
                'A API da Meta retornou um payload inválido no envio do WhatsApp.',
                response_body=content,
            ) from exc
