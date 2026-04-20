from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_client_auth
from app.db.session import get_db
from app.schemas.client_portal import ClientPortalWorkspaceResponse
from app.services.client_portal import get_client_workspace_portal

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