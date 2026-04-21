from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.security import require_client_auth
from app.db.session import get_db
from app.schemas.client_portal import (
    ClientPortalWorkspaceFileUploadResponse,
    ClientPortalWorkspaceFilesResponse,
    ClientPortalWorkspaceResponse,
)
from app.services.client_portal import get_client_workspace_portal
from app.services.client_workspace_files import client_upload_workspace_file, list_client_workspace_files, read_upload_file

router = APIRouter(
    prefix='/client',
    tags=['client-portal'],
    dependencies=[Depends(require_client_auth)],
)


@router.get('/workspace', response_model=ClientPortalWorkspaceResponse)
def get_client_workspace(
    claims: dict[str, object] = Depends(require_client_auth),
    db: Session = Depends(get_db),
) -> ClientPortalWorkspaceResponse:
    return get_client_workspace_portal(db, claims)


@router.get('/files', response_model=ClientPortalWorkspaceFilesResponse)
def get_client_workspace_files(
    claims: dict[str, object] = Depends(require_client_auth),
    db: Session = Depends(get_db),
) -> ClientPortalWorkspaceFilesResponse:
    return list_client_workspace_files(db, claims)


@router.post('/files/upload', response_model=ClientPortalWorkspaceFileUploadResponse)
async def post_client_workspace_file_upload(
    claims: dict[str, object] = Depends(require_client_auth),
    file: UploadFile = File(...),
    meeting_id: int | None = Form(None),
    display_name: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ClientPortalWorkspaceFileUploadResponse:
    prepared = await read_upload_file(file)
    return client_upload_workspace_file(
        db=db,
        claims=claims,
        upload=prepared,
        meeting_id=meeting_id,
        display_name=display_name,
        description=description,
    )
