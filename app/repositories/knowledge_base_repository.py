from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, knowledge_base: KnowledgeBase) -> KnowledgeBase:
        self.db.add(knowledge_base)
        self.db.flush()
        return knowledge_base

    def get_by_id(self, kb_id: str) -> KnowledgeBase | None:
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        return self.db.scalar(stmt)

    def get_by_id_and_tenant(self, kb_id: str, tenant_id: str) -> KnowledgeBase | None:
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
        return self.db.scalar(stmt)

    def list_for_tree(self, tenant_id: str, keyword: str | None = None) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.tenant_id == tenant_id)
            .order_by(KnowledgeBase.created_at.desc())
            .options(selectinload(KnowledgeBase.documents))
        )
        if keyword:
            stmt = stmt.where(KnowledgeBase.name.ilike(f"%{keyword}%"))
        return list(self.db.scalars(stmt).all())

    def update_settings(self, kb_id: str, settings: dict) -> KnowledgeBase | None:
        knowledge_base = self.get_by_id(kb_id)
        if knowledge_base is None:
            return None
        knowledge_base.settings = settings
        self.db.flush()
        return knowledge_base

    def count_documents(self, kb_id: str) -> int:
        stmt = select(func.count()).select_from(Document).where(Document.kb_id == kb_id)
        return int(self.db.scalar(stmt) or 0)

    def count_by_tenant(self, tenant_id: str) -> int:
        stmt = select(func.count()).select_from(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
        )
        return int(self.db.scalar(stmt) or 0)

    def delete(self, knowledge_base: KnowledgeBase) -> None:
        self.db.delete(knowledge_base)
        self.db.flush()

    def get_chunk_counts(self, document_ids: list[str]) -> dict[str, int]:
        if not document_ids:
            return {}
        stmt = (
            select(Chunk.document_id, func.count())
            .where(Chunk.document_id.in_(document_ids))
            .group_by(Chunk.document_id)
        )
        return dict(self.db.execute(stmt).all())
