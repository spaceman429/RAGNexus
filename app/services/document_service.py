from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, ErrorCode
from app.core.logging import get_logger
from app.providers.parsers.registry import validate_upload_extension
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    DocumentDetailData,
    ReindexDocumentData,
    UploadDocumentData,
    UploadDocumentRequest,
)
from app.services.chunk_purge_service import purge_document_chunks
from app.services.reindex_service import queue_document_reindex
from app.services.indexing_service import create_indexing_service
from app.services.quota_service import QuotaService
from app.tasks.indexing import index_document_task
from app.utils.document_storage import save_document_file
from app.utils.id_generator import generate_uuid
from app.utils.status import DocumentStatus

logger = get_logger(__name__)


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.document_repository = DocumentRepository(db)
        self.chunk_repository = ChunkRepository(db)

    async def upload(self, tenant_id: str, request: UploadDocumentRequest) -> UploadDocumentData:
        QuotaService(self.db).check_upload_document(tenant_id, request.kb_id)
        indexing_service = create_indexing_service(self.db)
        document = indexing_service.create_document_record(tenant_id, request)
        index_document_task.delay(document.id)
        return UploadDocumentData(
            document_id=document.id,
            kb_id=document.kb_id,
            status=DocumentStatus.PROCESSING,
            chunk_count=0,
        )

    async def upload_file(
        self,
        tenant_id: str,
        *,
        kb_id: str,
        title: str | None,
        filename: str,
        file_bytes: bytes,
    ) -> UploadDocumentData:
        validate_upload_extension(filename)
        max_bytes = settings.document_max_size_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise AppError(
                ErrorCode.PARAM_ERROR,
                msg=f"文件大小超过限制（最大 {settings.document_max_size_mb} MB）",
                context={"filename": filename, "size_bytes": len(file_bytes)},
            )

        QuotaService(self.db).check_upload_document(tenant_id, kb_id)
        indexing_service = create_indexing_service(self.db)

        document_title = (title or Path(filename).stem or filename)[:255]
        document_id = generate_uuid()
        source_file_path = save_document_file(
            tenant_id=tenant_id,
            document_id=document_id,
            filename=filename,
            file_bytes=file_bytes,
        )
        document = indexing_service.create_file_document_record(
            tenant_id,
            kb_id=kb_id,
            title=document_title,
            source_file_path=source_file_path,
            source_filename=Path(filename).name,
            document_id=document_id,
        )

        index_document_task.delay(document.id)
        return UploadDocumentData(
            document_id=document.id,
            kb_id=document.kb_id,
            status=DocumentStatus.PROCESSING,
            chunk_count=0,
        )

    def get_detail(self, tenant_id: str, document_id: str) -> DocumentDetailData:
        document = self._get_document_or_raise(tenant_id, document_id)
        chunk_count = self.chunk_repository.count_by_document_id(document_id)
        return DocumentDetailData(
            document_id=document.id,
            kb_id=document.kb_id,
            title=document.title,
            status=document.status,
            error_message=document.error_message,
            chunk_count=chunk_count,
            source_type=document.source_type,
            source_filename=document.source_filename,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def delete(self, tenant_id: str, document_id: str) -> None:
        document = self._get_document_or_raise(tenant_id, document_id)
        if document.status == DocumentStatus.PROCESSING:
            raise AppError(
                ErrorCode.DOCUMENT_PROCESSING,
                context={"tenant_id": tenant_id, "document_id": document_id},
            )

        await purge_document_chunks(self.db, document_id)
        self.document_repository.delete(document)
        self.db.commit()
        logger.info(
            "BUSINESS_NODE | delete_document_success | tenant_id=%s | document_id=%s",
            tenant_id,
            document_id,
        )

    async def reindex(self, tenant_id: str, document_id: str, *, reparse: bool = False) -> ReindexDocumentData:
        document = self._get_document_or_raise(tenant_id, document_id)
        if document.status == DocumentStatus.PROCESSING:
            raise AppError(
                ErrorCode.DOCUMENT_PROCESSING,
                context={"tenant_id": tenant_id, "document_id": document_id},
            )
        if document.status not in (DocumentStatus.FAILED, DocumentStatus.SUCCESS):
            raise AppError(
                ErrorCode.PARAM_ERROR,
                msg="仅索引成功或失败的文档可重建索引",
                context={"tenant_id": tenant_id, "document_id": document_id, "status": document.status},
            )

        QuotaService(self.db).check_reindex(tenant_id)

        await queue_document_reindex(self.db, document, reparse=reparse)
        logger.info(
            "BUSINESS_NODE | reindex_document_queued | tenant_id=%s | document_id=%s",
            tenant_id,
            document_id,
        )
        return ReindexDocumentData(
            document_id=document.id,
            kb_id=document.kb_id,
            status=DocumentStatus.PROCESSING,
            chunk_count=0,
        )

    def _get_document_or_raise(self, tenant_id: str, document_id: str):
        document = self.document_repository.get_by_id_and_tenant(document_id, tenant_id)
        if document is None:
            raise AppError(
                ErrorCode.DOCUMENT_NOT_FOUND,
                context={"tenant_id": tenant_id, "document_id": document_id},
            )
        return document
