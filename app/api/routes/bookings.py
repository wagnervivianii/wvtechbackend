from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.bookings import BookingRequestCreate, BookingRequestCreated
from app.services.booking_confirmations import (
    CONSUMED_CONFIRMATION_DETAIL,
    build_confirmation_result_url,
    confirm_booking_request_email,
)
from app.services.booking_requests import create_booking_request

router = APIRouter(
    prefix="/bookings",
    tags=["bookings"],
)


@router.post("/requests", response_model=BookingRequestCreated)
def create_booking_request_route(
    payload: BookingRequestCreate,
    db: Session = Depends(get_db),
) -> BookingRequestCreated:
    return create_booking_request(db=db, payload=payload)


@router.get("/confirm/{raw_token}")
def confirm_booking_request_email_route(
    raw_token: str,
    db: Session = Depends(get_db),
):
    try:
        result = confirm_booking_request_email(db=db, raw_token=raw_token)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return RedirectResponse(
                url=build_confirmation_result_url(result_status="invalid"),
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )

        if exc.status_code == status.HTTP_410_GONE:
            if exc.detail == CONSUMED_CONFIRMATION_DETAIL:
                return Response(status_code=status.HTTP_204_NO_CONTENT)

            return RedirectResponse(
                url=build_confirmation_result_url(result_status="expired"),
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )

        return RedirectResponse(
            url=build_confirmation_result_url(result_status="error"),
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    return RedirectResponse(
        url=build_confirmation_result_url(
            result_status=result.result_status,
            booking_id=result.booking_id,
        ),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )