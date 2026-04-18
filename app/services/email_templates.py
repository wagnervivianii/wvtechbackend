from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import urlencode

from app.core.config import settings
from app.models.booking_request import BookingRequest


@dataclass(frozen=True, slots=True)
class EmailContent:
    subject: str
    html: str
    text: str


@dataclass(frozen=True, slots=True)
class BookingEmailContext:
    recipient_name: str
    booking_label: str
    subject_summary: str


SUCCESS_MESSAGE = (
    'Recebemos a confirmação do seu endereço de e-mail e sua solicitação foi encaminhada '
    'para validação da nossa equipe.'
)

SUCCESS_NEXT_STEPS = (
    'Após a análise, você receberá a confirmação da reunião, o link do Google Meet agendado, '
    'uma mensagem de confirmação via WhatsApp e o acesso à sua área do cliente, onde ficarão '
    'disponíveis os registros das reuniões e suas transcrições durante a vigência do projeto.'
)


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip('/')
    normalized_path = path if path.startswith('/') else f'/{path}'
    return f'{base}{normalized_path}'


def build_public_asset_url(asset_path: str) -> str:
    return _join_url(settings.public_app_base_url, asset_path)


def build_client_setup_url(setup_path: str | None) -> str | None:
    if not setup_path:
        return None
    return _join_url(settings.client_portal_base_url, setup_path)


def build_confirmation_result_url(*, status: str, booking_id: int | None = None) -> str:
    path = settings.booking_confirmation_result_path_prefix.rstrip('/')
    query_params: dict[str, str] = {'status': status}
    if booking_id is not None:
        query_params['booking_id'] = str(booking_id)
    return f"{_join_url(settings.public_app_base_url, path)}?{urlencode(query_params)}"


def build_confirmation_action_url(raw_token: str) -> str:
    return _join_url(
        settings.booking_confirmation_action_base_url,
        f"/bookings/confirm/{raw_token}",
    )


def build_booking_context(booking: BookingRequest) -> BookingEmailContext:
    start_text = booking.start_time.strftime('%H:%M') if booking.start_time else None
    end_text = booking.end_time.strftime('%H:%M') if booking.end_time else None

    if booking.booking_date and start_text and end_text:
        booking_label = f"{booking.booking_date.strftime('%d/%m/%Y')} • {start_text} às {end_text}"
    elif booking.booking_date:
        booking_label = booking.booking_date.strftime('%d/%m/%Y')
    else:
        booking_label = f'Solicitação #{booking.id}'

    return BookingEmailContext(
        recipient_name=booking.name,
        booking_label=booking_label,
        subject_summary=booking.subject_summary,
    )


def _render_html_shell(
    *,
    title: str,
    eyebrow: str,
    intro: str,
    body_lines: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    cta_hint: str | None = None,
) -> str:
    body_html = ''.join(
        f'<p style="margin:0 0 16px;color:#cbd5e1;font-size:15px;line-height:1.75;">{escape(line)}</p>'
        for line in body_lines
    )

    cta_html = ''
    if cta_label and cta_url:
        cta_html = f'''
          <div style="margin:28px 0 18px;">
            <a href="{escape(cta_url)}" style="display:inline-block;border-radius:999px;background:linear-gradient(135deg,#22d3ee 0%,#38bdf8 100%);padding:14px 22px;color:#082f49;font-size:14px;font-weight:700;text-decoration:none;box-shadow:0 10px 28px rgba(34,211,238,0.35);">{escape(cta_label)}</a>
          </div>
        '''

    hint_html = ''
    if cta_hint:
        hint_html = (
            f'<p style="margin:0 0 18px;color:#94a3b8;font-size:13px;line-height:1.7;">{escape(cta_hint)}</p>'
        )

    return f'''<!doctype html>
<html lang="pt-BR">
  <body style="margin:0;padding:0;background:#0f172a;font-family:Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:linear-gradient(180deg,#0f172a 0%,#082f49 100%);padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;border:1px solid rgba(103,232,249,0.18);border-radius:28px;overflow:hidden;background:#0f172a;box-shadow:0 24px 60px rgba(2,6,23,0.45);">
            <tr>
              <td style="padding:30px 28px 18px;background:linear-gradient(135deg,#0f172a 0%,#0c4a6e 52%,#1e3a8a 100%);border-bottom:1px solid rgba(148,163,184,0.16);">
                <div style="display:inline-block;border-radius:999px;background:rgba(255,255,255,0.08);border:1px solid rgba(103,232,249,0.22);padding:8px 14px;color:#67e8f9;font-size:12px;font-weight:700;letter-spacing:0.24em;text-transform:uppercase;">
                  {escape(eyebrow)}
                </div>
                <div style="margin-top:16px;color:#f8fafc;font-size:30px;font-weight:700;line-height:1.12;">{escape(title)}</div>
                <div style="margin-top:10px;color:#bae6fd;font-size:14px;line-height:1.7;">Dados, automação e percepção de negócio</div>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 28px 10px;background:linear-gradient(180deg,rgba(15,23,42,0.98) 0%,rgba(8,47,73,0.96) 100%);">
                <p style="margin:0 0 18px;color:#e2e8f0;font-size:16px;line-height:1.8;">{escape(intro)}</p>
                {body_html}
                {cta_html}
                {hint_html}
              </td>
            </tr>
            <tr>
              <td style="padding:10px 28px 28px;background:#0f172a;">
                <div style="margin-top:10px;padding-top:20px;border-top:1px solid rgba(148,163,184,0.16);">
                  <p style="margin:0 0 6px;color:#f8fafc;font-size:15px;font-weight:700;">WV Tech Solutions</p>
                  <p style="margin:0 0 4px;color:#e2e8f0;font-size:14px;font-weight:700;">{escape(settings.email_signature_name)}</p>
                  <p style="margin:0 0 8px;color:#94a3b8;font-size:13px;line-height:1.7;">{escape(settings.email_signature_phone)}</p>
                  <p style="margin:0;color:#67e8f9;font-size:12px;line-height:1.7;">Comunicação oficial da WV Tech Solutions</p>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>'''


def build_confirmation_request_email(*, booking: BookingRequest, confirmation_url: str) -> EmailContent:
    context = build_booking_context(booking)
    subject = 'Confirme seu e-mail para prosseguir com a solicitação | WV Tech Solutions'
    intro = f'Olá, {context.recipient_name}. Recebemos sua solicitação de reunião e precisamos validar o seu endereço de e-mail antes de encaminhá-la para análise.'
    body_lines = [
        f'Horário solicitado: {context.booking_label}',
        f'Assunto informado: {context.subject_summary}',
        'Após a confirmação, sua solicitação seguirá para validação da nossa equipe.',
    ]
    html = _render_html_shell(
        title='Confirmação de e-mail',
        eyebrow='WV Tech Solutions',
        intro=intro,
        body_lines=body_lines,
        cta_label='Confirmar e-mail',
        cta_url=confirmation_url,
        cta_hint='Se você não reconhece esta solicitação, basta desconsiderar esta mensagem.',
    )
    text = (
        f'Olá, {context.recipient_name}.\n\n'
        'Recebemos sua solicitação de reunião e precisamos validar o seu endereço de e-mail.\n'
        f'Horário solicitado: {context.booking_label}\n'
        f'Assunto informado: {context.subject_summary}\n\n'
        f'Confirme seu e-mail neste link: {confirmation_url}\n\n'
        'Se você não reconhece esta solicitação, basta desconsiderar esta mensagem.'
    )
    return EmailContent(subject=subject, html=html, text=text)


def build_booking_approved_email(*, booking: BookingRequest, client_setup_url: str | None) -> EmailContent:
    context = build_booking_context(booking)
    subject = 'Solicitação aprovada | WV Tech Solutions'
    intro = (
        f'Olá, {context.recipient_name}. Sua solicitação foi validada e a reunião está confirmada.'
    )
    body_lines = [
        f'Reunião confirmada para: {context.booking_label}',
        'Você receberá a confirmação complementar via WhatsApp com os próximos passos do atendimento.',
    ]
    if booking.meet_url:
        body_lines.append(f'Link do Google Meet: {booking.meet_url}')
    if client_setup_url:
        body_lines.append(
            'Sua área do cliente já está disponível para ativação. Nela ficarão armazenadas as reuniões e as respectivas transcrições durante a vigência do projeto.'
        )
    html = _render_html_shell(
        title='Solicitação aprovada',
        eyebrow='WV Tech Solutions',
        intro=intro,
        body_lines=body_lines,
        cta_label='Ativar área do cliente' if client_setup_url else None,
        cta_url=client_setup_url,
        cta_hint='Guarde este link para acessar seu ambiente de acompanhamento do projeto.' if client_setup_url else None,
    )
    text_parts = [
        f'Olá, {context.recipient_name}.',
        '',
        'Sua solicitação foi validada e a reunião está confirmada.',
        f'Reunião confirmada para: {context.booking_label}',
    ]
    if booking.meet_url:
        text_parts.append(f'Link do Google Meet: {booking.meet_url}')
    text_parts.append('Você receberá a confirmação complementar via WhatsApp com os próximos passos do atendimento.')
    if client_setup_url:
        text_parts.extend([
            '',
            f'Ative sua área do cliente: {client_setup_url}',
        ])
    return EmailContent(subject=subject, html=html, text='\n'.join(text_parts))


def build_booking_rejected_email(*, booking: BookingRequest) -> EmailContent:
    context = build_booking_context(booking)
    subject = 'Atualização da sua solicitação | WV Tech Solutions'
    intro = (
        f'Olá, {context.recipient_name}. Concluímos a análise da sua solicitação e, neste momento, não conseguiremos prosseguir com o agendamento solicitado.'
    )
    body_lines = [
        f'Solicitação analisada: {context.booking_label}',
    ]
    if booking.rejection_reason:
        body_lines.append(f'Motivo informado: {booking.rejection_reason}')
    body_lines.append(
        'Agradecemos pelo seu contato. Se houver nova disponibilidade ou necessidade de reabertura do atendimento, retornaremos pelos canais registrados.'
    )
    html = _render_html_shell(
        title='Solicitação analisada',
        eyebrow='WV Tech Solutions',
        intro=intro,
        body_lines=body_lines,
    )
    text_parts = [
        f'Olá, {context.recipient_name}.',
        '',
        'Concluímos a análise da sua solicitação e, neste momento, não conseguiremos prosseguir com o agendamento solicitado.',
        f'Solicitação analisada: {context.booking_label}',
    ]
    if booking.rejection_reason:
        text_parts.append(f'Motivo informado: {booking.rejection_reason}')
    text_parts.extend([
        '',
        'Agradecemos pelo seu contato. Se houver nova disponibilidade ou necessidade de reabertura do atendimento, retornaremos pelos canais registrados.',
    ])
    return EmailContent(subject=subject, html=html, text='\n'.join(text_parts))