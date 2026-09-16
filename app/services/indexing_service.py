from sqlalchemy.orm import Session

from app.core.config import settings
import httpx

from app.core.exceptions import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.document import Document
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.openai_compatible import OpenAICompatibleEmbeddingProvider
from app.providers.keyword_search.base import KeywordSearchProvider
from app.providers.keyword_search.elasticsearch import ElasticsearchKeywordSearchProvider
from app.providers.vectorstores.base import VectorStore
from app.providers.vectorstores.pgvector import PgVectorStore
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.document import UploadDocumentRequest
from app.services.document_ingestion import prepare_document_content
from app.utils.id_generator import generate_uuid
from app.utils.status import DocumentStatus
from app.utils.markdown_splitter import MarkdownStructuredSplitter, SplitPiece

logger = get_logger(__name__)

RETRYABLE_ERROR_CODES = {
    ErrorCode.API_TIMEOUT.code,
    ErrorCode.API_REQUEST_ERROR.code,
    ErrorCode.EMBEDDING_FAILED.code,
    ErrorCode.SYSTEM_BUSY.code,
}


def create_indexing_service(db: Session) -> "IndexingService":
    keyword_search_provider = None
    if settings.keyword_search_provider == "elasticsearch":
        keyword_search_provider = ElasticsearchKeywordSearchProvider()

    return IndexingService(
        db,
        embedding_provider=OpenAICompatibleEmbeddingProvider(),
        vector_store=PgVectorStore(db),
        keyword_search_provider=keyword_search_provider,
        text_splitter=MarkdownStructuredSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            table_max_rows_per_chunk=settings.table_max_rows_per_chunk,
        ),
    )


class IndexingService:
    def __init__(
        self,
        db: Session,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        keyword_search_provider: KeywordSearchProvider | None = None,
        text_splitter: MarkdownStructuredSplitter,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.keyword_search_provider = keyword_search_provider
        self.text_splitter = text_splitter
        self.knowledge_base_repository = KnowledgeBaseRepository(db)
        self.document_repository = DocumentRepository(db)

    def create_document_record(self, tenant_id: str, request: UploadDocumentRequest) -> Document:
        logger.info(
            "BUSINESS_NODE | create_document_record_start | tenant_id=%s | kb_id=%s | title=%s | content_chars=%s",
            tenant_id,
            request.kb_id,
            request.title,
            len(request.content),
        )
        knowledge_base = self.knowledge_base_repository.get_by_id_and_tenant(
            request.kb_id,
            tenant_id,
        )
        if knowledge_base is None:
            raise AppError(
                ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                context={"tenant_id": tenant_id, "kb_id": request.kb_id},
            )

        document = Document(
            id=generate_uuid(),
            tenant_id=tenant_id,
            kb_id=request.kb_id,
            title=request.title,
            content=request.content,
            source_type="text",
            status=DocumentStatus.PROCESSING,
        )
        self.document_repository.create(document)
        self.db.commit()
        self.db.refresh(document)

        logger.info(
            "BUSINESS_NODE | create_document_record_success | document_id=%s | kb_id=%s",
            document.id,
            document.kb_id,
        )
        return document

    def create_file_document_record(
        self,
        tenant_id: str,
        *,
        kb_id: str,
        title: str,
        source_file_path: str,
        source_filename: str,
        document_id: str | None = None,
    ) -> Document:
        logger.info(
            "BUSINESS_NODE | create_file_document_record_start | tenant_id=%s | kb_id=%s | "
            "title=%s | source_filename=%s",
            tenant_id,
            kb_id,
            title,
            source_filename,
        )
        knowledge_base = self.knowledge_base_repository.get_by_id_and_tenant(kb_id, tenant_id)
        if knowledge_base is None:
            raise AppError(
                ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                context={"tenant_id": tenant_id, "kb_id": kb_id},
            )

        document = Document(
            id=document_id or generate_uuid(),
            tenant_id=tenant_id,
            kb_id=kb_id,
            title=title,
            content="",
            source_type="text",
            source_file_path=source_file_path,
            source_filename=source_filename,
            status=DocumentStatus.PROCESSING,
        )
        self.document_repository.create(document)
        self.db.commit()
        self.db.refresh(document)

        logger.info(
            "BUSINESS_NODE | create_file_document_record_success | document_id=%s | kb_id=%s",
            document.id,
            document.kb_id,
        )
        return document

    async def index_existing_document(self, document_id: str, *, reparse: bool = False) -> int:
        document = self.document_repository.get_by_id(document_id)
        if document is None:
            logger.warning(
                "BUSINESS_NODE | index_existing_document_skip | document_id=%s | reason=not_found",
                document_id,
            )
            return 0

        if document.status != DocumentStatus.PROCESSING:
            logger.info(
                "BUSINESS_NODE | index_existing_document_skip | document_id=%s | status=%s",
                document_id,
                document.status,
            )
            return 0

        logger.info(
            "BUSINESS_NODE | index_existing_document_start | document_id=%s | kb_id=%s | title=%s",
            document.id,
            document.kb_id,
            document.title,
        )

        needs_prepare = bool(document.source_file_path) and (
            reparse or not document.content.strip()
        )
        if needs_prepare:
            try:
                parsed = await prepare_document_content(
                    content=document.content if not reparse and document.content.strip() else None,
                    file_path=document.source_file_path,
                    filename=document.source_filename,
                )
                document.content = parsed.content
                document.source_type = parsed.source_type
                self.db.commit()
                self.db.refresh(document)
            except AppError as exc:
                self.db.rollback()
                self._mark_failed(document, exc.msg)
                logger.error(
                    "BUSINESS_NODE | index_existing_document_parse_failed | document_id=%s | "
                    "code=%s | msg=%s",
                    document.id,
                    exc.code,
                    exc.msg,
                )
                return 0
            except Exception as exc:
                self.db.rollback()
                self._mark_failed(document, f"文档解析失败: {exc}")
                logger.exception(
                    "BUSINESS_NODE | index_existing_document_parse_unhandled | document_id=%s",
                    document.id,
                )
                return 0

        if not document.content.strip():
            self._mark_failed(document, ErrorCode.DOCUMENT_CONTENT_EMPTY.msg)
            return 0

        try:
            chunk_count = await self._index_document_content(document)
            self.document_repository.update_status(document, status=DocumentStatus.SUCCESS)
            self.db.commit()
            logger.info(
                "BUSINESS_NODE | index_existing_document_success | document_id=%s | kb_id=%s | "
                "chunk_count=%s | keyword_search=%s",
                document.id,
                document.kb_id,
                chunk_count,
                self.keyword_search_provider.name if self.keyword_search_provider else None,
            )
            return chunk_count
        except AppError as exc:
            self.db.rollback()
            if exc.code in RETRYABLE_ERROR_CODES:
                logger.warning(
                    "BUSINESS_NODE | index_existing_document_retryable | document_id=%s | code=%s | msg=%s",
                    document.id,
                    exc.code,
                    exc.msg,
                )
                raise
            self._mark_failed(document, exc.msg)
            logger.error(
                "BUSINESS_NODE | index_existing_document_failed | document_id=%s | code=%s | msg=%s",
                document.id,
                exc.code,
                exc.msg,
            )
            return 0
        except Exception as exc:
            self.db.rollback()
            if isinstance(
                exc,
                (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, ConnectionError),
            ):
                logger.warning(
                    "BUSINESS_NODE | index_existing_document_retryable | document_id=%s | error=%s",
                    document.id,
                    str(exc),
                )
                raise
            logger.exception(
                "BUSINESS_NODE | index_existing_document_unhandled | document_id=%s | error=%s",
                document.id,
                str(exc),
            )
            self._mark_failed(document, str(exc))
            return 0

    async def _index_document_content(self, document: Document) -> int:
        pieces: list[SplitPiece] = self.text_splitter.split(document.content)
        if not pieces:
            raise AppError(ErrorCode.DOCUMENT_CONTENT_EMPTY)

        logger.info(
            "BUSINESS_NODE | document_split_success | document_id=%s | chunk_count=%s",
            document.id,
            len(pieces),
        )

        texts = [piece.text for piece in pieces]
        embeddings = await self.embedding_provider.embed_texts(texts)
        chunks = [
            {
                "chunk_id": generate_uuid(),
                "tenant_id": document.tenant_id,
                "kb_id": document.kb_id,
                "document_id": document.id,
                "title": document.title,
                "content": piece.text,
                "metadata": {
                    "chunk_index": index,
                    "source_type": document.source_type,
                    **piece.metadata,
                },
                "embedding": embedding,
            }
            for index, (piece, embedding) in enumerate(zip(pieces, embeddings, strict=True))
        ]

        await self.vector_store.add_chunks(chunks)
        if self.keyword_search_provider is not None:
            await self.keyword_search_provider.add_chunks(chunks)

        return len(chunks)

    def _mark_failed(self, document: Document, error_message: str) -> None:
        self.document_repository.update_status(
            document,
            status=DocumentStatus.FAILED,
            error_message=error_message,
        )
        self.db.commit()
