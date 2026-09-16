from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_tenant
from app.core.auth import TenantContext
from app.db.session import get_db
from app.schemas.common import success_response
from app.schemas.document import UploadDocumentRequest
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    request: Request,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    content_type = request.headers.get("content-type", "").lower()
    service = DocumentService(db)

    if "multipart/form-data" in content_type:
        form = await request.form()
        kb_id = form.get("kb_id")
        if not kb_id or not str(kb_id).strip():
            from app.core.exceptions import AppError, ErrorCode

            raise AppError(ErrorCode.PARAM_ERROR, msg="kb_id 不能为空")

        upload_file = form.get("file")
        if upload_file is None or not hasattr(upload_file, "read"):
            from app.core.exceptions import AppError, ErrorCode

            raise AppError(ErrorCode.PARAM_ERROR, msg="file 不能为空")

        filename = getattr(upload_file, "filename", None) or "upload.bin"
        file_bytes = await upload_file.read()
        title_field = form.get("title")
        title = str(title_field).strip() if title_field else None

        data = await service.upload_file(
            tenant.tenant_id,
            kb_id=str(kb_id).strip(),
            title=title,
            filename=filename,
            file_bytes=file_bytes,
        )
    else:
        payload = UploadDocumentRequest.model_validate(await request.json())
        data = await service.upload(tenant.tenant_id, payload)

    return success_response(data.model_dump(mode="json"))


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = DocumentService(db).get_detail(tenant.tenant_id, document_id)
    return success_response(data.model_dump(mode="json"))


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    await DocumentService(db).delete(tenant.tenant_id, document_id)
    return success_response(None)


@router.post("/{document_id}/reindex")
async def reindex_document(
    document_id: str,
    reparse: bool = False,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_current_tenant),
) -> dict:
    data = await DocumentService(db).reindex(tenant.tenant_id, document_id, reparse=reparse)
    return success_response(data.model_dump(mode="json"))
