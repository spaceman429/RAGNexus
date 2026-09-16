from abc import ABC, abstractmethod


class RerankProvider(ABC):
    @abstractmethod
    async def rerank(
        self,
        *,
        query: str,
        chunks: list[dict],
        top_n: int,
    ) -> list[dict]:
        pass

