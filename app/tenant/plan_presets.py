from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlanName = Literal["free", "standard", "pro"]
RetrieveProfileName = Literal["speed", "balanced", "quality", "custom"]

VALID_PLANS: frozenset[str] = frozenset({"free", "standard", "pro"})


@dataclass(frozen=True, slots=True)
class PlanFeatures:
    allowed_profiles: frozenset[str]
    hybrid_allowed: bool
    rerank_allowed: bool
    query_rewrite_allowed: bool


@dataclass(frozen=True, slots=True)
class PlanLimits:
    retrieve_qps: int
    daily_retrieve_limit: int
    max_kb: int
    max_kb_per_retrieve: int
    max_documents_per_kb: int
    max_processing_documents: int


@dataclass(frozen=True, slots=True)
class PlanPreset:
    features: PlanFeatures
    limits: PlanLimits


PLAN_PRESETS: dict[PlanName, PlanPreset] = {
    "free": PlanPreset(
        features=PlanFeatures(
            allowed_profiles=frozenset({"speed"}),
            hybrid_allowed=False,
            rerank_allowed=False,
            query_rewrite_allowed=False,
        ),
        limits=PlanLimits(
            retrieve_qps=3,
            daily_retrieve_limit=500,
            max_kb=1,
            max_kb_per_retrieve=1,
            max_documents_per_kb=30,
            max_processing_documents=1,
        ),
    ),
    "standard": PlanPreset(
        features=PlanFeatures(
            allowed_profiles=frozenset({"speed", "balanced", "custom"}),
            hybrid_allowed=True,
            rerank_allowed=False,
            query_rewrite_allowed=False,
        ),
        limits=PlanLimits(
            retrieve_qps=10,
            daily_retrieve_limit=5_000,
            max_kb=5,
            max_kb_per_retrieve=3,
            max_documents_per_kb=200,
            max_processing_documents=2,
        ),
    ),
    "pro": PlanPreset(
        features=PlanFeatures(
            allowed_profiles=frozenset({"speed", "balanced", "quality", "custom"}),
            hybrid_allowed=True,
            rerank_allowed=True,
            query_rewrite_allowed=True,
        ),
        limits=PlanLimits(
            retrieve_qps=50,
            daily_retrieve_limit=100_000,
            max_kb=50,
            max_kb_per_retrieve=5,
            max_documents_per_kb=5_000,
            max_processing_documents=10,
        ),
    ),
}

DEFAULT_RETRIEVE_PROFILE: RetrieveProfileName = "balanced"
