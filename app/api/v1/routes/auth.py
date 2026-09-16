from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_tenant
from app.core.auth import TenantContext
from app.db.session import get_db
from app.schemas.common import success_response
from app.services.auth_me_service import AuthMeService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def auth_me(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict:
    data = AuthMeService(db).get_me_data(tenant)
    return success_response(data.model_dump(mode="json"))
