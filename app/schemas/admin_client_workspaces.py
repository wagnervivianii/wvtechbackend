from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdminClientWorkspaceProvisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    create_invite: bool = Field(
        True,
        description="Indica se deve gerar um convite de ativação para o cliente.",
    )
    invite_ttl_hours: int = Field(
        168,
        ge=1,
        le=720,
        description="Prazo de expiração do convite, em horas.",
    )
    portal_notes: str | None = Field(
        None,
        max_length=4000,
        description="Observações internas para o portal do cliente.",
    )


class AdminClientWorkspaceMeetingItem(BaseModel):
    id: int = Field(..., description="Identificador interno da reunião no workspace")
    booking_request_id: int = Field(..., description="Solicitação original vinculada")
    meeting_label: str = Field(..., description="Rótulo consolidado da reunião")
    meet_url: str | None = Field(None, description="Link do Google Meet")
    recording_url: str | None = Field(None, description="Link externo da gravação")
    recording_provider: str | None = Field(None, description="Provedor da gravação")
    has_transcript: bool = Field(..., description="Indica se existe transcrição")
    transcript_summary: str | None = Field(None, description="Resumo da transcrição")
    meeting_notes: str | None = Field(None, description="Observações da reunião")
    is_visible_to_client: bool = Field(
        ...,
        description="Indica se a reunião está visível ao cliente no portal",
    )
    synced_from_booking_at: str | None = Field(
        None,
        description="Momento da última sincronização a partir do booking",
    )


class AdminClientWorkspaceInviteItem(BaseModel):
    id: int = Field(..., description="Identificador interno do convite")
    invite_email: str = Field(..., description="Email para o qual o convite foi emitido")
    invite_status: str = Field(..., description="Status atual do convite")
    expires_at: str | None = Field(None, description="Data de expiração do convite")
    sent_at: str | None = Field(None, description="Data de envio do convite")
    accepted_at: str | None = Field(None, description="Data de aceite do convite")
    created_at: str = Field(..., description="Data de criação do convite")


class AdminClientWorkspaceDetailResponse(BaseModel):
    workspace_id: int = Field(..., description="Identificador interno do workspace")
    workspace_status: str = Field(..., description="Status atual do workspace")
    source_booking_request_id: int | None = Field(
        None,
        description="Solicitação de origem que deu base ao workspace",
    )
    source_booking_status: str = Field(..., description="Status operacional do booking")
    source_meeting_status: str = Field(..., description="Status da reunião de origem")
    primary_contact_name: str = Field(..., description="Nome do contato principal")
    primary_contact_email: str = Field(..., description="Email do contato principal")
    primary_contact_phone: str = Field(..., description="Telefone do contato principal")
    portal_notes: str | None = Field(None, description="Observações internas do portal")
    activated_at: str | None = Field(None, description="Data de ativação do portal")
    created_at: str = Field(..., description="Data de criação do workspace")
    meetings: list[AdminClientWorkspaceMeetingItem] = Field(
        ...,
        description="Reuniões vinculadas ao workspace",
    )
    invites: list[AdminClientWorkspaceInviteItem] = Field(
        ...,
        description="Convites emitidos para ativação do workspace",
    )
    setup_token: str | None = Field(
        None,
        description="Token bruto gerado para ativação inicial, quando aplicável",
    )
    setup_path: str | None = Field(
        None,
        description="Caminho previsto para ativação do portal do cliente",
    )