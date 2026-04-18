from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings
from app.services.email_templates import EmailContent


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


class EmailConfigurationError(RuntimeError):
    pass


def _ensure_smtp_configuration() -> None:
    required = {
        'SMTP_HOST': settings.smtp_host,
        'SMTP_USERNAME': settings.smtp_username,
        'SMTP_PASSWORD': settings.smtp_password,
        'SMTP_FROM_EMAIL': settings.smtp_from_email,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        missing_text = ', '.join(missing)
        raise EmailConfigurationError(
            f'Configuração SMTP incompleta. Variáveis ausentes: {missing_text}.'
        )


def _build_message(*, to_email: str, content: EmailContent) -> EmailMessage:
    message = EmailMessage()
    message['Subject'] = content.subject
    message['From'] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message['To'] = to_email
    message['Reply-To'] = settings.smtp_from_email
    message.set_content(content.text)
    message.add_alternative(content.html, subtype='html')
    return message


def _deliver_via_smtp(message: EmailMessage) -> None:
    _ensure_smtp_configuration()

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.ehlo()
            if settings.smtp_use_tls:
                server.starttls()
                server.ehlo()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except Exception as exc:  # pragma: no cover - depends on environment
        raise EmailDeliveryError('Falha ao enviar email via SMTP.') from exc


def _deliver_via_log(*, to_email: str, content: EmailContent) -> None:
    logger.info(
        'EMAIL_DELIVERY_MODE=log | to=%s | subject=%s | html=%s',
        to_email,
        content.subject,
        content.html,
    )


def send_email(*, to_email: str, content: EmailContent) -> None:
    delivery_mode = settings.email_delivery_mode
    message = _build_message(to_email=to_email, content=content)

    if delivery_mode == 'log':
        _deliver_via_log(to_email=to_email, content=content)
        return

    if delivery_mode != 'smtp':
        raise EmailConfigurationError(
            f'Modo de entrega de email inválido: {delivery_mode!r}. Use "log" ou "smtp".'
        )

    _deliver_via_smtp(message)