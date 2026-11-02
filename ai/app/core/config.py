from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://quarry:quarry@localhost:5432/quarry"
    internal_token: SecretStr = SecretStr("")
    uploads_dir: Path = Path("/data/uploads")

    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://localhost:11434"

    llm_provider: Literal["openrouter", "ollama"] = "openrouter"
    llm_model: str = "z-ai/glm-5.3-flash"
    llm_reasoning_effort: Literal["none", "minimal", "low", "medium", "high"] = "minimal"
    llm_timeout_seconds: float = 120.0

    embedding_model: str = "baai/bge-m3"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 32

    chunk_max_chars: int = 1200
    chunk_overlap_chars: int = 200
    retrieval_top_k: int = 6
