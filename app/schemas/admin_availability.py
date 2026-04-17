from datetime import date as date_type
from datetime import time as time_type

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class AdminAvailabilitySlotItem(BaseModel):
    id: int = Field(..., description="Identificador interno do horário")
    start_time: str = Field(..., description="Hora inicial formatada")
    end_time: str = Field(..., description="Hora final formatada")
    timezone_name: str = Field(..., description="Timezone do horário")
    is_active: bool = Field(..., description="Indica se o horário está ativo")
    label: str = Field(..., description="Rótulo formatado do horário")


class AdminAvailabilityDayItem(BaseModel):
    id: int = Field(..., description="Identificador interno do dia")
    date: str = Field(..., description="Data disponível no formato ISO")
    weekday_label: str = Field(..., description="Dia da semana formatado")
    day_label: str = Field(..., description="Dia do mês formatado")
    month_label: str = Field(..., description="Nome do mês formatado")
    display_label: str = Field(..., description="Rótulo completo do dia")
    is_active: bool = Field(..., description="Indica se o dia está ativo")
    has_active_slots: bool = Field(..., description="Indica se o dia possui ao menos um horário ativo")
    notes: str | None = Field(None, description="Observações internas do dia")
    slots: list[AdminAvailabilitySlotItem] = Field(..., description="Horários vinculados ao dia")


class AdminBookingHistoryItem(BaseModel):
    id: int = Field(..., description="Identificador da solicitação")
    booking_date: str | None = Field(None, description="Data da reunião")
    start_time: str | None = Field(None, description="Hora inicial da reunião")
    end_time: str | None = Field(None, description="Hora final da reunião")
    display_label: str = Field(..., description="Rótulo consolidado da reunião")
    status: str = Field(..., description="Status operacional da solicitação")
    meeting_status: str = Field(..., description="Status da reunião em si")
    name: str = Field(..., description="Nome do contato")
    email: str = Field(..., description="Email do contato")
    phone: str = Field(..., description="Telefone do contato")
    subject_summary: str = Field(..., description="Resumo do assunto")
    meet_url: str | None = Field(None, description="Link do Google Meet, quando existir")
    meeting_notes: str | None = Field(None, description="Observações internas da reunião")
    transcript_summary: str | None = Field(None, description="Resumo da transcrição")
    has_transcript: bool = Field(..., description="Indica se já existe transcrição vinculada")
    created_at: str = Field(..., description="Data de criação da solicitação")
    contact_confirmed_at: str | None = Field(None, description="Data de confirmação do email")
    admin_reviewed_at: str | None = Field(None, description="Data da análise administrativa")
    rejection_reason: str | None = Field(None, description="Motivo de rejeição, quando houver")
    can_schedule_again: bool = Field(
        ...,
        description="Indica se o contato já pode abrir uma nova solicitação",
    )
    has_client_workspace: bool = Field(
        ...,
        description="Indica se já existe workspace provisionado para esta solicitação",
    )
    client_workspace_status: str | None = Field(
        None,
        description="Status do workspace do cliente, quando já existir",
    )


class AdminAvailabilityListResponse(BaseModel):
    days: list[AdminAvailabilityDayItem] = Field(..., description="Dias ativos para gestão administrativa")
    history: list[AdminBookingHistoryItem] = Field(..., description="Histórico de reuniões já solicitadas")


class AdminAvailabilityDayUpsertRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    date: date_type = Field(..., description="Data a ser liberada no formato YYYY-MM-DD")
    is_active: bool = Field(True, description="Indica se o dia deve ficar ativo")


class AdminAvailabilityDayToggleRequest(BaseModel):
    is_active: bool = Field(..., description="Novo status do dia")


class AdminAvailabilitySlotCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    start_time: time_type = Field(..., description="Hora inicial no formato HH:MM")
    end_time: time_type = Field(..., description="Hora final no formato HH:MM")
    timezone_name: str = Field(
        default=settings.app_timezone,
        min_length=1,
        max_length=80,
        description="Timezone do horário",
    )
    is_active: bool = Field(True, description="Indica se o horário inicia ativo")

    @field_validator("timezone_name")
    @classmethod
    def normalize_timezone_name(cls, value: str) -> str:
        return value.strip()


class AdminAvailabilitySlotUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    start_time: time_type = Field(..., description="Hora inicial no formato HH:MM")
    end_time: time_type = Field(..., description="Hora final no formato HH:MM")
    timezone_name: str = Field(
        default=settings.app_timezone,
        min_length=1,
        max_length=80,
        description="Timezone do horário",
    )
    is_active: bool = Field(..., description="Novo status do horário")

    @field_validator("timezone_name")
    @classmethod
    def normalize_timezone_name(cls, value: str) -> str:
        return value.strip()