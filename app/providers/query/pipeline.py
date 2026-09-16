from app.core.config import settings
from app.providers.query.base import KnowledgeBaseQueryContext, QueryProcessResult
from app.providers.query.llm_rewrite import LLMRewriteQueryProcessor
from app.providers.query.noop import NoopQueryProcessor
from app.providers.query.synonym_expander import expand_synonyms
from app.schemas.rag import QueryOptions


class QueryProcessorPipeline:
    def __init__(self) -> None:
        self.noop_processor = NoopQueryProcessor()
        self.rewrite_processor = LLMRewriteQueryProcessor()

    async def process(
        self,
        raw_query: str,
        *,
        kb: KnowledgeBaseQueryContext,
        query_options: QueryOptions | None,
    ) -> QueryProcessResult:
        if self._should_rewrite(query_options):
            base_result = await self.rewrite_processor.process(raw_query, kb=kb)
        else:
            base_result = await self.noop_processor.process(raw_query)

        expand_result = expand_synonyms(base_result.effective_query, kb.settings)
        return QueryProcessResult(
            raw_query=base_result.raw_query,
            effective_query=base_result.effective_query,
            search_query=expand_result.search_query,
            strategy=base_result.strategy,
            latency_ms=base_result.latency_ms,
            synonym_expansions=expand_result.synonym_expansions,
            synonym_applied=expand_result.synonym_applied,
            degraded=base_result.degraded,
            degraded_reason=base_result.degraded_reason,
            rewrite_attempted=base_result.rewrite_attempted,
        )

    @staticmethod
    def _should_rewrite(query_options: QueryOptions | None) -> bool:
        if query_options is not None and query_options.enabled is not None:
            enabled = query_options.enabled
        else:
            enabled = settings.query_rewrite_enabled

        if not enabled:
            return False

        if query_options is not None and query_options.strategy == "noop":
            return False

        return True
