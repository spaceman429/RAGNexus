from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, tenant: Tenant) -> Tenant:
        self.db.add(tenant)
        self.db.flush()
        return tenant

    def get_by_id(self, tenant_id: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        return self.db.scalar(stmt)

    def exists(self, tenant_id: str) -> bool:
        return self.get_by_id(tenant_id) is not None

    def update_plan(self, tenant: Tenant, plan: str) -> Tenant:
        tenant.plan = plan
        self.db.flush()
        return tenant
