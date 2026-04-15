from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str | int]:
    return {
        "status": "ok",
        "service": "wvtechsolutions-backend",
        "environment": settings.app_env,
        "timezone": settings.app_timezone,
        "port": settings.app_port,
    }