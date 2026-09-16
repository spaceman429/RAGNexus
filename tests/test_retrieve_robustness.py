import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppError, ErrorCode
from app.services.rag_service import RagService


def _sample_vector_chunk(chunk_id: str = "chunk-1") -> dict:
    return {
        "document_id": "doc-1",
        "chunk_id": chunk_id,
        "title": "title",
        "content": "content",
        "score": 0.9,
        "metadata": {},
    }


def _sample_bm25_chunk(chunk_id: str = "chunk-2") -> dict:
    return {
        "document_id": "doc-2",
        "chunk_id": chunk_id,
        "title": "title",
        "content": "content",
        "bm25_score": 1.2,
        "metadata": {},
    }


def _hybrid_metadata(**overrides) -> dict:
    base = {
        "mode": "hybrid",
        "fusion": "rrf",
        "rrf_k": 60,
        "vector_store": "pgvector",
        "keyword_search": "elasticsearch",
        "vector_top_k": 20,
        "bm25_top_k": 20,
        "vector_count": 1,
        "bm25_count": 1,
        "fused_count": 1,
        "degraded": False,
        "degraded_reason": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def rag_service() -> RagService:
    return RagService(MagicMock())


def test_hybrid_degrades_to_bm25_when_vector_fails(rag_service: RagService) -> None:
    rag_service._vector_search = AsyncMock(side_effect=RuntimeError("embedding down"))
    rag_service._bm25_search = AsyncMock(return_value=[_sample_bm25_chunk()])
    rag_service._get_vector_top_k = MagicMock(return_value=20)
    rag_service._get_bm25_top_k = MagicMock(return_value=20)
    rag_service._get_rrf_k = MagicMock(return_value=60)

    chunks, metadata = asyncio.run(
        rag_service._retrieve_candidates_for_kb(
            tenant_id="tenant-a",
            request=MagicMock(retrieval_options=None),
            kb_id="kb-1",
            search_query="test query",
            mode="hybrid",
            per_kb_top_k=10,
        )
    )

    assert metadata["degraded"] is True
    assert metadata["degraded_reason"] == "vector search failed"
    assert len(chunks) == 1
    assert chunks[0]["retrieval_source"] == "bm25"


def test_hybrid_degrades_to_vector_when_bm25_fails(rag_service: RagService) -> None:
    rag_service._vector_search = AsyncMock(return_value=[_sample_vector_chunk()])
    rag_service._bm25_search = AsyncMock(side_effect=RuntimeError("es down"))
    rag_service._get_vector_top_k = MagicMock(return_value=20)
    rag_service._get_bm25_top_k = MagicMock(return_value=20)
    rag_service._get_rrf_k = MagicMock(return_value=60)

    chunks, metadata = asyncio.run(
        rag_service._retrieve_candidates_for_kb(
            tenant_id="tenant-a",
            request=MagicMock(retrieval_options=None),
            kb_id="kb-1",
            search_query="test query",
            mode="hybrid",
            per_kb_top_k=10,
        )
    )

    assert metadata["degraded"] is True
    assert metadata["degraded_reason"] == "bm25 search failed"
    assert chunks[0]["retrieval_source"] == "vector"


def test_hybrid_raises_when_both_paths_fail(rag_service: RagService) -> None:
    rag_service._vector_search = AsyncMock(side_effect=RuntimeError("embedding down"))
    rag_service._bm25_search = AsyncMock(side_effect=RuntimeError("es down"))
    rag_service._get_vector_top_k = MagicMock(return_value=20)
    rag_service._get_bm25_top_k = MagicMock(return_value=20)
    rag_service._get_rrf_k = MagicMock(return_value=60)

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            rag_service._retrieve_candidates_for_kb(
                tenant_id="tenant-a",
                request=MagicMock(retrieval_options=None),
                kb_id="kb-1",
                search_query="test query",
                mode="hybrid",
                per_kb_top_k=10,
            )
        )

    assert exc_info.value.code == ErrorCode.RETRIEVAL_FAILED.code


def test_multi_kb_partial_failure_keeps_successful_library(rag_service: RagService) -> None:
    kb_ok = MagicMock(id="kb-ok", name="OK")
    kb_bad = MagicMock(id="kb-bad", name="BAD")

    async def retrieve_side_effect(**kwargs):
        if kwargs["kb_id"] == "kb-bad":
            raise RuntimeError("kb retrieval failed")
        return (
            [_sample_vector_chunk("ok-chunk")],
            _hybrid_metadata(),
        )

    rag_service._retrieve_candidates_for_kb = AsyncMock(side_effect=retrieve_side_effect)
    rag_service._get_rrf_k = MagicMock(return_value=60)

    chunks, metadata = asyncio.run(
        rag_service._retrieve_multi_kb(
            tenant_id="tenant-a",
            request=MagicMock(retrieval_options=None),
            knowledge_bases=[kb_ok, kb_bad],
            search_query="test query",
            mode="hybrid",
            top_k=5,
            per_kb_top_k=10,
        )
    )

    assert metadata["partial_kb_success"] is True
    assert metadata["failed_kb_ids"] == ["kb-bad"]
    assert metadata["degraded"] is True
    assert len(chunks) == 1
    assert chunks[0]["kb_id"] == "kb-ok"


def test_multi_kb_all_failed_raises(rag_service: RagService) -> None:
    kb_a = MagicMock(id="kb-a", name="A")
    kb_b = MagicMock(id="kb-b", name="B")
    rag_service._retrieve_candidates_for_kb = AsyncMock(
        side_effect=RuntimeError("retrieval failed"),
    )

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            rag_service._retrieve_multi_kb(
                tenant_id="tenant-a",
                request=MagicMock(retrieval_options=None),
                knowledge_bases=[kb_a, kb_b],
                search_query="test query",
                mode="hybrid",
                top_k=5,
                per_kb_top_k=10,
            )
        )

    assert exc_info.value.code == ErrorCode.RETRIEVAL_FAILED.code


def test_resolve_empty_reason_no_indexed_chunks(rag_service: RagService) -> None:
    rag_service.chunk_repository.count_by_kb_id = MagicMock(return_value=0)

    reason = rag_service._resolve_empty_reason("tenant-a", ["kb-1"], [])

    assert reason == "no_indexed_chunks"


def test_resolve_empty_reason_no_chunks_matched(rag_service: RagService) -> None:
    rag_service.chunk_repository.count_by_kb_id = MagicMock(return_value=3)

    reason = rag_service._resolve_empty_reason("tenant-a", ["kb-1"], [])

    assert reason == "no_chunks_matched"
