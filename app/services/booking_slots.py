STATIC_BOOKING_SLOTS = [
    {
        "id": "slot-1",
        "date": "2026-04-20",
        "start_time": "09:00",
        "end_time": "09:30",
        "label": "20/04/2026 • 09:00 às 09:30",
    },
    {
        "id": "slot-2",
        "date": "2026-04-20",
        "start_time": "10:00",
        "end_time": "10:30",
        "label": "20/04/2026 • 10:00 às 10:30",
    },
    {
        "id": "slot-3",
        "date": "2026-04-21",
        "start_time": "14:00",
        "end_time": "14:30",
        "label": "21/04/2026 • 14:00 às 14:30",
    },
]


def list_static_booking_slots() -> list[dict[str, str]]:
    return STATIC_BOOKING_SLOTS


def get_static_booking_slot_by_id(slot_id: str) -> dict[str, str] | None:
    for slot in STATIC_BOOKING_SLOTS:
        if slot["id"] == slot_id:
            return slot
    return None