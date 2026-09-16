from pydantic import BaseModel


class HybridSearchResult(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    vector_score: float | None = None
    bm25_score: float | None = None
    vector_rank: int | None = None
    bm25_rank: int | None = None
    retrieval_source: str
