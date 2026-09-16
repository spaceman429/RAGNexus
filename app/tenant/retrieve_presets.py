from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tenant.plan_presets import RetrieveProfileName


@dataclass(frozen=True, slots=True)
class RetrieveProfilePreset:
    """Options bundle for a retrieve profile; consumed by 02 enforcement."""

    top_k: int | None = None
    retrieval_options: dict[str, Any] | None = None
    rerank_options: dict[str, Any] | None = None
    query_options: dict[str, Any] | None = None


RETRIEVE_PROFILE_PRESETS: dict[RetrieveProfileName, RetrieveProfilePreset | None] = {
    "speed": RetrieveProfilePreset(
        top_k=3,
        retrieval_options={"mode": "vector"},
        rerank_options={"enabled": False},
        query_options={"enabled": False, "strategy": "noop"},
    ),
    "balanced": RetrieveProfilePreset(
        top_k=5,
        retrieval_options={
            "mode": "hybrid",
            "vector_top_k": 10,
            "bm25_top_k": 10,
        },
        rerank_options={"enabled": False},
        query_options={"enabled": False, "strategy": "noop"},
    ),
    "quality": RetrieveProfilePreset(
        top_k=8,
        retrieval_options={
            "mode": "hybrid",
            "vector_top_k": 20,
            "bm25_top_k": 20,
        },
        rerank_options={"enabled": True},
        query_options={"enabled": True, "strategy": "rewrite"},
    ),
    "custom": None,
}
