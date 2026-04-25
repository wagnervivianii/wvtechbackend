from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminClientWorkspaceProvisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    create_invite: bool = Field(
        True,
        description='Indica se deve gerar um convite de ativação para o cliente.',
    )
    invite_ttl_hours: int = Field(
        168,
        ge=1,
        le=720,
        description='Prazo de expiração do convite, em horas.',
    )
    portal_notes: str | None = Field(
        None,
        max_length=4000,
        description='Observações internas para o portal do cliente.',
    )


class AdminClientWorkspaceInviteRefreshRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    invite_ttl_hours: int = Field(
        168,
        ge=1,
        le=720,
        description='Prazo de expiração do novo convite, em horas.',
    )


class AdminClientWorkspaceLifecycleRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str | None = Field(
        None,
        max_length=1000,
        description="Motivo administrativo para a alteração do ciclo de vida.",
    )


class AdminClientWorkspaceLifecycleResponse(BaseModel):
    workspace_id: int = Field(..., description="Identificador interno do workspace")
    previous_status: str = Field(..., description="Status anterior do workspace")
    workspace_status: str = Field(..., description="Novo status do workspace")
    client_access_revoked: bool = Field(..., description="Indica se o acesso do cliente foi bloqueado")
    pending_invites_revoked: int = Field(..., description="Quantidade de convites pendentes revogados")
    visible_meetings_hidden: int = Field(..., description="Quantidade de reuniões ocultadas do cliente")
    admin_history_preserved: bool = Field(..., description="Indica que o histórico administrativo foi preservado")
    message: str = Field(..., description="Resumo operacional da alteração")


class AdminClientWorkspaceArtifactUpsertRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    artifact_type: str = Field(..., description='Tipo do artefato: recording, transcript, summary ou notes')
    artifact_status: str = Field('available', description='Status do artefato: pending, available, failed ou archived')
    artifact_label: str | None = Field(None, max_length=255, description='Rótulo amigável do artefato')
    source_provider: str | None = Field(None, max_length=80, description='Origem do artefato, como google_meet')
    google_conference_record_name: str | None = Field(None, max_length=255, description='Resource name do conference record no Google')
    google_artifact_resource_name: str | None = Field(None, max_length=255, description='Resource name específico do artefato no Google')
    source_download_url: str | None = Field(None, max_length=500, description='Link original de origem do artefato')
    drive_file_id: str | None = Field(None, max_length=255, description='ID do arquivo no Google Drive')
    drive_file_name: str | None = Field(None, max_length=255, description='Nome do arquivo no Google Drive')
    drive_web_view_link: str | None = Field(None, max_length=500, description='Link web para visualização do arquivo')
    mime_type: str | None = Field(None, max_length=120, description='Mime type do arquivo')
    file_size_bytes: int | None = Field(None, ge=0, description='Tamanho do arquivo em bytes')
    text_content: str | None = Field(None, description='Conteúdo textual completo do artefato')
    summary_text: str | None = Field(None, description='Resumo textual do artefato')
    metadata_json: dict[str, Any] | list[Any] | None = Field(
        None,
        description='Metadados complementares serializáveis em JSON',
    )
    captured_at: datetime | None = Field(None, description='Momento em que o artefato foi capturado')
    is_visible_to_client: bool = Field(True, description='Define se o artefato fica visível no portal do cliente')


class AdminClientWorkspaceDriveFolderItem(BaseModel):
    folder_id: str = Field(..., description='Identificador da pasta no Google Drive')
    folder_name: str = Field(..., description='Nome visível da pasta')
    web_view_link: str | None = Field(None, description='Link web da pasta no Google Drive')


class AdminClientWorkspaceDriveInfo(BaseModel):
    sync_status: str = Field(..., description='Status da sincronização da estrutura no Drive')
    sync_error: str | None = Field(None, description='Último erro de sincronização registrado')
    synced_at: str | None = Field(None, description='Momento da última sincronização bem-sucedida')
    root: AdminClientWorkspaceDriveFolderItem | None = Field(None, description='Pasta raiz do cliente')
    meet_artifacts: AdminClientWorkspaceDriveFolderItem | None = Field(
        None,
        description='Subpasta destinada aos artefatos do Meet',
    )
    client_uploads: AdminClientWorkspaceDriveFolderItem | None = Field(
        None,
        description='Subpasta destinada aos uploads do cliente',
    )
    generated_documents: AdminClientWorkspaceDriveFolderItem | None = Field(
        None,
        description='Subpasta destinada aos documentos gerados pelo sistema',
    )
    archive: AdminClientWorkspaceDriveFolderItem | None = Field(
        None,
        description='Subpasta reservada para arquivamento do workspace',
    )


class AdminClientWorkspaceMeetingArtifactItem(BaseModel):
    id: int = Field(..., description='Identificador interno do artefato')
    artifact_type: str = Field(..., description='Tipo do artefato persistido')
    artifact_status: str = Field(..., description='Status operacional do artefato')
    artifact_label: str | None = Field(None, description='Rótulo amigável do artefato')
    source_provider: str | None = Field(None, description='Origem do artefato')
    google_conference_record_name: str | None = Field(None, description='Resource name do conference record')
    google_artifact_resource_name: str | None = Field(None, description='Resource name específico do artefato')
    source_download_url: str | None = Field(None, description='Link original do artefato')
    drive_file_id: str | None = Field(None, description='ID do arquivo no Google Drive')
    drive_file_name: str | None = Field(None, description='Nome do arquivo no Google Drive')
    drive_web_view_link: str | None = Field(None, description='Link de visualização do arquivo no Google Drive')
    mime_type: str | None = Field(None, description='Mime type do arquivo')
    file_size_bytes: int | None = Field(None, description='Tamanho do arquivo em bytes')
    text_content: str | None = Field(None, description='Conteúdo textual completo')
    summary_text: str | None = Field(None, description='Resumo textual do artefato')
    metadata_json: dict[str, Any] | list[Any] | None = Field(None, description='Metadados complementares')
    captured_at: str | None = Field(None, description='Momento da captura do artefato')
    last_synced_at: str | None = Field(None, description='Momento da última sincronização do artefato')
    is_visible_to_client: bool = Field(..., description='Se o artefato aparece para o cliente')
    created_at: str = Field(..., description='Data de criação do artefato')
    updated_at: str = Field(..., description='Data da última atualização do artefato')


class AdminClientWorkspaceMeetingItem(BaseModel):
    id: int = Field(..., description='Identificador interno da reunião no workspace')
    booking_request_id: int = Field(..., description='Solicitação original vinculada')
    meeting_label: str = Field(..., description='Rótulo consolidado da reunião')
    meet_url: str | None = Field(None, description='Link do Google Meet')
    recording_url: str | None = Field(None, description='Link externo da gravação')
    recording_provider: str | None = Field(None, description='Provedor da gravação')
    has_transcript: bool = Field(..., description='Indica se existe transcrição')
    transcript_summary: str | None = Field(None, description='Resumo da transcrição')
    transcript_text: str | None = Field(None, description='Transcrição completa da reunião')
    meeting_notes: str | None = Field(None, description='Observações da reunião')
    meeting_started_at: str | None = Field(None, description='Início registrado da reunião')
    meeting_ended_at: str | None = Field(None, description='Fim registrado da reunião')
    is_visible_to_client: bool = Field(
        ...,
        description='Indica se a reunião está visível ao cliente no portal',
    )
    synced_from_booking_at: str | None = Field(
        None,
        description='Momento da última sincronização a partir do booking',
    )
    artifacts: list[AdminClientWorkspaceMeetingArtifactItem] = Field(
        default_factory=list,
        description='Artefatos persistidos e vinculados a esta reunião',
    )


class AdminClientWorkspaceInviteItem(BaseModel):
    id: int = Field(..., description='Identificador interno do convite')
    invite_email: str = Field(..., description='Email para o qual o convite foi emitido')
    invite_status: str = Field(..., description='Status atual do convite')
    expires_at: str | None = Field(None, description='Data de expiração do convite')
    sent_at: str | None = Field(None, description='Data de envio do convite')
    accepted_at: str | None = Field(None, description='Data de aceite do convite')
    created_at: str = Field(..., description='Data de criação do convite')


class AdminClientWorkspaceAccountItem(BaseModel):
    id: int = Field(..., description='Identificador interno da conta do cliente')
    email: str = Field(..., description='E-mail de autenticação do cliente')
    full_name: str | None = Field(None, description='Nome principal da conta')
    has_password: bool = Field(..., description='Indica se existe senha definida')
    google_linked: bool = Field(..., description='Indica se existe vínculo com Google')
    auth_provider: str = Field(..., description='Resumo do provedor de autenticação')
    google_picture_url: str | None = Field(None, description='Avatar retornado pelo Google')
    last_login_at: str | None = Field(None, description='Último acesso autenticado do cliente')
    created_at: str = Field(..., description='Data de criação da conta')


class AdminClientWorkspaceSummaryItem(BaseModel):
    workspace_id: int = Field(..., description='Identificador interno do workspace')
    workspace_status: str = Field(..., description='Status atual do workspace')
    source_booking_request_id: int | None = Field(None, description='Solicitação de origem')
    source_booking_status: str = Field(..., description='Status atual do booking de origem')
    source_meeting_status: str = Field(..., description='Status da reunião de origem')
    primary_contact_name: str = Field(..., description='Nome do contato principal')
    primary_contact_email: str = Field(..., description='Email do contato principal')
    primary_contact_phone: str = Field(..., description='Telefone do contato principal')
    portal_notes: str | None = Field(None, description='Observações internas do portal')
    activated_at: str | None = Field(None, description='Data de ativação do portal')
    created_at: str = Field(..., description='Data de criação do workspace')
    has_client_access: bool = Field(..., description='Indica se o cliente já acessou o portal')
    latest_invite_status: str | None = Field(None, description='Status do convite mais recente')
    latest_invite_sent_at: str | None = Field(None, description='Data de envio do convite mais recente')
    latest_invite_accepted_at: str | None = Field(None, description='Data de aceite do convite mais recente')
    meetings_count: int = Field(..., description='Quantidade total de reuniões vinculadas')
    visible_meetings_count: int = Field(..., description='Quantidade de reuniões visíveis ao cliente')
    latest_meeting: AdminClientWorkspaceMeetingItem | None = Field(
        None,
        description='Reunião mais recente vinculada ao workspace',
    )
    account: AdminClientWorkspaceAccountItem | None = Field(
        None,
        description='Conta do cliente associada ao workspace',
    )
    invites: list[AdminClientWorkspaceInviteItem] = Field(..., description='Convites emitidos')
    meetings: list[AdminClientWorkspaceMeetingItem] = Field(..., description='Reuniões vinculadas')
    drive: AdminClientWorkspaceDriveInfo = Field(..., description='Estrutura Google Drive vinculada ao workspace')


class AdminClientWorkspaceListResponse(BaseModel):
    items: list[AdminClientWorkspaceSummaryItem] = Field(
        ...,
        description='Lista consolidada de workspaces do cliente',
    )


class AdminClientWorkspaceArtifactsResponse(BaseModel):
    workspace_id: int = Field(..., description='Identificador interno do workspace')
    primary_contact_name: str = Field(..., description='Nome do contato principal do workspace')
    primary_contact_email: str = Field(..., description='Email do contato principal do workspace')
    meetings: list[AdminClientWorkspaceMeetingItem] = Field(
        ...,
        description='Reuniões do workspace com seus artefatos persistidos',
    )

class AdminClientWorkspaceMeetingArtifactBatchSyncRequest(BaseModel):
    max_meetings: int = Field(10, ge=1, le=100, description='Quantidade máxima de reuniões elegíveis a sincronizar nesta execução')
    force_resync: bool = Field(False, description='Se verdadeiro, tenta sincronizar mesmo reuniões que já possuem artefatos Google disponíveis')


class AdminClientWorkspaceMeetingArtifactBatchSyncItem(BaseModel):
    meeting_id: int = Field(..., description='Identificador interno da reunião do workspace')
    meeting_label: str = Field(..., description='Rótulo consolidado da reunião')
    sync_status: str = Field(..., description='Status final da tentativa de sincronização')
    message: str | None = Field(None, description='Mensagem resumida do resultado da tentativa')
    conference_record_name: str | None = Field(None, description='Conference record selecionada no Google Meet')
    synchronized_at: str = Field(..., description='Momento em que a tentativa foi executada')
    artifacts_upserted: int = Field(..., description='Quantidade de artefatos persistidos/atualizados na tentativa')
    recordings_synced: int = Field(..., description='Quantidade de gravações sincronizadas na tentativa')
    transcripts_synced: int = Field(..., description='Quantidade de transcrições sincronizadas na tentativa')
    notes_synced: int = Field(..., description='Quantidade de smart notes sincronizadas na tentativa')


class AdminClientWorkspaceMeetingArtifactBatchSyncResponse(BaseModel):
    workspace_id: int = Field(..., description='Identificador interno do workspace')
    processed_meetings_count: int = Field(..., description='Quantidade de reuniões realmente processadas nesta execução')
    eligible_meetings_count: int = Field(..., description='Quantidade de reuniões elegíveis encontradas antes do limite')
    synchronized_meetings_count: int = Field(..., description='Quantidade de reuniões com algum artefato efetivamente sincronizado')
    no_artifacts_available_count: int = Field(..., description='Quantidade de reuniões sem artefatos prontos no Google Meet')
    conference_not_found_count: int = Field(..., description='Quantidade de reuniões em que a conference record ainda não foi encontrada')
    failed_meetings_count: int = Field(..., description='Quantidade de reuniões que falharam durante a tentativa')
    items: list[AdminClientWorkspaceMeetingArtifactBatchSyncItem] = Field(default_factory=list, description='Resultado individual de cada reunião processada')


class AdminClientWorkspaceMeetingArtifactSyncResponse(BaseModel):
    workspace_id: int = Field(..., description='Identificador interno do workspace')
    meeting_id: int = Field(..., description='Identificador interno da reunião do workspace')
    meeting_label: str = Field(..., description='Rótulo consolidado da reunião sincronizada')
    meeting_code: str | None = Field(None, description='Código do Google Meet associado à reunião')
    conference_record_name: str | None = Field(None, description='Conference record selecionada no Google Meet')
    sync_status: str = Field(..., description='Status da sincronização automática com o Google Meet')
    message: str | None = Field(None, description='Mensagem resumida do resultado da sincronização')
    synchronized_at: str = Field(..., description='Momento em que a sincronização foi executada')
    artifacts_found: int = Field(..., description='Quantidade de artefatos prontos encontrados no Google Meet')
    artifacts_upserted: int = Field(..., description='Quantidade de artefatos persistidos/atualizados no sistema')
    recordings_synced: int = Field(..., description='Quantidade de gravações sincronizadas')
    transcripts_synced: int = Field(..., description='Quantidade de transcrições sincronizadas')
    notes_synced: int = Field(..., description='Quantidade de smart notes sincronizadas')
    artifacts: list[AdminClientWorkspaceMeetingArtifactItem] = Field(
        default_factory=list,
        description='Artefatos persistidos na reunião após a sincronização',
    )


class AdminClientWorkspaceDetailResponse(BaseModel):
    workspace_id: int = Field(..., description='Identificador interno do workspace')
    workspace_status: str = Field(..., description='Status atual do workspace')
    source_booking_request_id: int | None = Field(
        None,
        description='Solicitação de origem que deu base ao workspace',
    )
    source_booking_status: str = Field(..., description='Status operacional do booking')
    source_meeting_status: str = Field(..., description='Status da reunião vinculada')
    primary_contact_name: str = Field(..., description='Nome do contato principal')
    primary_contact_email: str = Field(..., description='Email do contato principal')
    primary_contact_phone: str = Field(..., description='Telefone do contato principal')
    portal_notes: str | None = Field(None, description='Observações internas do portal')
    activated_at: str | None = Field(None, description='Data de ativação do workspace')
    created_at: str = Field(..., description='Data de criação do workspace')
    account: AdminClientWorkspaceAccountItem | None = Field(
        None,
        description='Conta do cliente associada ao workspace',
    )
    meetings: list[AdminClientWorkspaceMeetingItem] = Field(..., description='Reuniões vinculadas')
    invites: list[AdminClientWorkspaceInviteItem] = Field(..., description='Convites emitidos para acesso')
    drive: AdminClientWorkspaceDriveInfo = Field(..., description='Estrutura Google Drive vinculada ao workspace')
    setup_token: str | None = Field(
        None,
        description='Token bruto de ativação retornado apenas após gerar um novo acesso',
    )
    setup_path: str | None = Field(
        None,
        description='Caminho relativo do primeiro acesso do cliente',
    )
    setup_url: str | None = Field(
        None,
        description='URL absoluta de primeiro acesso do cliente',
    )


class AdminClientWorkspaceFileItem(BaseModel):
    id: int
    workspace_id: int
    meeting_id: int | None
    uploaded_by_role: str
    file_category: str
    review_status: str
    visibility_scope: str
    display_name: str | None
    description: str | None
    drive_file_id: str
    drive_file_name: str | None
    drive_web_view_link: str | None
    mime_type: str | None
    file_extension: str | None
    file_size_bytes: int | None
    review_notes: str | None
    approved_at: str | None
    reviewed_at: str | None
    archived_at: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str


class AdminClientWorkspaceFileListResponse(BaseModel):
    workspace_id: int
    pending_review_count: int
    approved_count: int
    archived_count: int
    rejected_count: int
    items: list[AdminClientWorkspaceFileItem]


class AdminClientWorkspaceFileActionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    review_notes: str | None = Field(None, max_length=4000)
    visible_to_client: bool = Field(True)
