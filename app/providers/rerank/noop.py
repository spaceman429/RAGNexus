from app.providers.rerank.base import RerankProvider


class NoopRerankProvider(RerankProvider):
    async def rerank(
        self,
        *,
        query: str,
        chunks: list[dict],
        top_n: int,
    ) -> list[dict]:
        return [{**chunk, "rerank_score": None} for chunk in chunks[:top_n]]

