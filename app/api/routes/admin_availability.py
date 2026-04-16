from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_admin_auth
from app.db.session import get_db
from app.schemas.admin_availability import (
    AdminAvailabilityDayItem,
    AdminAvailabilityDayToggleRequest,
    AdminAvailabilityDayUpsertRequest,
    AdminAvailabilityListResponse,
    AdminAvailabilitySlotCreateRequest,
    AdminAvailabilitySlotUpdateRequest,
)
from app.services.admin_availability import (
    create_admin_slot,
    delete_admin_slot,
    list_admin_availability,
    toggle_admin_day,
    update_admin_slot,
    upsert_admin_day,
)

router = APIRouter(
    prefix="/admin/availability",
    tags=["admin-availability"],
    dependencies=[Depends(require_admin_auth)],
)


@router.get("/days", response_model=AdminAvailabilityListResponse)
def get_admin_availability_days(
    db: Session = Depends(get_db),
) -> AdminAvailabilityListResponse:
    return list_admin_availability(db=db)


@router.post("/days", response_model=AdminAvailabilityDayItem)
def post_admin_availability_day(
    payload: AdminAvailabilityDayUpsertRequest,
    db: Session = Depends(get_db),
) -> AdminAvailabilityDayItem:
    return upsert_admin_day(db=db, payload=payload)


@router.patch("/days/{day_id}", response_model=AdminAvailabilityDayItem)
def patch_admin_availability_day(
    day_id: int,
    payload: AdminAvailabilityDayToggleRequest,
    db: Session = Depends(get_db),
) -> AdminAvailabilityDayItem:
    return toggle_admin_day(db=db, day_id=day_id, payload=payload)


@router.post("/days/{day_id}/slots", response_model=AdminAvailabilityDayItem)
def post_admin_availability_slot(
    day_id: int,
    payload: AdminAvailabilitySlotCreateRequest,
    db: Session = Depends(get_db),
) -> AdminAvailabilityDayItem:
    return create_admin_slot(db=db, day_id=day_id, payload=payload)


@router.put("/slots/{slot_id}", response_model=AdminAvailabilityDayItem)
def put_admin_availability_slot(
    slot_id: int,
    payload: AdminAvailabilitySlotUpdateRequest,
    db: Session = Depends(get_db),
) -> AdminAvailabilityDayItem:
    return update_admin_slot(db=db, slot_id=slot_id, payload=payload)


@router.delete("/slots/{slot_id}", response_model=AdminAvailabilityDayItem)
def delete_admin_availability_slot(
    slot_id: int,
    db: Session = Depends(get_db),
) -> AdminAvailabilityDayItem:
    return delete_admin_slot(db=db, slot_id=slot_id)