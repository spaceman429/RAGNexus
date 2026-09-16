import json
import time

import httpx

from app.core.config import settings
from app.core.logging import log_llm_error, log_llm_request, log_llm_response
from app.providers.llm.base import LLMProvider, LLMProviderError


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        base_url: str = settings.llm_base_url,
        api_key: str = settings.llm_api_key,
        model: str = settings.llm_model,
        timeout_seconds: int = settings.llm_timeout_seconds,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def chat_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict,
        temperature: float = 0.0,
        timeout_seconds: int | None = None,
    ) -> dict:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        started_at = time.perf_counter()
        log_llm_request(
            model=self.model,
            prompt={"system_prompt": system_prompt, "user_payload": user_payload},
            extra={"provider": "openai_compatible", "base_url": self.base_url},
        )

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds or self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            cost_ms = (time.perf_counter() - started_at) * 1000
            log_llm_error(
                model=self.model,
                error=exc,
                cost_ms=cost_ms,
                prompt={"system_prompt": system_prompt, "user_payload": user_payload},
                extra={"provider": "openai_compatible", "base_url": self.base_url},
            )
            raise LLMProviderError(f"llm request failed: {exc}") from exc

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = self._parse_json_content(content)
            cost_ms = (time.perf_counter() - started_at) * 1000
            log_llm_response(
                model=self.model,
                response=parsed,
                cost_ms=cost_ms,
                extra={"provider": "openai_compatible"},
            )
            return parsed
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            cost_ms = (time.perf_counter() - started_at) * 1000
            log_llm_error(
                model=self.model,
                error=exc,
                cost_ms=cost_ms,
                prompt={"system_prompt": system_prompt, "user_payload": user_payload},
                extra={"provider": "openai_compatible"},
            )
            raise LLMProviderError(f"llm response json parse failed: {exc}") from exc

    @staticmethod
    def _parse_json_content(content: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("top-level JSON is not an object", cleaned, 0)
        return parsed
