from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.utils.status import DocumentStatus


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document

    def get_by_id(self, document_id: str) -> Document | None:
        return self.db.get(Document, document_id)

    def get_by_id_and_tenant(self, document_id: str, tenant_id: str) -> Document | None:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .one_or_none()
        )

    def list_by_kb_id(self, kb_id: str) -> list[Document]:
        stmt = select(Document).where(Document.kb_id == kb_id)
        return list(self.db.scalars(stmt).all())

    def list_by_kb_id_and_status(self, kb_id: str, status: int) -> list[Document]:
        stmt = select(Document).where(Document.kb_id == kb_id, Document.status == status)
        return list(self.db.scalars(stmt).all())

    def count_by_kb_id(self, kb_id: str) -> int:
        stmt = select(func.count()).select_from(Document).where(Document.kb_id == kb_id)
        return int(self.db.scalar(stmt) or 0)

    def count_processing_by_tenant(self, tenant_id: str) -> int:
        stmt = select(func.count()).select_from(Document).where(
            Document.tenant_id == tenant_id,
            Document.status == DocumentStatus.PROCESSING,
        )
        return int(self.db.scalar(stmt) or 0)

    def update_status(
        self,
        document: Document,
        *,
        status: int,
        error_message: str | None = None,
    ) -> Document:
        document.status = status
        document.error_message = error_message
        self.db.flush()
        return document

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.flush()
