from app.core.exceptions import AppError, ErrorCode
from app.schemas.rag import RetrieveRequest
from app.tenant.plan_presets import PLAN_PRESETS
from app.tenant.plan_resolver import PlanContext, PlanResolver
from app.tenant.retrieve_policy import resolve_retrieve_request
import pytest


def test_free_plan_rejects_multi_kb_retrieve():
    plan_context = PlanContext(
        plan="free",
        features=PLAN_PRESETS["free"].features,
        limits=PLAN_PRESETS["free"].limits,
    )
    request = RetrieveRequest(
        kb_ids=["kb-a", "kb-b"],
        user_id="user",
        query="test",
        profile="speed",
    )
    with pytest.raises(AppError) as exc_info:
        resolve_retrieve_request(request, plan_context)
    assert exc_info.value.code == ErrorCode.FEATURE_NOT_ALLOWED.code


def test_standard_plan_allows_three_kbs():
    plan_context = PlanContext(
        plan="standard",
        features=PLAN_PRESETS["standard"].features,
        limits=PLAN_PRESETS["standard"].limits,
    )
    request = RetrieveRequest(
        kb_ids=["kb-a", "kb-b", "kb-c"],
        user_id="user",
        query="test",
        profile="balanced",
    )
    resolved, policy = resolve_retrieve_request(request, plan_context)
    assert resolved.kb_ids == ["kb-a", "kb-b", "kb-c"]
    assert policy.max_kb_per_retrieve == 3
    assert policy.actual_kb_count == 3
