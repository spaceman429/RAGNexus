from abc import ABC, abstractmethod


class KeywordSearchProvider(ABC):
    name: str

    @abstractmethod
    async def add_chunks(self, chunks: list[dict]) -> None:
        pass

    @abstractmethod
    async def keyword_search(
        self,
        *,
        query: str,
        tenant_id: str,
        kb_id: str,
        top_k: int = 20,
    ) -> list[dict]:
        pass

    @abstractmethod
    async def delete_by_document_id(self, document_id: str) -> None:
        pass
