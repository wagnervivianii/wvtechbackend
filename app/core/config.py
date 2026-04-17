from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "WV Tech Solutions API")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_timezone: str = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/wvtechsolutions",
    )
    admin_username: str = os.getenv("ADMIN_USERNAME", "").strip()
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")
    admin_token_secret: str = os.getenv("ADMIN_TOKEN_SECRET", "").strip()
    admin_token_ttl_minutes: int = int(os.getenv("ADMIN_TOKEN_TTL_MINUTES", "480"))
    admin_token_issuer: str = os.getenv(
        "ADMIN_TOKEN_ISSUER",
        "wvtechsolutions-admin",
    )
    booking_confirmation_ttl_hours: int = int(
        os.getenv("BOOKING_CONFIRMATION_TTL_HOURS", "48")
    )
    booking_confirmation_path_prefix: str = os.getenv(
        "BOOKING_CONFIRMATION_PATH_PREFIX",
        "/agendar/confirmar",
    ).strip() or "/agendar/confirmar"


settings = Settings()