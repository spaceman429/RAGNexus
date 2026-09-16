from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.services.chunk_purge_service import purge_document_chunks
from app.tasks.indexing import index_document_task
from app.utils.status import DocumentStatus

logger = get_logger(__name__)


async def queue_document_reindex(db: Session, document: Document, *, reparse: bool = False) -> None:
    if document.status == DocumentStatus.PROCESSING:
        raise ValueError(f"document is processing: {document.id}")

    prior_status = document.status
    await purge_document_chunks(db, document.id)
    DocumentRepository(db).update_status(
        document,
        status=DocumentStatus.PROCESSING,
        error_message=None,
    )
    if reparse:
        document.content = ""
        db.flush()
    db.commit()
    index_document_task.delay(document.id, reparse=reparse)
    logger.info(
        "BUSINESS_NODE | queue_document_reindex | document_id=%s | kb_id=%s | prior_status=%s",
        document.id,
        document.kb_id,
        prior_status,
    )
