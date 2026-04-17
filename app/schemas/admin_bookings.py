from pydantic import BaseModel, Field


class AdminBookingRebookingPermissionRequest(BaseModel):
    can_schedule_again: bool = Field(
        ...,
        description="Indica se o contato está liberado para criar uma nova solicitação",
    )


class AdminBookingRebookingPermissionResponse(BaseModel):
    id: int = Field(..., description="Identificador da solicitação")
    status: str = Field(..., description="Status operacional da solicitação")
    meeting_status: str = Field(..., description="Status da reunião")
    email: str = Field(..., description="Email normalizado do contato")
    phone: str = Field(..., description="Telefone normalizado do contato")
    can_schedule_again: bool = Field(
        ...,
        description="Indica se o contato foi liberado para um novo agendamento",
    )