from datetime import date as date_type

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.text_rules import (
    normalize_name_text,
    normalize_phone_text,
    normalize_summary_text,
)


class BookingSlotSummary(BaseModel):
    id: str = Field(..., description="Identificador do horário")
    availability_slot_id: int = Field(..., description="ID interno do horário disponível")
    date: str = Field(..., description="Data do horário")
    start_time: str = Field(..., description="Hora inicial")
    end_time: str = Field(..., description="Hora final")
    label: str = Field(..., description="Rótulo formatado para exibição")


class BookingSlotListResponse(BaseModel):
    slots: list[BookingSlotSummary] = Field(
        ...,
        description="Lista de horários disponíveis para agendamento",
    )


class BookingRequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slot_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identificador do horário selecionado",
    )
    name: str = Field(
        ...,
        min_length=3,
        max_length=120,
        description="Nome do visitante",
    )
    email: EmailStr = Field(
        ...,
        description="Email do visitante",
    )
    phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Telefone do visitante",
    )
    subject_summary: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Resumo do assunto da reunião",
    )

    @field_validator("slot_id")
    @classmethod
    def normalize_slot_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_name_text(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_phone_text(value)

    @field_validator("subject_summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        return normalize_summary_text(value)


class BookingRequestCreated(BaseModel):
    status: str = Field(..., description="Status do recebimento da solicitação")
    message: str = Field(..., description="Mensagem de retorno da API")
    slot_id: str = Field(..., description="Identificador do horário solicitado")
    booking_date: date_type = Field(..., description="Data selecionada para a conversa")
    name: str = Field(..., description="Nome do visitante")
    email: EmailStr = Field(..., description="Email do visitante")
    phone: str = Field(..., description="Telefone do visitante")
    subject_summary: str = Field(..., description="Resumo do assunto da reunião")
    slot: BookingSlotSummary = Field(..., description="Resumo do horário selecionado")
    confirmation_preview_token: str | None = Field(
        None,
        description="Token bruto de confirmação visível apenas em ambientes não produtivos",
    )
    confirmation_preview_path: str | None = Field(
        None,
        description="Caminho de confirmação visível apenas em ambientes não produtivos",
    )


class BookingEmailConfirmationResponse(BaseModel):
    booking_id: int = Field(..., description="Identificador interno da solicitação")
    status: str = Field(..., description="Status atualizado da solicitação")
    message: str = Field(..., description="Mensagem de retorno da confirmação")
    confirmed_at: str = Field(..., description="Data e hora da confirmação do email")