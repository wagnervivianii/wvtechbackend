from fastapi import APIRouter

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/health")
def bookings_healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "module": "bookings",
    }