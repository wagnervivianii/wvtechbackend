from __future__ import annotations

BLOCKING_BOOKING_REQUEST_STATUSES = frozenset(
    {
        "pending_contact_confirmation",
        "email_confirmed_pending_admin_review",
        "approved",
    }
)

REOPENED_BOOKING_REQUEST_STATUSES = frozenset(
    {
        "rejected",
        "cancelled",
    }
)


def is_blocking_booking_request_status(status: str) -> bool:
    return status in BLOCKING_BOOKING_REQUEST_STATUSES