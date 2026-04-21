class MetaWhatsAppError(Exception):
    """Base para falhas da integração com a API do WhatsApp da Meta."""


class MetaWhatsAppConfigurationError(MetaWhatsAppError):
    """Configuração obrigatória ausente ou inválida."""


class MetaWhatsAppRequestError(MetaWhatsAppError):
    """Falha ao enviar requisição para a API externa."""

    def __init__(self, message: str, *, status_code: int | None = None, response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class MetaWhatsAppWebhookVerificationError(MetaWhatsAppError):
    """Falha ao validar o webhook de verificação da Meta."""
