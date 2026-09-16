from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_tenant
from app.core.auth import TenantContext
from app.db.session import get_db
from app.schemas.common import success_response
from app.schemas.feedback import FeedbackRequest
from app.schemas.rag import RetrieveRequest
from app.services.feedback_service import FeedbackService
from app.services.rag_service import RagService

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/retrieve")
async def retrieve(
    request: RetrieveRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = await RagService(db).retrieve(tenant.tenant_id, request)
    return success_response(data.model_dump(mode="json"))


@router.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = FeedbackService(db).submit_feedback(tenant.tenant_id, request)
    return success_response(data.model_dump(mode="json"))
