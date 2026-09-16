from __future__ import annotations

from dataclasses import dataclass

from app.models.tenant import Tenant
from app.tenant.plan_presets import (
    PLAN_PRESETS,
    PlanFeatures,
    PlanLimits,
    PlanName,
    VALID_PLANS,
)


@dataclass(frozen=True, slots=True)
class PlanContext:
    plan: PlanName
    features: PlanFeatures
    limits: PlanLimits


class PlanResolver:
    @staticmethod
    def resolve_plan(tenant: Tenant) -> PlanContext:
        plan = tenant.plan if tenant.plan in VALID_PLANS else "free"
        preset = PLAN_PRESETS[plan]  # type: ignore[index]
        return PlanContext(plan=plan, features=preset.features, limits=preset.limits)
