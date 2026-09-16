from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk


class ChunkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_many(self, chunks: list[Chunk]) -> None:
        self.db.add_all(chunks)
        self.db.flush()

    def count_by_document_id(self, document_id: str) -> int:
        stmt = select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
        return int(self.db.scalar(stmt) or 0)

    def count_by_kb_id(self, tenant_id: str, kb_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.tenant_id == tenant_id, Chunk.kb_id == kb_id)
        )
        return int(self.db.scalar(stmt) or 0)

    def delete_by_document_id(self, document_id: str) -> None:
        stmt = delete(Chunk).where(Chunk.document_id == document_id)
        self.db.execute(stmt)
        self.db.flush()

