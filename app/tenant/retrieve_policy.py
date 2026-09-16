from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import AppError, ErrorCode
from app.schemas.rag import (
    QueryOptions,
    RerankOptions,
    RetrievalOptions,
    RetrieveRequest,
    TenantPolicyMetadata,
)
from app.tenant.plan_presets import DEFAULT_RETRIEVE_PROFILE, RetrieveProfileName
from app.tenant.plan_resolver import PlanContext
from app.tenant.retrieve_presets import RETRIEVE_PROFILE_PRESETS


def resolve_retrieve_request(
    request: RetrieveRequest,
    plan_context: PlanContext,
) -> tuple[RetrieveRequest, TenantPolicyMetadata]:
    profile: RetrieveProfileName = request.profile or DEFAULT_RETRIEVE_PROFILE

    if profile not in plan_context.features.allowed_profiles:
        raise AppError(
            ErrorCode.FEATURE_NOT_ALLOWED,
            msg=f"当前套餐（{plan_context.plan}）不支持检索预设 {profile}",
            context={"plan": plan_context.plan, "profile": profile},
        )

    if profile == "custom":
        top_k = request.top_k or settings.top_k
        retrieval_options = request.retrieval_options or RetrievalOptions(
            mode=settings.retrieval_mode,
        )
        rerank_options = request.rerank_options or RerankOptions(
            enabled=settings.rerank_enabled,
        )
        query_options = request.query_options or QueryOptions(
            enabled=settings.query_rewrite_enabled,
            strategy="rewrite" if settings.query_rewrite_enabled else "noop",
        )
    else:
        preset = RETRIEVE_PROFILE_PRESETS[profile]
        assert preset is not None
        top_k = request.top_k or preset.top_k or settings.top_k
        retrieval_options = _build_retrieval_options(preset.retrieval_options, request.retrieval_options)
        rerank_options = _build_rerank_options(preset.rerank_options, request.rerank_options)
        query_options = _build_query_options(preset.query_options, request.query_options)

    _validate_plan_ceiling(plan_context, profile, retrieval_options, rerank_options, query_options)

    kb_ids = request.kb_ids or []
    if len(kb_ids) > plan_context.limits.max_kb_per_retrieve:
        raise AppError(
            ErrorCode.FEATURE_NOT_ALLOWED,
            msg=(
                f"当前套餐（{plan_context.plan}）最多支持 "
                f"{plan_context.limits.max_kb_per_retrieve} 个知识库联合检索"
            ),
            context={
                "plan": plan_context.plan,
                "profile": profile,
                "kb_count": len(kb_ids),
                "max_kb_per_retrieve": plan_context.limits.max_kb_per_retrieve,
            },
        )

    effective_rerank = _effective_rerank_enabled(rerank_options)
    effective_query_rewrite = _effective_query_rewrite_enabled(query_options)

    rerank_options = RerankOptions(
        enabled=effective_rerank,
        top_n=rerank_options.top_n,
    )
    if not effective_query_rewrite:
        query_options = QueryOptions(enabled=False, strategy="noop")

    mode = retrieval_options.mode or settings.retrieval_mode
    resolved = request.model_copy(
        update={
            "top_k": top_k,
            "retrieval_options": retrieval_options,
            "rerank_options": rerank_options,
            "query_options": query_options,
        }
    )
    tenant_policy = TenantPolicyMetadata(
        plan=plan_context.plan,
        retrieve_profile=profile,
        effective_mode=mode,
        effective_rerank=effective_rerank,
        effective_query_rewrite=effective_query_rewrite,
        max_kb_per_retrieve=plan_context.limits.max_kb_per_retrieve,
        actual_kb_count=len(kb_ids),
    )
    return resolved, tenant_policy


def _build_retrieval_options(
    preset: dict | None,
    override: RetrievalOptions | None,
) -> RetrievalOptions:
    base = preset or {}
    if override is None:
        return RetrievalOptions(**base)
    merged = {**base, **override.model_dump(exclude_none=True)}
    return RetrievalOptions(**merged)


def _build_rerank_options(
    preset: dict | None,
    override: RerankOptions | None,
) -> RerankOptions:
    base = preset or {}
    if override is None:
        return RerankOptions(**base)
    merged = {**base, **override.model_dump(exclude_none=True)}
    return RerankOptions(**merged)


def _build_query_options(
    preset: dict | None,
    override: QueryOptions | None,
) -> QueryOptions:
    base = preset or {}
    if override is None:
        return QueryOptions(**base)
    merged = {**base, **override.model_dump(exclude_none=True)}
    return QueryOptions(**merged)


def _validate_plan_ceiling(
    plan_context: PlanContext,
    profile: str,
    retrieval_options: RetrievalOptions,
    rerank_options: RerankOptions,
    query_options: QueryOptions,
) -> None:
    mode = retrieval_options.mode or settings.retrieval_mode
    if mode == "hybrid" and not plan_context.features.hybrid_allowed:
        raise AppError(
            ErrorCode.FEATURE_NOT_ALLOWED,
            msg=f"当前套餐（{plan_context.plan}）不支持 hybrid 检索",
            context={"plan": plan_context.plan, "profile": profile, "mode": mode},
        )

    if _requested_rerank_enabled(rerank_options) and not plan_context.features.rerank_allowed:
        raise AppError(
            ErrorCode.FEATURE_NOT_ALLOWED,
            msg=f"当前套餐（{plan_context.plan}）不支持 rerank",
            context={"plan": plan_context.plan, "profile": profile},
        )

    if _requested_query_rewrite_enabled(query_options) and not plan_context.features.query_rewrite_allowed:
        raise AppError(
            ErrorCode.FEATURE_NOT_ALLOWED,
            msg=f"当前套餐（{plan_context.plan}）不支持 query 改写",
            context={"plan": plan_context.plan, "profile": profile},
        )


def _requested_rerank_enabled(rerank_options: RerankOptions) -> bool:
    if rerank_options.enabled is not None:
        return rerank_options.enabled
    return settings.rerank_enabled


def _requested_query_rewrite_enabled(query_options: QueryOptions) -> bool:
    if query_options.enabled is not None:
        if not query_options.enabled:
            return False
    elif not settings.query_rewrite_enabled:
        return False

    if query_options.strategy == "noop":
        return False
    return True


def _effective_rerank_enabled(rerank_options: RerankOptions) -> bool:
    if not _requested_rerank_enabled(rerank_options):
        return False
    if not settings.rerank_enabled or settings.rerank_provider == "noop":
        return False
    return True


def _effective_query_rewrite_enabled(query_options: QueryOptions) -> bool:
    if not _requested_query_rewrite_enabled(query_options):
        return False
    if not settings.query_rewrite_enabled:
        return False
    return True
