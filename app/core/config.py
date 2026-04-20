from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / '.env'

load_dotenv(ENV_FILE)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv('APP_NAME', 'WV Tech Solutions API')
    app_env: str = os.getenv('APP_ENV', 'development')
    app_host: str = os.getenv('APP_HOST', '127.0.0.1')
    app_port: int = int(os.getenv('APP_PORT', '8000'))
    app_timezone: str = os.getenv('APP_TIMEZONE', 'America/Sao_Paulo')
    database_url: str = os.getenv(
        'DATABASE_URL',
        'postgresql+psycopg://postgres:postgres@localhost:5432/wvtechsolutions',
    )
    admin_username: str = os.getenv('ADMIN_USERNAME', '').strip()
    admin_password: str = os.getenv('ADMIN_PASSWORD', '')
    admin_token_secret: str = os.getenv('ADMIN_TOKEN_SECRET', '').strip()
    admin_token_ttl_minutes: int = int(os.getenv('ADMIN_TOKEN_TTL_MINUTES', '480'))
    admin_token_issuer: str = os.getenv('ADMIN_TOKEN_ISSUER', 'wvtechsolutions-admin')

    client_auth_token_secret: str = os.getenv(
        'CLIENT_AUTH_TOKEN_SECRET',
        os.getenv('ADMIN_TOKEN_SECRET', ''),
    ).strip()
    client_auth_token_ttl_minutes: int = int(
        os.getenv('CLIENT_AUTH_TOKEN_TTL_MINUTES', '720')
    )
    client_auth_token_issuer: str = os.getenv(
        'CLIENT_AUTH_TOKEN_ISSUER',
        'wvtechsolutions-client',
    ).strip() or 'wvtechsolutions-client'
    client_google_state_ttl_minutes: int = int(
        os.getenv('CLIENT_GOOGLE_STATE_TTL_MINUTES', '15')
    )
    client_password_reset_ttl_minutes: int = int(
        os.getenv('CLIENT_PASSWORD_RESET_TTL_MINUTES', '60')
    )
    client_password_hash_iterations: int = int(
        os.getenv('CLIENT_PASSWORD_HASH_ITERATIONS', '390000')
    )

    booking_confirmation_ttl_hours: int = int(
        os.getenv('BOOKING_CONFIRMATION_TTL_HOURS', '48')
    )
    booking_confirmation_path_prefix: str = os.getenv(
        'BOOKING_CONFIRMATION_PATH_PREFIX',
        '/bookings/confirm',
    ).strip() or '/bookings/confirm'
    booking_confirmation_result_path_prefix: str = os.getenv(
        'BOOKING_CONFIRMATION_RESULT_PATH_PREFIX',
        '/agendar/confirmacao',
    ).strip() or '/agendar/confirmacao'

    email_delivery_mode: str = os.getenv('EMAIL_DELIVERY_MODE', 'log').strip().lower() or 'log'
    smtp_host: str = os.getenv('SMTP_HOST', '').strip()
    smtp_port: int = int(os.getenv('SMTP_PORT', '587'))
    smtp_username: str = os.getenv('SMTP_USERNAME', '').strip()
    smtp_password: str = os.getenv('SMTP_PASSWORD', '')
    smtp_use_tls: bool = _get_bool('SMTP_USE_TLS', True)
    smtp_from_email: str = os.getenv('SMTP_FROM_EMAIL', '').strip()
    smtp_from_name: str = os.getenv('SMTP_FROM_NAME', 'WV Tech Solutions').strip() or 'WV Tech Solutions'

    public_app_base_url: str = os.getenv('PUBLIC_APP_BASE_URL', 'http://127.0.0.1:5173').strip().rstrip('/')
    booking_confirmation_action_base_url: str = os.getenv(
        'BOOKING_CONFIRMATION_ACTION_BASE_URL',
        'http://127.0.0.1:8000',
    ).strip().rstrip('/')
    client_portal_base_url: str = os.getenv(
        'CLIENT_PORTAL_BASE_URL',
        'http://127.0.0.1:5173',
    ).strip().rstrip('/')
    client_login_path_prefix: str = os.getenv(
        'CLIENT_LOGIN_PATH_PREFIX',
        '/cliente/login',
    ).strip() or '/cliente/login'
    client_setup_path_prefix: str = os.getenv(
        'CLIENT_SETUP_PATH_PREFIX',
        '/cliente/ativacao',
    ).strip() or '/cliente/ativacao'
    client_password_reset_path_prefix: str = os.getenv(
        'CLIENT_PASSWORD_RESET_PATH_PREFIX',
        '/cliente/redefinir-senha',
    ).strip() or '/cliente/redefinir-senha'
    client_forgot_password_path_prefix: str = os.getenv(
        'CLIENT_FORGOT_PASSWORD_PATH_PREFIX',
        '/cliente/esqueci-senha',
    ).strip() or '/cliente/esqueci-senha'
    client_portal_home_path_prefix: str = os.getenv(
        'CLIENT_PORTAL_HOME_PATH_PREFIX',
        '/cliente',
    ).strip() or '/cliente'
    client_google_callback_path_prefix: str = os.getenv(
        'CLIENT_GOOGLE_CALLBACK_PATH_PREFIX',
        '/cliente/google/callback',
    ).strip() or '/cliente/google/callback'

    google_oauth_client_id: str = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip()
    google_oauth_client_secret: str = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
    google_oauth_refresh_token: str = os.getenv('GOOGLE_OAUTH_REFRESH_TOKEN', '').strip()
    google_oauth_token_url: str = os.getenv(
        'GOOGLE_OAUTH_TOKEN_URL',
        'https://oauth2.googleapis.com/token',
    ).strip() or 'https://oauth2.googleapis.com/token'
    google_calendar_id: str = os.getenv('GOOGLE_CALENDAR_ID', 'primary').strip() or 'primary'
    google_calendar_send_updates: str = os.getenv('GOOGLE_CALENDAR_SEND_UPDATES', 'none').strip() or 'none'
    google_calendar_event_summary_prefix: str = os.getenv(
        'GOOGLE_CALENDAR_EVENT_SUMMARY_PREFIX',
        'WV Tech Solutions | Reunião',
    ).strip() or 'WV Tech Solutions | Reunião'
    google_meet_retry_attempts: int = int(os.getenv('GOOGLE_MEET_RETRY_ATTEMPTS', '6'))
    google_meet_retry_delay_seconds: float = float(os.getenv('GOOGLE_MEET_RETRY_DELAY_SECONDS', '1.0'))


    google_meet_auto_artifacts_enabled: bool = _get_bool(
        'GOOGLE_MEET_AUTO_ARTIFACTS_ENABLED',
        True,
    )
    google_meet_auto_recording_enabled: bool = _get_bool(
        'GOOGLE_MEET_AUTO_RECORDING_ENABLED',
        True,
    )
    google_meet_auto_transcription_enabled: bool = _get_bool(
        'GOOGLE_MEET_AUTO_TRANSCRIPTION_ENABLED',
        True,
    )
    google_meet_auto_smart_notes_enabled: bool = _get_bool(
        'GOOGLE_MEET_AUTO_SMART_NOTES_ENABLED',
        True,
    )
    google_artifacts_auto_sync_enabled: bool = _get_bool(
        'GOOGLE_ARTIFACTS_AUTO_SYNC_ENABLED',
        True,
    )
    google_artifacts_auto_sync_max_meetings_per_request: int = int(
        os.getenv('GOOGLE_ARTIFACTS_AUTO_SYNC_MAX_MEETINGS_PER_REQUEST', '3')
    )

    google_drive_clients_root_folder_id: str = os.getenv(
        'GOOGLE_DRIVE_CLIENTS_ROOT_FOLDER_ID',
        '',
    ).strip()
    google_drive_auto_create_client_folders: bool = _get_bool(
        'GOOGLE_DRIVE_AUTO_CREATE_CLIENT_FOLDERS',
        True,
    )

    client_google_oauth_client_id: str = os.getenv(
        'CLIENT_GOOGLE_OAUTH_CLIENT_ID',
        os.getenv('GOOGLE_OAUTH_CLIENT_ID', ''),
    ).strip()
    client_google_oauth_client_secret: str = os.getenv(
        'CLIENT_GOOGLE_OAUTH_CLIENT_SECRET',
        os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', ''),
    )
    client_google_oauth_authorize_url: str = os.getenv(
        'CLIENT_GOOGLE_OAUTH_AUTHORIZE_URL',
        'https://accounts.google.com/o/oauth2/v2/auth',
    ).strip() or 'https://accounts.google.com/o/oauth2/v2/auth'
    client_google_oauth_token_url: str = os.getenv(
        'CLIENT_GOOGLE_OAUTH_TOKEN_URL',
        'https://oauth2.googleapis.com/token',
    ).strip() or 'https://oauth2.googleapis.com/token'
    client_google_oauth_userinfo_url: str = os.getenv(
        'CLIENT_GOOGLE_OAUTH_USERINFO_URL',
        'https://openidconnect.googleapis.com/v1/userinfo',
    ).strip() or 'https://openidconnect.googleapis.com/v1/userinfo'
    client_google_oauth_scope: str = os.getenv(
        'CLIENT_GOOGLE_OAUTH_SCOPE',
        'openid email profile',
    ).strip() or 'openid email profile'

    email_logo_path: str = os.getenv('EMAIL_LOGO_PATH', '/imagens/logo.png').strip() or '/imagens/logo.png'
    email_signature_image_path: str = os.getenv(
        'EMAIL_SIGNATURE_IMAGE_PATH',
        '/imagens/Assinatura_mail.png',
    ).strip() or '/imagens/Assinatura_mail.png'
    email_signature_name: str = os.getenv('EMAIL_SIGNATURE_NAME', 'Wagner Viviani').strip() or 'Wagner Viviani'
    email_signature_phone: str = os.getenv('EMAIL_SIGNATURE_PHONE', '11 99688-4509').strip() or '11 99688-4509'


settings = Settings()