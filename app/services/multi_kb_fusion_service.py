from app.core.logging import get_logger

logger = get_logger(__name__)


class MultiKbFusionService:
    def fuse_by_rrf(
        self,
        *,
        chunks_by_kb: list[list[dict]],
        rrf_k: int,
        top_n: int,
    ) -> list[dict]:
        fused: list[dict] = []
        for kb_chunks in chunks_by_kb:
            for rank, chunk in enumerate(kb_chunks, start=1):
                fused.append(
                    {
                        **chunk,
                        "score": 1.0 / (rrf_k + rank),
                        "kb_rank": rank,
                    }
                )

        fused.sort(key=lambda item: item["score"], reverse=True)
        results = fused[:top_n]
        logger.info(
            "MULTI_KB_RRF_SUCCESS | kb_count=%s | candidate_count=%s | fused_count=%s | rrf_k=%s | top_n=%s",
            len(chunks_by_kb),
            sum(len(group) for group in chunks_by_kb),
            len(results),
            rrf_k,
            top_n,
        )
        return results
