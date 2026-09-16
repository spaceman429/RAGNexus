from sqlalchemy.orm import Session

from app.models.retrieval_log import RetrievalLog


class RetrievalLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, retrieval_log: RetrievalLog) -> RetrievalLog:
        self.db.add(retrieval_log)
        self.db.flush()
        return retrieval_log

    def get_by_id_and_tenant(self, log_id: str, tenant_id: str) -> RetrievalLog | None:
        return (
            self.db.query(RetrievalLog)
            .filter(RetrievalLog.id == log_id, RetrievalLog.tenant_id == tenant_id)
            .one_or_none()
        )

