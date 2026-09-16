from time import perf_counter

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.llm.base import LLMProvider, LLMProviderError
from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider
from app.providers.query.base import KnowledgeBaseQueryContext, QueryProcessResult

logger = get_logger(__name__)

REWRITE_SYSTEM_PROMPT = """你是检索 query 改写器，不是问答助手。
任务：把用户的口语提问改写成一条更适合在知识库中检索的短句。
要求：
1. 只输出 JSON，格式为 {"rewritten_query": "..."}。
2. rewritten_query 必须是一条中文短句，更贴近文档常用表述。
3. 保留用户原意，不编造事实，不扩展用户没问的内容。
4. 禁止回答问题（例如不能输出「3 个工作日」这类答案句）。"""


class LLMRewriteQueryProcessor:
    name = "rewrite"

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or OpenAICompatibleLLMProvider()

    async def process(
        self,
        raw_query: str,
        *,
        kb: KnowledgeBaseQueryContext,
    ) -> QueryProcessResult:
        started_at = perf_counter()
        timeout_seconds = max(settings.query_rewrite_timeout_ms / 1000, 0.1)

        user_payload = {
            "knowledge_base_name": kb.name,
            "knowledge_base_description": kb.domain_description(),
            "raw_query": raw_query,
        }

        try:
            response = await self.llm_provider.chat_json(
                system_prompt=REWRITE_SYSTEM_PROMPT,
                user_payload=user_payload,
                temperature=0.2,
                timeout_seconds=timeout_seconds,
            )
            rewritten = self._extract_rewritten_query(response)
            if not rewritten:
                raise LLMProviderError("rewritten_query is empty")

            latency_ms = int((perf_counter() - started_at) * 1000)
            logger.info(
                "QUERY_REWRITE_SUCCESS | raw_query=%s | effective_query=%s | latency_ms=%s",
                raw_query,
                rewritten,
                latency_ms,
            )
            return QueryProcessResult(
                raw_query=raw_query,
                effective_query=rewritten,
                search_query=rewritten,
                strategy="rewrite",
                latency_ms=latency_ms,
                degraded=False,
                degraded_reason=None,
                rewrite_attempted=True,
            )
        except Exception as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            logger.warning(
                "QUERY_REWRITE_DEGRADED | raw_query=%s | error_type=%s | error=%s | latency_ms=%s",
                raw_query,
                type(exc).__name__,
                str(exc),
                latency_ms,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return QueryProcessResult(
                raw_query=raw_query,
                effective_query=raw_query,
                search_query=raw_query,
                strategy="rewrite",
                latency_ms=latency_ms,
                degraded=True,
                degraded_reason=str(exc),
                rewrite_attempted=True,
            )

    @staticmethod
    def _extract_rewritten_query(response: dict) -> str:
        rewritten = response.get("rewritten_query")
        if not isinstance(rewritten, str):
            return ""
        return rewritten.strip()
