import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppError, ErrorCode
from app.core.logging import get_logger, safe_json
from app.providers.keyword_search.base import KeywordSearchProvider

logger = get_logger(__name__)


class ElasticsearchKeywordSearchProvider(KeywordSearchProvider):
    name = "elasticsearch"

    def __init__(
        self,
        *,
        base_url: str = settings.elasticsearch_url,
        index_name: str = settings.elasticsearch_index,
        timeout: float = settings.elasticsearch_timeout_seconds,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.index_name = index_name
        self.timeout = timeout

    async def add_chunks(self, chunks: list[dict]) -> None:
        if not chunks:
            return

        started_at = perf_counter()
        await self.ensure_index()
        bulk_lines: list[str] = []
        now = datetime.now(timezone.utc).isoformat()

        for chunk in chunks:
            doc_id = chunk["chunk_id"]
            source = {
                "tenant_id": chunk["tenant_id"],
                "kb_id": chunk["kb_id"],
                "document_id": chunk["document_id"],
                "chunk_id": chunk["chunk_id"],
                "title": chunk["title"],
                "content": chunk["content"],
                "metadata": chunk.get("metadata", {}),
                "created_at": now,
            }
            bulk_lines.append(
                json.dumps(
                    {"index": {"_index": self.index_name, "_id": doc_id}},
                    ensure_ascii=False,
                )
            )
            bulk_lines.append(json.dumps(source, ensure_ascii=False, default=str))

        payload = "\n".join(bulk_lines) + "\n"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(
                    f"{self.base_url}/_bulk",
                    content=payload,
                    headers={"Content-Type": "application/x-ndjson"},
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            error_body = _response_text(exc)
            logger.error(
                "KEYWORD_INDEX_FAILED | provider=%s | index=%s | chunk_count=%s | "
                "error=%s | response_body=%s",
                self.name,
                self.index_name,
                len(chunks),
                str(exc),
                error_body,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise AppError(
                ErrorCode.KEYWORD_SEARCH_ERROR,
                internal_msg=f"elasticsearch bulk index failed: {exc}; response_body={error_body}",
                context={"index": self.index_name, "chunk_count": len(chunks)},
            ) from exc

        if body.get("errors"):
            logger.error(
                "KEYWORD_INDEX_FAILED | provider=%s | index=%s | chunk_count=%s | response=%s",
                self.name,
                self.index_name,
                len(chunks),
                safe_json(body),
            )
            raise AppError(
                ErrorCode.KEYWORD_SEARCH_ERROR,
                internal_msg="elasticsearch bulk index returned item errors",
                context={"index": self.index_name, "chunk_count": len(chunks), "response": body},
            )

        cost_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "KEYWORD_INDEX_SUCCESS | provider=%s | index=%s | chunk_count=%s | cost_ms=%.2f",
            self.name,
            self.index_name,
            len(chunks),
            cost_ms,
        )

    async def keyword_search(
        self,
        *,
        query: str,
        tenant_id: str,
        kb_id: str,
        top_k: int = 20,
    ) -> list[dict]:
        started_at = perf_counter()
        payload: dict[str, Any] = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"tenant_id": tenant_id}},
                        {"term": {"kb_id": kb_id}},
                    ],
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^2", "content"],
                        }
                    },
                }
            },
            "size": top_k,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(
                    f"{self.base_url}/{self.index_name}/_search",
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            error_body = _response_text(exc)
            logger.error(
                "BM25_SEARCH_FAILED | provider=%s | index=%s | tenant_id=%s | kb_id=%s | "
                "top_k=%s | error=%s | response_body=%s",
                self.name,
                self.index_name,
                tenant_id,
                kb_id,
                top_k,
                str(exc),
                error_body,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise AppError(
                ErrorCode.KEYWORD_SEARCH_ERROR,
                internal_msg=f"elasticsearch bm25 search failed: {exc}; response_body={error_body}",
                context={"index": self.index_name, "tenant_id": tenant_id, "kb_id": kb_id},
            ) from exc

        results: list[dict] = []
        for hit in body.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            results.append(
                {
                    "document_id": source.get("document_id"),
                    "chunk_id": source.get("chunk_id"),
                    "title": source.get("title", ""),
                    "content": source.get("content", ""),
                    "bm25_score": float(hit.get("_score") or 0.0),
                    "metadata": source.get("metadata", {}),
                }
            )

        cost_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "BM25_SEARCH_SUCCESS | provider=%s | index=%s | tenant_id=%s | kb_id=%s | "
            "top_k=%s | result_count=%s | cost_ms=%.2f",
            self.name,
            self.index_name,
            tenant_id,
            kb_id,
            top_k,
            len(results),
            cost_ms,
        )
        return results

    async def delete_by_document_id(self, document_id: str) -> None:
        payload = {"query": {"term": {"document_id": document_id}}}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(
                    f"{self.base_url}/{self.index_name}/_delete_by_query",
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            error_body = _response_text(exc)
            logger.error(
                "KEYWORD_DELETE_FAILED | provider=%s | index=%s | document_id=%s | "
                "error=%s | response_body=%s",
                self.name,
                self.index_name,
                document_id,
                str(exc),
                error_body,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise AppError(
                ErrorCode.KEYWORD_SEARCH_ERROR,
                internal_msg=f"elasticsearch delete failed: {exc}; response_body={error_body}",
                context={"index": self.index_name, "document_id": document_id},
            ) from exc

    async def ensure_index(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.head(f"{self.base_url}/{self.index_name}")
                if response.status_code == 200:
                    return
                if response.status_code != 404:
                    response.raise_for_status()

                create_response = await client.put(
                    f"{self.base_url}/{self.index_name}",
                    json=self._index_body(),
                )
                create_response.raise_for_status()
        except httpx.HTTPError as exc:
            error_body = _response_text(exc)
            logger.error(
                "KEYWORD_INDEX_INIT_FAILED | provider=%s | index=%s | error=%s | response_body=%s",
                self.name,
                self.index_name,
                str(exc),
                error_body,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise AppError(
                ErrorCode.KEYWORD_SEARCH_ERROR,
                internal_msg=f"elasticsearch index init failed: {exc}; response_body={error_body}",
                context={"index": self.index_name},
            ) from exc

    def _index_body(self) -> dict[str, Any]:
        return {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "ik_smart",
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "tenant_id": {"type": "keyword"},
                    "kb_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "search_analyzer": "ik_smart",
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "ik_max_word",
                        "search_analyzer": "ik_smart",
                    },
                    "metadata": {"type": "object", "enabled": True},
                    "created_at": {"type": "date"},
                }
            },
        }


def _response_text(exc: httpx.HTTPError) -> str | None:
    response = getattr(exc, "response", None)
    return response.text if response is not None else None
