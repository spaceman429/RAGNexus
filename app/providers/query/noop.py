from app.providers.query.base import QueryProcessResult


class NoopQueryProcessor:
    name = "noop"

    async def process(self, raw_query: str) -> QueryProcessResult:
        return QueryProcessResult(
            raw_query=raw_query,
            effective_query=raw_query,
            search_query=raw_query,
            strategy="noop",
            latency_ms=0,
            degraded=False,
            degraded_reason=None,
            rewrite_attempted=False,
        )
