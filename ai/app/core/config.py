from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://quarry:quarry@localhost:5432/quarry"
    llm_provider: Literal["openrouter", "ollama"] = "openrouter"
    llm_model: str = ""
    openrouter_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "http://localhost:11434"
