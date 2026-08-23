from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    app_name: str = "SentinelPay Risk Engine"
    api_key: str = Field(
        "change-me-demo-key",
        validation_alias=AliasChoices("SENTINELPAY_API_KEY", "API_KEY"),
    )
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'sentipay.db'}"
    artifacts_dir: Path = BASE_DIR / "artifacts"
    data_dir: Path = BASE_DIR / "data"

    t_review: float = 0.45
    t_block: float = 0.85
    hard_gate_amount: float = 40000.0
    fp_friction_cost_inr: float = 150.0
    target_recall_floor: float = 0.80

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-08-01-preview"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    llm_timeout_seconds: float = 8.0
    llm_max_consecutive_failures: int = 3
    llm_cooldown_seconds: float = 60.0

    webhook_url: str | None = None

    rate_limit_per_minute: int = 240

    simulator_interval_seconds: float = 1.5
    simulator_attack_every: int = 25

    @property
    def has_azure_openai(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
