from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.providers.vectorstores.base import VectorStore
from app.repositories.chunk_repository import ChunkRepository


class PgVectorStore(VectorStore):
    name = "pgvector"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.chunk_repository = ChunkRepository(db)

    async def add_chunks(self, chunks: list[dict]) -> None:
        db_chunks = [
            Chunk(
                id=chunk["chunk_id"],
                tenant_id=chunk["tenant_id"],
                kb_id=chunk["kb_id"],
                document_id=chunk["document_id"],
                title=chunk["title"],
                content=chunk["content"],
                metadata_=chunk.get("metadata", {}),
                embedding=chunk["embedding"],
            )
            for chunk in chunks
        ]
        self.chunk_repository.add_many(db_chunks)

    async def similarity_search(
        self,
        query_vector: list[float],
        *,
        tenant_id: str,
        kb_id: str,
        top_k: int = 5,
    ) -> list[dict]:
        distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
        stmt = (
            select(Chunk, distance)
            .where(Chunk.tenant_id == tenant_id, Chunk.kb_id == kb_id)
            .order_by(distance)
            .limit(top_k)
        )
        rows = self.db.execute(stmt).all()

        results: list[dict] = []
        for chunk, distance_value in rows:
            score = 1.0 - float(distance_value)
            results.append(
                {
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "score": score,
                    "metadata": chunk.metadata_ or {},
                }
            )
        return results

    async def delete_by_document_id(self, document_id: str) -> None:
        self.chunk_repository.delete_by_document_id(document_id)

