from app.core.config import settings
from app.providers.llm.base import LLMProvider
from app.providers.rerank.base import RerankProvider


RERANK_SYSTEM_PROMPT = """你是 RAG 检索重排器。你的任务是根据用户问题，对候选知识片段进行相关性打分和排序。

要求：
1. 只判断候选片段是否有助于回答用户问题。
2. 不要回答用户问题。
3. 不要编造候选片段中不存在的信息。
4. 每个候选片段给出 0 到 1 之间的 rerank_score。
5. 分数越高表示越相关、越适合作为 RAG 上下文。
6. 只返回 JSON，不要返回 Markdown，不要返回解释性文字。
7. JSON 格式必须是 {"rankings":[{"chunk_id":"...","rerank_score":0.0,"reason":"..."}]}。
"""


class LLMRerankProvider(RerankProvider):
    name = "llm"

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        max_candidates: int = settings.rerank_max_candidates,
        chunk_max_chars: int = settings.rerank_chunk_max_chars,
        temperature: float = settings.rerank_temperature,
        timeout_seconds: int = settings.llm_timeout_seconds,
    ) -> None:
        self.llm_provider = llm_provider
        self.max_candidates = max_candidates
        self.chunk_max_chars = chunk_max_chars
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    async def rerank(
        self,
        *,
        query: str,
        chunks: list[dict],
        top_n: int,
    ) -> list[dict]:
        candidates = chunks[: self.max_candidates]
        payload = {
            "query": query,
            "candidates": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "title": chunk["title"],
                    "content": chunk["content"][: self.chunk_max_chars],
                    "vector_score": chunk["score"],
                }
                for chunk in candidates
            ],
            "top_n": top_n,
        }

        response = await self.llm_provider.chat_json(
            system_prompt=RERANK_SYSTEM_PROMPT,
            user_payload=payload,
            temperature=self.temperature,
            timeout_seconds=self.timeout_seconds,
        )

        score_map = self._build_score_map(response)
        reranked_chunks = [
            {
                **chunk,
                "rerank_score": score_map.get(chunk["chunk_id"], 0.0),
            }
            for chunk in candidates
        ]
        reranked_chunks.sort(
            key=lambda chunk: (chunk["rerank_score"], chunk["score"]),
            reverse=True,
        )
        return reranked_chunks[:top_n]

    @staticmethod
    def _build_score_map(response: dict) -> dict[str, float]:
        rankings = response.get("rankings")
        if not isinstance(rankings, list):
            raise ValueError("rerank response missing rankings")

        score_map: dict[str, float] = {}
        for item in rankings:
            if not isinstance(item, dict):
                continue
            chunk_id = item.get("chunk_id")
            if not isinstance(chunk_id, str):
                continue
            raw_score = item.get("rerank_score", 0)
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = 0.0
            score_map[chunk_id] = min(max(score, 0.0), 1.0)
        return score_map

