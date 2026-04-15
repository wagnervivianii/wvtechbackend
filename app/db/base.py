from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.booking_request import BookingRequest  # noqa: E402,F401