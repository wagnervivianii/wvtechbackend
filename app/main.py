from fastapi import FastAPI

from app.api.routes.admin_auth import router as admin_auth_router
from app.api.routes.admin_availability import router as admin_availability_router
from app.api.routes.availability import router as availability_router
from app.api.routes.bookings import router as bookings_router
from app.api.routes.health import router as health_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health_router)
app.include_router(bookings_router)
app.include_router(availability_router)
app.include_router(admin_auth_router)
app.include_router(admin_availability_router)