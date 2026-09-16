from app.core.logging import get_logger

logger = get_logger(__name__)


class HybridSearchService:
    def fuse_by_rrf(
        self,
        *,
        vector_chunks: list[dict],
        bm25_chunks: list[dict],
        rrf_k: int,
        top_n: int,
    ) -> list[dict]:
        merged: dict[str, dict] = {}

        for rank, chunk in enumerate(vector_chunks, start=1):
            chunk_id = chunk["chunk_id"]
            merged[chunk_id] = {
                "document_id": chunk["document_id"],
                "chunk_id": chunk_id,
                "title": chunk["title"],
                "content": chunk["content"],
                "metadata": chunk.get("metadata") or {},
                "vector_score": chunk.get("score"),
                "bm25_score": None,
                "vector_rank": rank,
                "bm25_rank": None,
            }

        for rank, chunk in enumerate(bm25_chunks, start=1):
            chunk_id = chunk["chunk_id"]
            existing = merged.get(chunk_id)
            if existing is None:
                merged[chunk_id] = {
                    "document_id": chunk["document_id"],
                    "chunk_id": chunk_id,
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "metadata": chunk.get("metadata") or {},
                    "vector_score": None,
                    "bm25_score": chunk.get("bm25_score"),
                    "vector_rank": None,
                    "bm25_rank": rank,
                }
            else:
                existing["bm25_score"] = chunk.get("bm25_score")
                existing["bm25_rank"] = rank
                if not existing.get("metadata") and chunk.get("metadata"):
                    existing["metadata"] = chunk.get("metadata")

        fused: list[dict] = []
        for chunk in merged.values():
            score = 0.0
            if chunk["vector_rank"] is not None:
                score += 1.0 / (rrf_k + chunk["vector_rank"])
            if chunk["bm25_rank"] is not None:
                score += 1.0 / (rrf_k + chunk["bm25_rank"])

            if chunk["vector_rank"] is not None and chunk["bm25_rank"] is not None:
                retrieval_source = "hybrid"
            elif chunk["vector_rank"] is not None:
                retrieval_source = "vector"
            else:
                retrieval_source = "bm25"

            fused.append(
                {
                    **chunk,
                    "score": score,
                    "retrieval_source": retrieval_source,
                }
            )

        fused.sort(key=lambda item: item["score"], reverse=True)
        results = fused[:top_n]
        logger.info(
            "RRF_FUSION_SUCCESS | vector_count=%s | bm25_count=%s | fused_count=%s | rrf_k=%s | top_n=%s",
            len(vector_chunks),
            len(bm25_chunks),
            len(fused),
            rrf_k,
            top_n,
        )
        return results
