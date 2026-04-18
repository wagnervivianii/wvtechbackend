from pydantic import BaseModel, ConfigDict, Field

from app.schemas.admin_client_workspaces import AdminClientWorkspaceDetailResponse


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


class AdminBookingPendingReviewItem(BaseModel):
    id: int = Field(..., description="Identificador interno da solicitação")
    booking_date: str | None = Field(None, description="Data da reunião")
    start_time: str | None = Field(None, description="Hora inicial da reunião")
    end_time: str | None = Field(None, description="Hora final da reunião")
    display_label: str = Field(..., description="Rótulo consolidado do horário")
    status: str = Field(..., description="Status atual da solicitação")
    meeting_status: str = Field(..., description="Status da reunião")
    name: str = Field(..., description="Nome do contato")
    email: str = Field(..., description="Email do contato")
    phone: str = Field(..., description="Telefone do contato")
    subject_summary: str = Field(..., description="Resumo do assunto")
    created_at: str = Field(..., description="Data de criação da solicitação")
    contact_confirmed_at: str = Field(..., description="Data de confirmação do email")


class AdminBookingPendingReviewListResponse(BaseModel):
    items: list[AdminBookingPendingReviewItem] = Field(
        ...,
        description="Solicitações prontas para análise administrativa",
    )


class AdminBookingApprovalRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    meeting_notes: str | None = Field(None, max_length=4000, description="Observações internas da reunião")
    create_client_workspace: bool = Field(
        True,
        description="Indica se a aprovação já deve provisionar o workspace do cliente",
    )
    create_workspace_invite: bool = Field(
        True,
        description="Indica se a provisão do workspace deve gerar convite inicial",
    )
    invite_ttl_hours: int = Field(
        168,
        ge=1,
        le=720,
        description="Prazo do convite inicial do portal do cliente, em horas",
    )
    portal_notes: str | None = Field(
        None,
        max_length=4000,
        description="Observações internas para o portal do cliente",
    )




class AdminBookingCancellationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cancellation_reason: str | None = Field(
        None,
        max_length=4000,
        description='Motivo informado ao cliente no cancelamento',
    )
    meeting_notes: str | None = Field(
        None,
        max_length=4000,
        description='Observações internas adicionais sobre o cancelamento',
    )


class AdminBookingRejectionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    rejection_reason: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Justificativa da rejeição da solicitação",
    )
    meeting_notes: str | None = Field(
        None,
        max_length=4000,
        description="Observações internas adicionais",
    )


class AdminBookingDecisionResponse(BaseModel):
    id: int = Field(..., description="Identificador interno da solicitação")
    status: str = Field(..., description="Status operacional da solicitação")
    meeting_status: str = Field(..., description="Status da reunião")
    name: str = Field(..., description="Nome do contato")
    email: str = Field(..., description="Email do contato")
    phone: str = Field(..., description="Telefone do contato")
    subject_summary: str = Field(..., description="Resumo do assunto")
    booking_date: str | None = Field(None, description="Data da reunião")
    start_time: str | None = Field(None, description="Hora inicial")
    end_time: str | None = Field(None, description="Hora final")
    meet_url: str | None = Field(None, description="Link do Google Meet")
    meet_event_id: str | None = Field(None, description="ID do evento do Google Meet")
    meeting_notes: str | None = Field(None, description="Observações internas")
    contact_confirmed_at: str | None = Field(None, description="Data de confirmação do email")
    admin_reviewed_at: str | None = Field(None, description="Data da revisão administrativa")
    rejection_reason: str | None = Field(None, description="Motivo da rejeição, quando existir")
    can_schedule_again: bool = Field(..., description="Indica se já pode abrir novo pedido")
    client_workspace: AdminClientWorkspaceDetailResponse | None = Field(
        None,
        description="Workspace do cliente criado a partir da aprovação, quando aplicável",
    )