from app.services.multi_kb_fusion_service import MultiKbFusionService


def test_multi_kb_rrf_balances_libraries():
    kb_a = [
        {"chunk_id": "a1", "score": 0.99, "content": "A1"},
        {"chunk_id": "a2", "score": 0.98, "content": "A2"},
    ]
    kb_b = [
        {"chunk_id": "b1", "score": 0.50, "content": "B1"},
        {"chunk_id": "b2", "score": 0.40, "content": "B2"},
    ]
    fused = MultiKbFusionService().fuse_by_rrf(
        chunks_by_kb=[kb_a, kb_b],
        rrf_k=60,
        top_n=2,
    )
    chunk_ids = {item["chunk_id"] for item in fused}
    assert chunk_ids == {"a1", "b1"}
