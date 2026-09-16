from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rag_center"

    model_base_url: str = "https://api.openai.com/v1"
    model_api_key: str = "your-api-key"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = Field(default=10, ge=1, le=100)

    llm_provider: str = "openai_compatible"
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = "your-deepseek-api-key"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = Field(default=60, ge=1)

    vector_store: str = "pgvector"
    keyword_search_provider: str = "elasticsearch"
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "rag_chunks"
    elasticsearch_timeout_seconds: int = Field(default=30, ge=1)

    retrieval_mode: str = "vector"
    hybrid_fusion: str = "rrf"
    hybrid_rrf_k: int = Field(default=60, ge=1)
    hybrid_vector_top_k: int = Field(default=20, ge=1, le=50)
    hybrid_bm25_top_k: int = Field(default=20, ge=1, le=50)
    hybrid_top_n: int = Field(default=20, ge=1, le=50)

    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    table_max_rows_per_chunk: int = Field(default=10, ge=1, le=100)
    top_k: int = Field(default=5, ge=1, le=50)
    multi_kb_max: int = Field(default=5, ge=1, le=10)
    query_max_length: int = Field(default=2000, ge=1, le=10000)

    rerank_enabled: bool = False
    rerank_provider: str = "llm"
    rerank_top_n: int = Field(default=5, ge=1, le=50)
    rerank_max_candidates: int = Field(default=20, ge=1, le=50)
    rerank_chunk_max_chars: int = Field(default=1024, ge=100)
    rerank_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    log_level: str = "INFO"
    log_dir: str = "logs"
    log_max_bytes: int = 20 * 1024 * 1024
    log_backup_count: int = 5
    log_error_max_bytes: int = 20 * 1024 * 1024
    log_error_backup_count: int = 10
    log_daily_backup_count: int = 14
    log_body_max_chars: int = 4000
    log_llm_max_chars: int = 8000
    log_request_body: bool = True
    log_response_body: bool = True

    auth_enabled: bool = True

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    query_rewrite_enabled: bool = False
    query_rewrite_timeout_ms: int = Field(default=2000, ge=100)

    langfuse_enabled: bool = False
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    document_storage_path: str = "data/uploads"
    document_max_size_mb: int = Field(default=20, ge=1, le=200)

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
