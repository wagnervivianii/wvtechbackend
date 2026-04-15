from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
def healthcheck() -> dict[str, str | int]:
    return {
        "status": "ok",
        "service": "wvtechsolutions-backend",
        "environment": settings.app_env,
        "timezone": settings.app_timezone,
        "port": settings.app_port,
    }