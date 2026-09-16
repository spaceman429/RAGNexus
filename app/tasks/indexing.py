import asyncio

import httpx
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.exceptions import AppError, ErrorCode
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.repositories.document_repository import DocumentRepository
from app.services.indexing_service import create_indexing_service
from app.utils.status import DocumentStatus

logger = get_logger(__name__)

RETRYABLE_ERROR_CODES = {
    ErrorCode.API_TIMEOUT.code,
    ErrorCode.API_REQUEST_ERROR.code,
    ErrorCode.EMBEDDING_FAILED.code,
    ErrorCode.SYSTEM_BUSY.code,
}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, AppError):
        return exc.code in RETRYABLE_ERROR_CODES
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, ConnectionError)):
        return True
    return False


def _mark_document_failed(db: Session, document_id: str, error_message: str) -> None:
    repository = DocumentRepository(db)
    document = repository.get_by_id(document_id)
    if document is None or document.status != DocumentStatus.PROCESSING:
        return
    repository.update_status(
        document,
        status=DocumentStatus.FAILED,
        error_message=error_message,
    )
    db.commit()
    logger.error(
        "BUSINESS_NODE | index_document_task_failed | document_id=%s | error=%s",
        document_id,
        error_message,
    )


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def index_document_task(self, document_id: str, reparse: bool = False) -> None:
    db = SessionLocal()
    try:
        service = create_indexing_service(db)
        asyncio.run(service.index_existing_document(document_id, reparse=reparse))
    except Exception as exc:
        if _is_retryable(exc) and self.request.retries < self.max_retries:
            logger.warning(
                "BUSINESS_NODE | index_document_task_retry | document_id=%s | "
                "retry=%s | error_type=%s | error=%s",
                document_id,
                self.request.retries,
                type(exc).__name__,
                str(exc),
            )
            try:
                raise self.retry(exc=exc)
            except MaxRetriesExceededError:
                _mark_document_failed(
                    db,
                    document_id,
                    f"索引重试耗尽: {exc}",
                )
                raise
        if isinstance(exc, AppError):
            logger.error(
                "BUSINESS_NODE | index_document_task_app_error | document_id=%s | "
                "code=%s | msg=%s",
                document_id,
                exc.code,
                exc.msg,
            )
        else:
            _mark_document_failed(db, document_id, str(exc))
            logger.exception(
                "BUSINESS_NODE | index_document_task_unhandled | document_id=%s",
                document_id,
            )
            raise
    finally:
        db.close()
