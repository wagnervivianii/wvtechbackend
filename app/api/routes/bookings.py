from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.bookings import (
    BookingEmailConfirmationResponse,
    BookingRequestCreate,
    BookingRequestCreated,
    BookingSlotListResponse,
)
from app.services.booking_confirmations import (
    CONSUMED_CONFIRMATION_DETAIL,
    build_confirmation_result_url,
    confirm_booking_request_email,
)
from app.services.booking_requests import create_booking_request
from app.services.booking_slots import list_dynamic_booking_slots

router = APIRouter(prefix='/bookings', tags=['bookings'])


@router.get('/health')
def bookings_healthcheck() -> dict[str, str]:
    return {
        'status': 'ok',
        'module': 'bookings',
    }


@router.get('/slots', response_model=BookingSlotListResponse)
def list_booking_slots(
    db: Session = Depends(get_db),
) -> BookingSlotListResponse:
    return BookingSlotListResponse(slots=list_dynamic_booking_slots(db=db))


@router.post('/requests', response_model=BookingRequestCreated)
def create_booking_request_route(
    payload: BookingRequestCreate,
    db: Session = Depends(get_db),
) -> BookingRequestCreated:
    return create_booking_request(db=db, payload=payload)


@router.get('/confirm/{token}/status', response_model=BookingEmailConfirmationResponse)
def confirm_booking_request_status_route(
    token: str,
    db: Session = Depends(get_db),
) -> BookingEmailConfirmationResponse:
    return confirm_booking_request_email(db=db, raw_token=token)


@router.get('/confirm/{token}', include_in_schema=False)
def confirm_booking_request_route(
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        result = confirm_booking_request_email(db=db, raw_token=token)
        redirect_url = build_confirmation_result_url(
            result_status=result.result_status,
            booking_id=result.booking_id,
        )
        return RedirectResponse(url=redirect_url, status_code=303)
    except HTTPException as exc:
        if exc.status_code == 410 and exc.detail == CONSUMED_CONFIRMATION_DETAIL:
            return Response(status_code=204)

        if exc.status_code == 404:
            result_status = 'invalid'
        elif exc.status_code == 410:
            result_status = 'expired'
        elif exc.status_code == 409:
            result_status = 'already-confirmed'
        else:
            result_status = 'error'

        redirect_url = build_confirmation_result_url(result_status=result_status)
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception:
        redirect_url = build_confirmation_result_url(result_status='error')
        return RedirectResponse(url=redirect_url, status_code=303)