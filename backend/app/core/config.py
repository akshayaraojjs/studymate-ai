"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_env: str = "development"
    app_name: str = "StudyMate AI"
    secret_key: str = "dev-insecure-secret-change-me"
    access_token_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173"

    # Database. Empty -> local SQLite file under backend/data.
    database_url: str = ""

    # LLM (Groq)
    llm_provider: str = "groq"
    groq_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1200
    # gpt-oss models support low/medium/high reasoning; low keeps time-to-first-token sane.
    llm_reasoning_effort: str = "low"

    # Embeddings
    embedding_provider: str = "auto"  # auto | fastembed | hash
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Web search
    web_search_provider: str = "duckduckgo"  # duckduckgo | tavily
    web_search_api_key: str = ""
    web_search_timeout_seconds: float = 8.0

    # RAG / ingestion
    max_upload_size_mb: int = 15
    retrieval_top_k: int = 5
    retrieval_min_similarity: float = 0.25
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 100
    max_tool_calls: int = 4
    max_upload_pages: int = 400

    # Paths
    data_dir: Path = BACKEND_DIR / "data"
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        return f"sqlite:///{(self.data_dir / 'studymate.db').as_posix()}"

    @property
    def is_postgres(self) -> bool:
        return self.resolved_database_url.startswith("postgresql")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
