from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_langfuse_client() -> Any | None:
    if not settings.langfuse_enabled:
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning("LANGFUSE_ENABLED=true but keys are missing; skipping trace export")
        return None

    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            httpx_client=httpx.Client(trust_env=False),
        )
    except Exception as exc:
        logger.warning(
            "LANGFUSE_INIT_FAILED | error_type=%s | error=%s",
            type(exc).__name__,
            str(exc),
        )
        return None


def _chunks_summary(chunks: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.get("chunk_id"),
            "document_id": chunk.get("document_id"),
            "title": chunk.get("title"),
            "score": chunk.get("score"),
            "retrieval_source": chunk.get("retrieval_source"),
        }
        for chunk in chunks
    ]


class RetrieveObservability:
    def __init__(self, log_id: str) -> None:
        self.log_id = log_id
        self.trace_id: str | None = None
        self._trace: Any | None = None
        self._langfuse: Any | None = None

    def start(
        self,
        *,
        tenant_id: str,
        kb_ids: list[str],
        user_id: str,
        raw_query: str,
        profile: str,
        plan: str,
        mode: str,
        top_k: int,
    ) -> None:
        primary_kb_id = kb_ids[0] if kb_ids else ""
        try:
            langfuse = get_langfuse_client()
            if langfuse is None:
                return

            self._langfuse = langfuse
            trace = langfuse.trace(
                name="rag_retrieve",
                user_id=user_id,
                input={
                    "query": raw_query,
                    "kb_id": primary_kb_id,
                    "kb_ids": kb_ids,
                    "profile": profile,
                    "mode": mode,
                    "top_k": top_k,
                },
                metadata={
                    "log_id": self.log_id,
                    "tenant_id": tenant_id,
                    "kb_id": primary_kb_id,
                    "kb_ids": kb_ids,
                    "user_id": user_id,
                    "profile": profile,
                    "plan": plan,
                    "mode": mode,
                },
            )
            self._trace = trace
            self.trace_id = trace.id
        except Exception as exc:
            logger.warning(
                "LANGFUSE_TRACE_START_FAILED | log_id=%s | error_type=%s | error=%s",
                self.log_id,
                type(exc).__name__,
                str(exc),
            )

    def record_query_processing(self, query_processing: dict[str, Any] | None) -> None:
        if self._trace is None:
            return
        try:
            payload = query_processing or {"enabled": False}
            self._trace.span(
                name="query_processing",
                input={"stage": "query_processing"},
                output=payload,
            )
        except Exception as exc:
            logger.warning(
                "LANGFUSE_SPAN_FAILED | span=query_processing | log_id=%s | error=%s",
                self.log_id,
                str(exc),
            )

    def record_retrieval(self, retrieval_metadata: dict[str, Any], *, latency_ms: int) -> None:
        if self._trace is None:
            return
        try:
            self._trace.span(
                name="retrieval",
                input={"stage": "retrieval"},
                output={**retrieval_metadata, "latency_ms": latency_ms},
            )
        except Exception as exc:
            logger.warning(
                "LANGFUSE_SPAN_FAILED | span=retrieval | log_id=%s | error=%s",
                self.log_id,
                str(exc),
            )

    def record_rerank(self, rerank_metadata: dict[str, Any]) -> None:
        if self._trace is None:
            return
        try:
            self._trace.span(
                name="rerank",
                input={"stage": "rerank"},
                output=rerank_metadata,
            )
        except Exception as exc:
            logger.warning(
                "LANGFUSE_SPAN_FAILED | span=rerank | log_id=%s | error=%s",
                self.log_id,
                str(exc),
            )

    def finish(self, chunks: list[dict], *, latency_ms: int) -> None:
        try:
            if self._trace is not None:
                self._trace.update(
                    output={
                        "returned_count": len(chunks),
                        "latency_ms": latency_ms,
                        "chunks": _chunks_summary(chunks),
                    }
                )
            if self._langfuse is not None:
                self._langfuse.flush()
        except Exception as exc:
            logger.warning(
                "LANGFUSE_TRACE_FINISH_FAILED | log_id=%s | error_type=%s | error=%s",
                self.log_id,
                type(exc).__name__,
                str(exc),
            )
