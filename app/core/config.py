from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "WV Tech Solutions API")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_timezone: str = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")


settings = Settings()
