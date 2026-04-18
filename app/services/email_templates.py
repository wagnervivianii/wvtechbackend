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
    meeting_date: str | None
    meeting_time_label: str | None


SUCCESS_MESSAGE = (
    'Recebemos a confirmação do seu endereço de e-mail e sua solicitação foi encaminhada '
    'para validação da nossa equipe.'
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
    meeting_date = booking.booking_date.strftime('%d/%m/%Y') if booking.booking_date else None
    meeting_time_label = f'{start_text} às {end_text}' if start_text and end_text else None

    if meeting_date and meeting_time_label:
        booking_label = f"{meeting_date} • {meeting_time_label}"
    elif meeting_date:
        booking_label = meeting_date
    else:
        booking_label = f'Solicitação #{booking.id}'

    return BookingEmailContext(
        recipient_name=booking.name,
        booking_label=booking_label,
        subject_summary=booking.subject_summary,
        meeting_date=meeting_date,
        meeting_time_label=meeting_time_label,
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
    info_box_lines: list[str] | None = None,
) -> str:
    body_html = ''.join(
        f'<p style="margin:0 0 16px;color:#cbd5e1;font-size:15px;line-height:1.75;">{escape(line)}</p>'
        for line in body_lines
    )

    info_box_html = ''
    if info_box_lines:
        info_box_html = (
            '<div style="margin:0 0 22px;padding:18px 18px 16px;border-radius:20px;'
            'background:linear-gradient(135deg,rgba(8,47,73,0.92) 0%,rgba(15,23,42,0.92) 100%);'
            'border:1px solid rgba(103,232,249,0.18);box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);">'
            + ''.join(
                f'<p style="margin:0 0 10px;color:#e0f2fe;font-size:14px;line-height:1.7;font-weight:600;">{escape(line)}</p>'
                for line in info_box_lines
            )
            + '</div>'
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
                {info_box_html}
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
    subject = 'Reunião confirmada | WV Tech Solutions'
    intro = (
        f'Olá, {context.recipient_name}. Sua solicitação foi validada e a reunião está confirmada.'
    )
    info_box_lines = []
    if context.meeting_date:
        info_box_lines.append(f'Data da reunião: {context.meeting_date}')
    if context.meeting_time_label:
        info_box_lines.append(f'Horário: {context.meeting_time_label} (horário de Brasília)')

    body_lines = [
        'O link da reunião segue abaixo. Mesmo sem conta Google, você poderá entrar como visitante e será admitido na sala.',
        'Recomendamos acessar o link alguns minutos antes do horário agendado.',
        'Caso tente entrar com muita antecedência, talvez seja necessário aguardar o início da reunião ou a liberação pelo organizador.',
        'Você também receberá os próximos passos pelos canais de contato já informados.',
    ]
    if client_setup_url:
        body_lines.append(
            'Sua área do cliente já está disponível para ativação. Nela ficarão armazenadas as reuniões e as respectivas transcrições durante a vigência do projeto.'
        )
    html = _render_html_shell(
        title='Reunião confirmada',
        eyebrow='WV Tech Solutions',
        intro=intro,
        body_lines=body_lines,
        cta_label='Entrar na reunião' if booking.meet_url else ('Ativar área do cliente' if client_setup_url else None),
        cta_url=booking.meet_url or client_setup_url,
        cta_hint='Guarde esta mensagem. O mesmo link também ficará disponível na sua área do cliente.' if booking.meet_url else ('Guarde este link para acessar seu ambiente de acompanhamento do projeto.' if client_setup_url else None),
        info_box_lines=info_box_lines or None,
    )
    text_parts = [
        f'Olá, {context.recipient_name}.',
        '',
        'Sua solicitação foi validada e a reunião está confirmada.',
    ]
    if context.meeting_date:
        text_parts.append(f'Data da reunião: {context.meeting_date}')
    if context.meeting_time_label:
        text_parts.append(f'Horário: {context.meeting_time_label} (horário de Brasília)')
    if booking.meet_url:
        text_parts.append(f'Link da reunião: {booking.meet_url}')
        text_parts.append('Mesmo sem conta Google, você poderá entrar como visitante e aguardar admissão na sala.')
    text_parts.extend([
        'Recomendamos acessar o link alguns minutos antes do horário agendado.',
        'Caso tente entrar com muita antecedência, talvez seja necessário aguardar o início da reunião ou a liberação pelo organizador.',
        'Você também receberá os próximos passos pelos canais de contato já informados.',
    ])
    if client_setup_url:
        text_parts.extend(['', f'Área do cliente: {client_setup_url}'])
    return EmailContent(subject=subject, html=html, text='\n'.join(text_parts))


def build_booking_cancelled_email(*, booking: BookingRequest, cancellation_reason: str | None = None) -> EmailContent:
    context = build_booking_context(booking)
    subject = 'Reunião cancelada | WV Tech Solutions'
    intro = (
        f'Olá, {context.recipient_name}. Precisamos informar que a reunião vinculada à sua solicitação foi cancelada pela nossa equipe.'
    )
    body_lines = [
        f'Reunião cancelada: {context.booking_label}',
        'Se precisarmos reagendar, faremos um novo contato pelos canais já cadastrados.',
    ]
    if cancellation_reason:
        body_lines.insert(1, f'Motivo informado: {cancellation_reason}')
    html = _render_html_shell(
        title='Reunião cancelada',
        eyebrow='WV Tech Solutions',
        intro=intro,
        body_lines=body_lines,
    )
    text_parts = [
        f'Olá, {context.recipient_name}.',
        '',
        'Precisamos informar que a reunião vinculada à sua solicitação foi cancelada pela nossa equipe.',
        f'Reunião cancelada: {context.booking_label}',
    ]
    if cancellation_reason:
        text_parts.append(f'Motivo informado: {cancellation_reason}')
    text_parts.extend(['', 'Se precisarmos reagendar, faremos um novo contato pelos canais já cadastrados.'])
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