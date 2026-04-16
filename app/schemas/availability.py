from pydantic import BaseModel, Field

from app.schemas.bookings import BookingSlotSummary


class AvailabilityCalendarDay(BaseModel):
    date: str = Field(..., description="Data disponível no calendário")
    weekday_label: str = Field(..., description="Dia da semana formatado")
    day_label: str = Field(..., description="Dia do mês formatado")
    month_label: str = Field(..., description="Nome do mês formatado")


class AvailabilityCalendarMonth(BaseModel):
    year: int = Field(..., description="Ano do agrupamento")
    month: int = Field(..., description="Mês do agrupamento")
    month_label: str = Field(..., description="Rótulo do mês para exibição")
    days: list[AvailabilityCalendarDay] = Field(
        ...,
        description="Dias disponíveis dentro do mês",
    )


class AvailabilityCalendarResponse(BaseModel):
    months: list[AvailabilityCalendarMonth] = Field(
        ...,
        description="Meses disponíveis no calendário",
    )


class AvailabilitySlotListResponse(BaseModel):
    date: str = Field(..., description="Data consultada")
    slots: list[BookingSlotSummary] = Field(
        ...,
        description="Horários disponíveis para a data selecionada",
    )
