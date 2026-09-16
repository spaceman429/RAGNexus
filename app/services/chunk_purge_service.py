from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.keyword_search.elasticsearch import ElasticsearchKeywordSearchProvider
from app.repositories.chunk_repository import ChunkRepository

logger = get_logger(__name__)


async def purge_document_chunks(db: Session, document_id: str) -> None:
    ChunkRepository(db).delete_by_document_id(document_id)
    if settings.keyword_search_provider == "elasticsearch":
        await ElasticsearchKeywordSearchProvider().delete_by_document_id(document_id)
    logger.info(
        "BUSINESS_NODE | purge_document_chunks_success | document_id=%s | keyword_search=%s",
        document_id,
        settings.keyword_search_provider,
    )
