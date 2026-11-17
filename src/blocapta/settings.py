"""Configuration globale, lue depuis les variables d'environnement (préfixe BLOCAPTA_)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLOCAPTA_", env_file=".env", extra="ignore", protected_namespaces=()
    )

    ollama_url: str = "http://localhost:11434"
    model_extraction: str = "qwen3:8b"
    model_report: str = "qwen3:8b"
    model_configurator: str = "qwen3:8b"
    ollama_think: bool = False
    ollama_timeout: float = 300.0
    llm_enabled: bool = True

    archetypes_dir: Path = DATA_DIR / "archetypes"
    criteria_file: Path = DATA_DIR / "criteria.yaml"
    questionnaire_file: Path = DATA_DIR / "questionnaire_dsi.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
