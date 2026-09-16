from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_tenant
from app.core.auth import TenantContext
from app.db.session import get_db
from app.schemas.common import success_response
from app.schemas.knowledge_base import CreateKnowledgeBaseRequest, UpdateKnowledgeBaseRequest
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("/tree")
def get_knowledge_base_tree(
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = KnowledgeBaseService(db).get_tree(tenant.tenant_id, keyword)
    return success_response([item.model_dump(mode="json") for item in data])


@router.post("/create")
def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = KnowledgeBaseService(db).create(tenant.tenant_id, request)
    return success_response(data.model_dump(mode="json"))


@router.get("/{kb_id}")
def get_knowledge_base(
    kb_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = KnowledgeBaseService(db).get_detail(tenant.tenant_id, kb_id)
    return success_response(data.model_dump(mode="json"))


@router.patch("/{kb_id}")
def update_knowledge_base(
    kb_id: str,
    request: UpdateKnowledgeBaseRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = KnowledgeBaseService(db).update(tenant.tenant_id, kb_id, request)
    return success_response(data.model_dump(mode="json"))


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    await KnowledgeBaseService(db).delete(tenant.tenant_id, kb_id)
    return success_response(None)
