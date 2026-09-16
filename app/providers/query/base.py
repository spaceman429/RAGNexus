from dataclasses import dataclass, field


@dataclass(slots=True)
class KnowledgeBaseQueryContext:
    name: str
    description: str | None
    settings: dict = field(default_factory=dict)

    def domain_description(self) -> str:
        """description + rewrite_hint（有 hint 时拼接，供 01 LLM 改写 Prompt 使用）。"""
        parts: list[str] = []
        if self.description:
            parts.append(self.description)
        rewrite_hint = self.settings.get("rewrite_hint")
        if isinstance(rewrite_hint, str) and rewrite_hint.strip():
            parts.append(rewrite_hint.strip())
        return "\n".join(parts)


@dataclass(slots=True)
class QueryProcessResult:
    raw_query: str
    effective_query: str
    search_query: str
    strategy: str
    latency_ms: int
    synonym_expansions: list[str] = field(default_factory=list)
    synonym_applied: bool = False
    degraded: bool = False
    degraded_reason: str | None = None
    rewrite_attempted: bool = False

    def should_expose_metadata(self) -> bool:
        return (
            self.rewrite_attempted
            or self.synonym_applied
            or self.search_query != self.raw_query
        )
