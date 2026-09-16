from pydantic import BaseModel


class RerankCandidate(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    content: str
    vector_score: float


class RerankRanking(BaseModel):
    chunk_id: str
    rerank_score: float
    reason: str | None = None

