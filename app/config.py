"""Configuration helpers."""

from dataclasses import dataclass
import os
from pathlib import Path

from agno.models.deepseek import DeepSeek
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    exa_api_key: str | None = None
    openai_worker_model: str = "gpt-4.1-mini"
    openai_reasoning_model: str = "gpt-4.1"
    deepseek_worker_model: str = "deepseek-chat"
    deepseek_reasoning_model: str = "deepseek-reasoner"
    agno_debug: bool = False
    agno_debug_level: int = 1


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_debug_level() -> int:
    value = os.getenv("AGNO_DEBUG_LEVEL", "1")
    try:
        level = int(value)
    except ValueError:
        return 1
    return 2 if level >= 2 else 1


def get_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "openai").lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        exa_api_key=os.getenv("EXA_API_KEY"),
        openai_worker_model=os.getenv("OPENAI_WORKER_MODEL", "gpt-4.1-mini"),
        openai_reasoning_model=os.getenv("OPENAI_REASONING_MODEL", "gpt-4.1"),
        deepseek_worker_model=os.getenv("DEEPSEEK_WORKER_MODEL", "deepseek-chat"),
        deepseek_reasoning_model=os.getenv("DEEPSEEK_REASONING_MODEL", "deepseek-reasoner"),
        agno_debug=_env_bool("AGNO_DEBUG"),
        agno_debug_level=_env_debug_level(),
    )


def get_agent_debug_config() -> dict[str, object]:
    settings = get_settings()
    return {
        "debug_mode": settings.agno_debug,
        "debug_level": settings.agno_debug_level,
    }


def get_worker_model(max_tokens: int | None = None):
    settings = get_settings()
    if settings.llm_provider == "openai":
        return OpenAIChat(
            id=settings.openai_worker_model,
            api_key=settings.openai_api_key,
            max_tokens=max_tokens,
            temperature=0,
        )
    if settings.llm_provider == "deepseek":
        return DeepSeek(
            id=settings.deepseek_worker_model,
            api_key=settings.deepseek_api_key,
            max_tokens=max_tokens,
            temperature=0,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def get_reasoning_model(max_tokens: int | None = None):
    settings = get_settings()
    if settings.llm_provider == "openai":
        return OpenAIChat(
            id=settings.openai_reasoning_model,
            api_key=settings.openai_api_key,
            max_tokens=max_tokens,
            temperature=0,
        )
    if settings.llm_provider == "deepseek":
        return DeepSeek(
            id=settings.deepseek_reasoning_model,
            api_key=settings.deepseek_api_key,
            max_tokens=max_tokens,
            temperature=0,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
