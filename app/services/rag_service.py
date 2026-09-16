import asyncio
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.knowledge_base import KnowledgeBase
from app.models.retrieval_log import RetrievalLog
from app.observability.langfuse_client import RetrieveObservability
from app.providers.embedding.openai_compatible import OpenAICompatibleEmbeddingProvider
from app.providers.keyword_search.base import KeywordSearchProvider
from app.providers.keyword_search.elasticsearch import ElasticsearchKeywordSearchProvider
from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider
from app.providers.llm.base import LLMProvider
from app.providers.rerank.llm import LLMRerankProvider
from app.providers.rerank.noop import NoopRerankProvider
from app.providers.rerank.base import RerankProvider
from app.providers.query.base import KnowledgeBaseQueryContext, QueryProcessResult
from app.providers.query.pipeline import QueryProcessorPipeline
from app.providers.vectorstores.pgvector import PgVectorStore
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.retrieval_log_repository import RetrievalLogRepository
from app.repositories.tenant_repository import TenantRepository
from app.schemas.rag import (
    QueryProcessingMetadata,
    RetrieveData,
    RetrieveMetadata,
    RetrieveRequest,
    RetrieveRerankMetadata,
    RetrievedChunkData,
)
from app.services.hybrid_search_service import HybridSearchService
from app.services.multi_kb_fusion_service import MultiKbFusionService
from app.services.rate_limit_service import get_rate_limit_service
from app.tenant.plan_resolver import PlanResolver
from app.tenant.retrieve_policy import resolve_retrieve_request
from app.utils.id_generator import generate_uuid

logger = get_logger(__name__)


class RagService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.knowledge_base_repository = KnowledgeBaseRepository(db)
        self.chunk_repository = ChunkRepository(db)
        self.retrieval_log_repository = RetrievalLogRepository(db)
        self.embedding_provider = OpenAICompatibleEmbeddingProvider()
        self.vector_store = PgVectorStore(db)
        self.hybrid_search_service = HybridSearchService()
        self.multi_kb_fusion_service = MultiKbFusionService()
        self.query_processor = QueryProcessorPipeline()

    async def retrieve(self, tenant_id: str, request: RetrieveRequest) -> RetrieveData:
        tenant = TenantRepository(self.db).get_by_id(tenant_id)
        if tenant is None:
            raise AppError(
                ErrorCode.NOT_FOUND,
                msg="租户不存在",
                context={"tenant_id": tenant_id},
            )

        plan_context = PlanResolver.resolve_plan(tenant)
        resolved_request, tenant_policy = resolve_retrieve_request(request, plan_context)
        kb_ids = resolved_request.kb_ids or []
        knowledge_bases = self._load_knowledge_bases(tenant_id, kb_ids)

        get_rate_limit_service().check_retrieve(
            tenant_id,
            qps_limit=plan_context.limits.retrieve_qps,
            daily_limit=plan_context.limits.daily_retrieve_limit,
        )

        retrieval_mode = self._get_retrieval_mode(resolved_request)
        top_k = resolved_request.top_k or settings.top_k
        logger.info(
            "BUSINESS_NODE | rag_retrieve_start | tenant_id=%s | kb_ids=%s | user_id=%s | "
            "plan=%s | profile=%s | mode=%s | top_k=%s | retrieval_options=%s | "
            "rerank_options=%s | query_options=%s",
            tenant_id,
            kb_ids,
            resolved_request.user_id,
            tenant_policy.plan,
            tenant_policy.retrieve_profile,
            retrieval_mode,
            top_k,
            resolved_request.retrieval_options.model_dump()
            if resolved_request.retrieval_options
            else None,
            resolved_request.rerank_options.model_dump()
            if resolved_request.rerank_options
            else None,
            resolved_request.query_options.model_dump() if resolved_request.query_options else None,
        )

        log_id = generate_uuid()
        observability = RetrieveObservability(log_id)
        observability.start(
            tenant_id=tenant_id,
            kb_ids=kb_ids,
            user_id=resolved_request.user_id,
            raw_query=resolved_request.query,
            profile=tenant_policy.retrieve_profile,
            plan=tenant_policy.plan,
            mode=retrieval_mode,
            top_k=top_k,
        )

        query_result = await self.query_processor.process(
            resolved_request.query,
            kb=self._build_query_context(knowledge_bases),
            query_options=resolved_request.query_options,
        )
        search_query = query_result.search_query
        query_processing = self._build_query_processing_metadata(query_result)
        observability.record_query_processing(
            query_processing.model_dump() if query_processing else None
        )

        retrieval_started_at = perf_counter()
        per_kb_top_k = self._get_per_kb_top_k(resolved_request, top_k)

        try:
            chunks, retrieval_metadata = await self._retrieve_multi_kb(
                tenant_id=tenant_id,
                request=resolved_request,
                knowledge_bases=knowledge_bases,
                search_query=search_query,
                mode=retrieval_mode,
                top_k=top_k,
                per_kb_top_k=per_kb_top_k,
            )
            empty_reason = self._resolve_empty_reason(tenant_id, kb_ids, chunks)
            if empty_reason:
                retrieval_metadata = {**retrieval_metadata, "empty_reason": empty_reason}
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                ErrorCode.RETRIEVAL_FAILED,
                internal_msg=f"retrieval failed: {exc}",
                context={"tenant_id": tenant_id, "kb_ids": kb_ids},
            ) from exc

        chunks, rerank_metadata = await self._maybe_rerank(
            request=resolved_request,
            chunks=chunks,
            top_k=min(top_k, len(chunks)) if chunks else top_k,
        )

        latency_ms = int((perf_counter() - retrieval_started_at) * 1000)
        observability.record_retrieval(retrieval_metadata, latency_ms=latency_ms)
        observability.record_rerank(rerank_metadata.model_dump())
        observability.finish(chunks, latency_ms=latency_ms)

        primary_kb_id = kb_ids[0]
        self.retrieval_log_repository.create(
            RetrievalLog(
                id=log_id,
                tenant_id=tenant_id,
                kb_id=primary_kb_id,
                kb_ids=kb_ids,
                user_id=resolved_request.user_id,
                query=resolved_request.query,
                retrieved_chunks=chunks,
                top_k=top_k,
                vector_store=retrieval_metadata.get("vector_store", self.vector_store.name),
                latency_ms=latency_ms,
                trace_id=observability.trace_id,
                profile=tenant_policy.retrieve_profile,
                search_query=search_query,
                effective_query=query_result.effective_query,
            )
        )
        self.db.commit()
        get_rate_limit_service().record_retrieve_success(tenant_id)

        logger.info(
            "BUSINESS_NODE | rag_retrieve_success | kb_ids=%s | mode=%s | returned_count=%s | "
            "latency_ms=%s | retrieval=%s | rerank=%s | query_processing=%s | tenant_policy=%s",
            kb_ids,
            retrieval_mode,
            len(chunks),
            latency_ms,
            retrieval_metadata,
            rerank_metadata.model_dump(),
            query_processing.model_dump() if query_processing else None,
            tenant_policy.model_dump(),
        )
        return RetrieveData(
            query=resolved_request.query,
            kb_id=primary_kb_id,
            kb_ids=kb_ids,
            retrieved_chunks=[RetrievedChunkData(**chunk) for chunk in chunks],
            metadata=RetrieveMetadata(
                log_id=log_id,
                trace_id=observability.trace_id,
                top_k=top_k,
                vector_store=self.vector_store.name,
                latency_ms=latency_ms,
                retrieval=retrieval_metadata,
                rerank=rerank_metadata,
                query_processing=query_processing,
                tenant_policy=tenant_policy,
            ),
        )

    def _load_knowledge_bases(self, tenant_id: str, kb_ids: list[str]) -> list[KnowledgeBase]:
        knowledge_bases: list[KnowledgeBase] = []
        for kb_id in kb_ids:
            knowledge_base = self.knowledge_base_repository.get_by_id_and_tenant(kb_id, tenant_id)
            if knowledge_base is None:
                raise AppError(
                    ErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
                    context={
                        "tenant_id": tenant_id,
                        "kb_id": kb_id,
                        "missing_kb_id": kb_id,
                    },
                )
            knowledge_bases.append(knowledge_base)
        return knowledge_bases

    @staticmethod
    def _build_query_context(knowledge_bases: list[KnowledgeBase]) -> KnowledgeBaseQueryContext:
        primary = knowledge_bases[0]
        if len(knowledge_bases) == 1:
            return KnowledgeBaseQueryContext(
                name=primary.name,
                description=primary.description,
                settings=primary.settings or {},
            )

        names = "、".join(kb.name for kb in knowledge_bases)
        descriptions = [kb.description for kb in knowledge_bases if kb.description]
        merged_description = "\n".join(descriptions) if descriptions else f"联合检索知识库：{names}"
        return KnowledgeBaseQueryContext(
            name=names,
            description=merged_description,
            settings=primary.settings or {},
        )

    async def _retrieve_multi_kb(
        self,
        *,
        tenant_id: str,
        request: RetrieveRequest,
        knowledge_bases: list[KnowledgeBase],
        search_query: str,
        mode: str,
        top_k: int,
        per_kb_top_k: int,
    ) -> tuple[list[dict], dict]:
        tasks = [
            self._retrieve_candidates_for_kb(
                tenant_id=tenant_id,
                request=request,
                kb_id=kb.id,
                search_query=search_query,
                mode=mode,
                per_kb_top_k=per_kb_top_k,
            )
            for kb in knowledge_bases
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        chunks_by_kb: list[list[dict]] = []
        per_kb_metadata: list[dict] = []
        failed_kb_ids: list[str] = []

        for kb, result in zip(knowledge_bases, results, strict=True):
            if isinstance(result, BaseException):
                failed_kb_ids.append(kb.id)
                logger.error(
                    "PER_KB_RETRIEVE_FAILED | tenant_id=%s | kb_id=%s | error_type=%s | error=%s",
                    tenant_id,
                    kb.id,
                    type(result).__name__,
                    str(result),
                    exc_info=(type(result), result, result.__traceback__)
                    if isinstance(result, Exception)
                    else None,
                )
                continue

            chunks, metadata = result
            tagged = [
                {
                    **chunk,
                    "kb_id": kb.id,
                    "kb_name": kb.name,
                }
                for chunk in chunks
            ]
            chunks_by_kb.append(tagged)
            per_kb_metadata.append({"kb_id": kb.id, **metadata})

        if not chunks_by_kb:
            if len(results) == 1 and isinstance(results[0], AppError):
                raise results[0]
            first_error = next((item for item in results if isinstance(item, BaseException)), None)
            raise AppError(
                ErrorCode.RETRIEVAL_FAILED,
                internal_msg="all knowledge base retrievals failed",
                context={
                    "tenant_id": tenant_id,
                    "kb_ids": [kb.id for kb in knowledge_bases],
                    "failed_kb_ids": failed_kb_ids,
                },
            ) from (first_error if isinstance(first_error, Exception) else None)

        partial_kb_success = len(failed_kb_ids) > 0
        degraded = any(item.get("degraded") for item in per_kb_metadata) or partial_kb_success
        degraded_reasons = [
            item["degraded_reason"]
            for item in per_kb_metadata
            if item.get("degraded") and item.get("degraded_reason")
        ]
        if partial_kb_success:
            degraded_reasons.append(
                f"partial kb failure: {', '.join(failed_kb_ids)}",
            )

        if len(knowledge_bases) == 1:
            merged_chunks = chunks_by_kb[0][:top_k]
            retrieval_metadata = {
                **per_kb_metadata[0],
                "multi_kb": False,
                "kb_count": 1,
                "kb_ids": [knowledge_bases[0].id],
                "per_kb_top_k": per_kb_top_k,
                "fusion": per_kb_metadata[0].get("fusion"),
                "failed_kb_ids": None,
                "partial_kb_success": False,
                "empty_reason": None,
                "degraded": degraded,
                "degraded_reason": "; ".join(degraded_reasons) if degraded_reasons else None,
            }
            return merged_chunks, retrieval_metadata

        if len(chunks_by_kb) == 1:
            merged_chunks = chunks_by_kb[0][:top_k]
        else:
            merged_chunks = self.multi_kb_fusion_service.fuse_by_rrf(
                chunks_by_kb=chunks_by_kb,
                rrf_k=self._get_rrf_k(request),
                top_n=top_k,
            )
        vector_count = sum(item.get("vector_count", 0) for item in per_kb_metadata)
        bm25_count = sum(item.get("bm25_count", 0) for item in per_kb_metadata)
        rrf_k = self._get_rrf_k(request)
        return merged_chunks, {
            "mode": mode,
            "fusion": "rrf" if len(chunks_by_kb) > 1 else per_kb_metadata[0].get("fusion"),
            "rrf_k": rrf_k,
            "vector_store": self.vector_store.name,
            "keyword_search": settings.keyword_search_provider if mode != "vector" else None,
            "vector_top_k": per_kb_metadata[0].get("vector_top_k"),
            "bm25_top_k": per_kb_metadata[0].get("bm25_top_k"),
            "vector_count": vector_count,
            "bm25_count": bm25_count,
            "fused_count": len(merged_chunks),
            "degraded": degraded,
            "degraded_reason": "; ".join(degraded_reasons) if degraded_reasons else None,
            "multi_kb": True,
            "kb_count": len(knowledge_bases),
            "kb_ids": [kb.id for kb in knowledge_bases],
            "per_kb_top_k": per_kb_top_k,
            "per_kb": per_kb_metadata,
            "failed_kb_ids": failed_kb_ids or None,
            "partial_kb_success": partial_kb_success,
            "empty_reason": None,
        }

    @staticmethod
    def _get_per_kb_top_k(request: RetrieveRequest, top_k: int) -> int:
        if request.retrieval_options and request.retrieval_options.vector_top_k:
            return request.retrieval_options.vector_top_k
        return max(top_k, 10)

    @staticmethod
    def _build_query_processing_metadata(
        query_result: QueryProcessResult,
    ) -> QueryProcessingMetadata | None:
        if not query_result.should_expose_metadata():
            return None

        return QueryProcessingMetadata(
            enabled=query_result.rewrite_attempted,
            strategy=query_result.strategy,
            raw_query=query_result.raw_query,
            effective_query=query_result.effective_query,
            search_query=query_result.search_query,
            latency_ms=query_result.latency_ms,
            synonym_expansions=query_result.synonym_expansions,
            synonym_applied=query_result.synonym_applied,
            degraded=query_result.degraded,
            degraded_reason=query_result.degraded_reason,
        )

    async def _retrieve_candidates_for_kb(
        self,
        *,
        tenant_id: str,
        request: RetrieveRequest,
        kb_id: str,
        search_query: str,
        mode: str,
        per_kb_top_k: int,
    ) -> tuple[list[dict], dict]:
        if mode == "vector":
            vector_chunks = await self._vector_search(
                tenant_id=tenant_id,
                kb_id=kb_id,
                search_query=search_query,
                top_k=per_kb_top_k,
            )
            return self._mark_vector_chunks(vector_chunks), {
                "mode": "vector",
                "fusion": None,
                "rrf_k": None,
                "vector_store": self.vector_store.name,
                "keyword_search": None,
                "vector_top_k": per_kb_top_k,
                "bm25_top_k": None,
                "vector_count": len(vector_chunks),
                "bm25_count": 0,
                "fused_count": len(vector_chunks),
                "degraded": False,
                "degraded_reason": None,
            }

        if mode == "bm25":
            bm25_top_k = self._get_bm25_top_k(request, per_kb_top_k)
            bm25_chunks = await self._bm25_search(
                tenant_id=tenant_id,
                kb_id=kb_id,
                search_query=search_query,
                top_k=bm25_top_k,
            )
            return self._mark_bm25_chunks(bm25_chunks), {
                "mode": "bm25",
                "fusion": None,
                "rrf_k": None,
                "vector_store": self.vector_store.name,
                "keyword_search": settings.keyword_search_provider,
                "vector_top_k": None,
                "bm25_top_k": bm25_top_k,
                "vector_count": 0,
                "bm25_count": len(bm25_chunks),
                "fused_count": len(bm25_chunks),
                "degraded": False,
                "degraded_reason": None,
            }

        if mode != "hybrid":
            raise AppError(
                ErrorCode.PARAM_ERROR,
                internal_msg=f"unsupported retrieval mode: {mode}",
                context={"mode": mode},
            )

        vector_top_k = self._get_vector_top_k(request, per_kb_top_k)
        bm25_top_k = self._get_bm25_top_k(request, per_kb_top_k)
        rrf_k = self._get_rrf_k(request)
        hybrid_top_n = min(settings.hybrid_top_n, max(vector_top_k, bm25_top_k), 50)
        started_at = perf_counter()
        logger.info(
            "HYBRID_SEARCH_START | tenant_id=%s | kb_id=%s | query=%s | "
            "vector_top_k=%s | bm25_top_k=%s | rrf_k=%s",
            tenant_id,
            kb_id,
            search_query,
            vector_top_k,
            bm25_top_k,
            rrf_k,
        )

        vector_chunks: list[dict] = []
        bm25_chunks: list[dict] = []
        vector_failed = False
        bm25_failed = False

        try:
            vector_chunks = await self._vector_search(
                tenant_id=tenant_id,
                kb_id=kb_id,
                search_query=search_query,
                top_k=vector_top_k,
            )
        except Exception as exc:
            vector_failed = True
            logger.error(
                "VECTOR_SEARCH_FAILED | tenant_id=%s | kb_id=%s | query=%s | "
                "vector_top_k=%s | error_type=%s | error=%s",
                tenant_id,
                kb_id,
                search_query,
                vector_top_k,
                type(exc).__name__,
                str(exc),
                exc_info=(type(exc), exc, exc.__traceback__),
            )

        try:
            bm25_chunks = await self._bm25_search(
                tenant_id=tenant_id,
                kb_id=kb_id,
                search_query=search_query,
                top_k=bm25_top_k,
            )
        except Exception as exc:
            bm25_failed = True
            logger.error(
                "BM25_SEARCH_FAILED | tenant_id=%s | kb_id=%s | query=%s | "
                "bm25_top_k=%s | error_type=%s | error=%s",
                tenant_id,
                kb_id,
                search_query,
                bm25_top_k,
                type(exc).__name__,
                str(exc),
                exc_info=(type(exc), exc, exc.__traceback__),
            )

        if vector_failed and bm25_failed:
            raise AppError(
                ErrorCode.RETRIEVAL_FAILED,
                internal_msg="hybrid search failed: vector and bm25 unavailable",
                context={
                    "tenant_id": tenant_id,
                    "kb_id": kb_id,
                    "query": search_query,
                },
            )

        degraded = vector_failed or bm25_failed
        degraded_reason: str | None = None
        if vector_failed and not bm25_failed:
            degraded_reason = "vector search failed"
            chunks = self._mark_bm25_chunks(bm25_chunks)
            logger.warning(
                "HYBRID_SEARCH_DEGRADED | tenant_id=%s | kb_id=%s | query=%s | "
                "reason=%s | vector_count=%s | bm25_count=%s",
                tenant_id,
                kb_id,
                search_query,
                degraded_reason,
                0,
                len(bm25_chunks),
            )
        elif bm25_failed and not vector_failed:
            degraded_reason = "bm25 search failed"
            chunks = self._mark_vector_chunks(vector_chunks)
            logger.warning(
                "HYBRID_SEARCH_DEGRADED | tenant_id=%s | kb_id=%s | query=%s | "
                "reason=%s | vector_count=%s | bm25_count=%s",
                tenant_id,
                kb_id,
                search_query,
                degraded_reason,
                len(vector_chunks),
                0,
            )
        else:
            chunks = self.hybrid_search_service.fuse_by_rrf(
                vector_chunks=vector_chunks,
                bm25_chunks=bm25_chunks,
                rrf_k=rrf_k,
                top_n=hybrid_top_n,
            )

        cost_ms = (perf_counter() - started_at) * 1000
        return chunks, {
            "mode": "hybrid",
            "fusion": settings.hybrid_fusion,
            "rrf_k": rrf_k,
            "vector_store": self.vector_store.name,
            "keyword_search": settings.keyword_search_provider,
            "vector_top_k": vector_top_k,
            "bm25_top_k": bm25_top_k,
            "vector_count": len(vector_chunks),
            "bm25_count": len(bm25_chunks),
            "fused_count": len(chunks),
            "degraded": degraded,
            "degraded_reason": degraded_reason,
            "cost_ms": round(cost_ms, 2),
        }

    def _count_indexed_chunks(self, tenant_id: str, kb_ids: list[str]) -> int:
        return sum(
            self.chunk_repository.count_by_kb_id(tenant_id, kb_id)
            for kb_id in kb_ids
        )

    def _resolve_empty_reason(self, tenant_id: str, kb_ids: list[str], chunks: list[dict]) -> str | None:
        if chunks:
            return None
        if self._count_indexed_chunks(tenant_id, kb_ids) == 0:
            return "no_indexed_chunks"
        return "no_chunks_matched"

    async def _vector_search(
        self,
        *,
        tenant_id: str,
        kb_id: str,
        search_query: str,
        top_k: int,
    ) -> list[dict]:
        query_vector = await self.embedding_provider.embed_query(search_query)
        chunks = await self.vector_store.similarity_search(
            query_vector,
            tenant_id=tenant_id,
            kb_id=kb_id,
            top_k=top_k,
        )
        logger.info(
            "VECTOR_SEARCH_SUCCESS | tenant_id=%s | kb_id=%s | query=%s | top_k=%s | vector_count=%s",
            tenant_id,
            kb_id,
            search_query,
            top_k,
            len(chunks),
        )
        return chunks

    async def _bm25_search(
        self,
        *,
        tenant_id: str,
        kb_id: str,
        search_query: str,
        top_k: int,
    ) -> list[dict]:
        provider = self._build_keyword_search_provider()
        return await provider.keyword_search(
            query=search_query,
            tenant_id=tenant_id,
            kb_id=kb_id,
            top_k=top_k,
        )

    def _mark_vector_chunks(self, chunks: list[dict]) -> list[dict]:
        marked: list[dict] = []
        for rank, chunk in enumerate(chunks, start=1):
            marked.append(
                {
                    **chunk,
                    "vector_score": chunk.get("score"),
                    "bm25_score": None,
                    "vector_rank": rank,
                    "bm25_rank": None,
                    "retrieval_source": "vector",
                }
            )
        return marked

    def _mark_bm25_chunks(self, chunks: list[dict]) -> list[dict]:
        marked: list[dict] = []
        for rank, chunk in enumerate(chunks, start=1):
            marked.append(
                {
                    **chunk,
                    "score": chunk.get("bm25_score", 0.0),
                    "vector_score": None,
                    "vector_rank": None,
                    "bm25_rank": rank,
                    "retrieval_source": "bm25",
                }
            )
        return marked

    async def _maybe_rerank(
        self,
        *,
        request: RetrieveRequest,
        chunks: list[dict],
        top_k: int,
    ) -> tuple[list[dict], RetrieveRerankMetadata]:
        enabled = (
            request.rerank_options.enabled
            if request.rerank_options and request.rerank_options.enabled is not None
            else settings.rerank_enabled
        )
        top_n = (
            request.rerank_options.top_n
            if request.rerank_options and request.rerank_options.top_n is not None
            else settings.rerank_top_n
        )
        top_n = min(top_n, top_k, len(chunks)) if chunks else top_n

        if not enabled or settings.rerank_provider == "noop":
            reranked = await NoopRerankProvider().rerank(
                query=request.query,
                chunks=chunks,
                top_n=min(top_k, len(chunks)),
            )
            return reranked, RetrieveRerankMetadata(
                enabled=False,
                provider="noop",
                top_n=None,
                candidate_count=len(chunks),
            )

        candidate_count = min(len(chunks), settings.rerank_max_candidates)
        try:
            rerank_provider = self._build_rerank_provider()
            reranked = await rerank_provider.rerank(
                query=request.query,
                chunks=chunks,
                top_n=top_n,
            )
            return reranked, RetrieveRerankMetadata(
                enabled=True,
                provider=rerank_provider.name,
                llm_provider=settings.llm_provider,
                model=settings.llm_model,
                top_n=top_n,
                candidate_count=candidate_count,
            )
        except Exception as exc:
            logger.warning(
                "BUSINESS_NODE | rerank_degraded | kb_ids=%s | candidate_count=%s | error_type=%s | error=%s",
                request.kb_ids,
                candidate_count,
                type(exc).__name__,
                str(exc),
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            fallback_top_n = min(top_n, len(chunks))
            fallback_chunks = [
                {**chunk, "rerank_score": None}
                for chunk in chunks[:fallback_top_n]
            ]
            return fallback_chunks, RetrieveRerankMetadata(
                enabled=True,
                provider="llm",
                llm_provider=settings.llm_provider,
                model=settings.llm_model,
                top_n=top_n,
                candidate_count=candidate_count,
                degraded=True,
                error=str(exc),
            )

    def _build_llm_provider(self) -> LLMProvider:
        if settings.llm_provider == "openai_compatible":
            return OpenAICompatibleLLMProvider()
        raise ValueError(f"unsupported llm provider: {settings.llm_provider}")

    def _build_rerank_provider(self) -> RerankProvider:
        if settings.rerank_provider == "llm":
            return LLMRerankProvider(llm_provider=self._build_llm_provider())
        if settings.rerank_provider == "noop":
            return NoopRerankProvider()
        raise ValueError(f"unsupported rerank provider: {settings.rerank_provider}")

    def _build_keyword_search_provider(self) -> KeywordSearchProvider:
        if settings.keyword_search_provider == "elasticsearch":
            return ElasticsearchKeywordSearchProvider()
        raise ValueError(f"unsupported keyword search provider: {settings.keyword_search_provider}")

    def _get_retrieval_mode(self, request: RetrieveRequest) -> str:
        if request.retrieval_options and request.retrieval_options.mode:
            return request.retrieval_options.mode
        return settings.retrieval_mode

    def _get_vector_top_k(self, request: RetrieveRequest, fallback: int) -> int:
        if request.retrieval_options and request.retrieval_options.vector_top_k:
            return request.retrieval_options.vector_top_k
        return settings.hybrid_vector_top_k or fallback

    def _get_bm25_top_k(self, request: RetrieveRequest, fallback: int) -> int:
        if request.retrieval_options and request.retrieval_options.bm25_top_k:
            return request.retrieval_options.bm25_top_k
        if self._get_retrieval_mode(request) == "bm25":
            return fallback
        return settings.hybrid_bm25_top_k or fallback

    def _get_rrf_k(self, request: RetrieveRequest) -> int:
        if request.retrieval_options and request.retrieval_options.rrf_k:
            return request.retrieval_options.rrf_k
        return settings.hybrid_rrf_k
