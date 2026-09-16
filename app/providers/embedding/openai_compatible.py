import time

import httpx

from app.core.config import settings
from app.core.exceptions import AppError, ErrorCode
from app.core.logging import log_llm_error, log_llm_request, log_llm_response
from app.providers.embedding.base import EmbeddingProvider


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        base_url: str = settings.model_base_url,
        api_key: str = settings.model_api_key,
        model: str = settings.embedding_model,
        dimensions: int = settings.embedding_dimensions,
        batch_size: int = settings.embedding_batch_size,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.timeout = timeout

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        total_started_at = time.perf_counter()
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            batch_embeddings = await self._embed_batch(
                batch,
                batch_index=start // self.batch_size + 1,
                batch_start=start,
                total_count=len(texts),
            )
            embeddings.extend(batch_embeddings)

        total_cost_ms = (time.perf_counter() - total_started_at) * 1000
        log_llm_response(
            model=self.model,
            response={
                "embedding_count": len(embeddings),
                "dimensions": self.dimensions,
                "batch_size": self.batch_size,
                "batch_count": (len(texts) + self.batch_size - 1) // self.batch_size,
            },
            cost_ms=total_cost_ms,
            extra={"provider": "openai_compatible_embedding", "stage": "embedding_total"},
        )
        return embeddings

    async def _embed_batch(
        self,
        texts: list[str],
        *,
        batch_index: int,
        batch_start: int,
        total_count: int,
    ) -> list[list[float]]:
        payload = {"model": self.model, "input": texts, "dimensions": self.dimensions}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        started_at = time.perf_counter()
        log_llm_request(
            model=self.model,
            prompt={
                "input_count": len(texts),
                "total_count": total_count,
                "batch_index": batch_index,
                "batch_start": batch_start,
                "dimensions": self.dimensions,
                "sample": texts[:2],
            },
            extra={
                "provider": "openai_compatible_embedding",
                "base_url": self.base_url,
                "batch_size": self.batch_size,
            },
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            cost_ms = (time.perf_counter() - started_at) * 1000
            response_text = getattr(exc, "response", None)
            error_body = response_text.text if response_text is not None else None
            log_llm_error(
                model=self.model,
                error=exc,
                cost_ms=cost_ms,
                prompt={
                    "input_count": len(texts),
                    "total_count": total_count,
                    "batch_index": batch_index,
                    "batch_start": batch_start,
                    "dimensions": self.dimensions,
                    "sample": texts[:2],
                },
                extra={
                    "provider": "openai_compatible_embedding",
                    "base_url": self.base_url,
                    "response_body": error_body,
                },
            )
            raise AppError(
                ErrorCode.EMBEDDING_FAILED,
                internal_msg=f"embedding request failed: {exc}; response_body={error_body}",
                context={
                    "model": self.model,
                    "input_count": len(texts),
                    "total_count": total_count,
                    "batch_index": batch_index,
                    "batch_start": batch_start,
                    "embedding_batch_size": self.batch_size,
                },
            ) from exc

        body = response.json()
        data = body.get("data", [])
        if len(data) != len(texts):
            error = AppError(
                ErrorCode.EMBEDDING_FAILED,
                internal_msg="embedding response size mismatch",
                context={
                    "expected": len(texts),
                    "actual": len(data),
                    "batch_index": batch_index,
                    "batch_start": batch_start,
                },
            )
            cost_ms = (time.perf_counter() - started_at) * 1000
            log_llm_error(
                model=self.model,
                error=error,
                cost_ms=cost_ms,
                prompt={
                    "input_count": len(texts),
                    "batch_index": batch_index,
                    "batch_start": batch_start,
                    "dimensions": self.dimensions,
                },
                extra={"provider": "openai_compatible_embedding"},
            )
            raise error

        embeddings = [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]
        cost_ms = (time.perf_counter() - started_at) * 1000
        log_llm_response(
            model=self.model,
            response={
                "embedding_count": len(embeddings),
                "dimensions": self.dimensions,
                "batch_index": batch_index,
                "batch_start": batch_start,
            },
            cost_ms=cost_ms,
            extra={"provider": "openai_compatible_embedding", "stage": "embedding_batch"},
        )
        return embeddings

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed_texts([query])
        return embeddings[0]
