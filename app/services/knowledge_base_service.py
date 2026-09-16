from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.knowledge_base import KnowledgeBase
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    CreateKnowledgeBaseRequest,
    DocumentTreeItem,
    KnowledgeBaseData,
    KnowledgeBaseDetailData,
    KnowledgeBaseTreeItem,
    TenantTreeItem,
    UpdateKnowledgeBaseRequest,
)
from app.services.chunk_purge_service import purge_document_chunks
from app.services.quota_service import QuotaService
from app.utils.id_generator import generate_uuid
from app.utils.kb_settings import validate_kb_settings
from app.utils.status import DocumentStatus

logger = get_logger(__name__)


class KnowledgeBaseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = KnowledgeBaseRepository(db)
        self.document_repository = DocumentRepository(db)

    def create(self, tenant_id: str, request: CreateKnowledgeBaseRequest) -> KnowledgeBaseData:
        QuotaService(self.db).check_create_kb(tenant_id)
        logger.info(
            "BUSINESS_NODE | create_knowledge_base_start | tenant_id=%s | name=%s",
            tenant_id,
            request.name,
        )
        knowledge_base = KnowledgeBase(
            id=generate_uuid(),
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            settings={},
        )
        self.repository.create(knowledge_base)
        self.db.commit()
        self.db.refresh(knowledge_base)

        logger.info(
            "BUSINESS_NODE | create_knowledge_base_success | tenant_id=%s | kb_id=%s",
            knowledge_base.tenant_id,
            knowledge_base.id,
        )
        return KnowledgeBaseData(
            kb_id=knowledge_base.id,
            name=knowledge_base.name,
            tenant_id=knowledge_base.tenant_id,
            created_at=knowledge_base.created_at,
        )

    def get_detail(self, tenant_id: str, kb_id: str) -> KnowledgeBaseDetailData:
        knowledge_base = self.repository.get_by_id_and_tenant(kb_id, tenant_id)
        if knowledge_base is None:
            raise AppError(
                ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                context={"tenant_id": tenant_id, "kb_id": kb_id},
            )
        return self._to_detail_data(knowledge_base)

    def update(
        self,
        tenant_id: str,
        kb_id: str,
        request: UpdateKnowledgeBaseRequest,
    ) -> KnowledgeBaseDetailData:
        knowledge_base = self.repository.get_by_id_and_tenant(kb_id, tenant_id)
        if knowledge_base is None:
            raise AppError(
                ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                context={"tenant_id": tenant_id, "kb_id": kb_id},
            )

        if request.name is not None:
            knowledge_base.name = request.name
        if request.description is not None:
            knowledge_base.description = request.description
        if request.settings is not None:
            validate_kb_settings(request.settings)
            knowledge_base.settings = request.settings

        self.db.commit()
        self.db.refresh(knowledge_base)
        logger.info(
            "BUSINESS_NODE | update_knowledge_base_success | tenant_id=%s | kb_id=%s",
            tenant_id,
            kb_id,
        )
        return self._to_detail_data(knowledge_base)

    async def delete(self, tenant_id: str, kb_id: str) -> None:
        knowledge_base = self.repository.get_by_id_and_tenant(kb_id, tenant_id)
        if knowledge_base is None:
            raise AppError(
                ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                context={"tenant_id": tenant_id, "kb_id": kb_id},
            )

        documents = self.document_repository.list_by_kb_id(kb_id)
        if any(document.status == DocumentStatus.PROCESSING for document in documents):
            raise AppError(
                ErrorCode.DOCUMENT_PROCESSING,
                msg="知识库下仍有文档正在索引，请稍后再删",
                context={"tenant_id": tenant_id, "kb_id": kb_id},
            )

        for document in documents:
            await purge_document_chunks(self.db, document.id)
            self.document_repository.delete(document)

        self.repository.delete(knowledge_base)
        self.db.commit()
        logger.info(
            "BUSINESS_NODE | delete_knowledge_base_success | tenant_id=%s | kb_id=%s | document_count=%s",
            tenant_id,
            kb_id,
            len(documents),
        )

    def get_tree(self, tenant_id: str, keyword: str | None = None) -> list[TenantTreeItem]:
        knowledge_bases = self.repository.list_for_tree(tenant_id, keyword)
        all_documents = [document for kb in knowledge_bases for document in kb.documents]
        success_document_ids = [
            document.id for document in all_documents if document.status == DocumentStatus.SUCCESS
        ]
        chunk_counts = self.repository.get_chunk_counts(success_document_ids)

        kb_items: list[KnowledgeBaseTreeItem] = []
        for kb in knowledge_bases:
            documents = sorted(kb.documents, key=lambda doc: doc.created_at, reverse=True)
            kb_items.append(
                KnowledgeBaseTreeItem(
                    kb_id=kb.id,
                    name=kb.name,
                    description=kb.description,
                    created_at=kb.created_at,
                    documents=[
                        DocumentTreeItem(
                            document_id=doc.id,
                            title=doc.title,
                            status=doc.status,
                            chunk_count=chunk_counts.get(doc.id, 0),
                            error_message=doc.error_message,
                            created_at=doc.created_at,
                        )
                        for doc in documents
                    ],
                )
            )

        return [TenantTreeItem(tenant_id=tenant_id, knowledge_bases=kb_items)]

    def _to_detail_data(self, knowledge_base: KnowledgeBase) -> KnowledgeBaseDetailData:
        return KnowledgeBaseDetailData(
            kb_id=knowledge_base.id,
            tenant_id=knowledge_base.tenant_id,
            name=knowledge_base.name,
            description=knowledge_base.description,
            settings=knowledge_base.settings or {},
            document_count=self.repository.count_documents(knowledge_base.id),
            created_at=knowledge_base.created_at,
            updated_at=knowledge_base.updated_at,
        )
