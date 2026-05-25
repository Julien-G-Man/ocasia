"""Central FastAPI configuration loaded from environment variables."""

from __future__ import annotations

import os
from typing import List, Set

try:
    from pydantic import AliasChoices, Field
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _PYDANTIC_SETTINGS = True
except ImportError:  # pragma: no cover
    from pydantic import BaseModel as BaseSettings, Field  # type: ignore[assignment]

    SettingsConfigDict = None  # type: ignore[assignment]
    AliasChoices = None  # type: ignore[assignment]
    _PYDANTIC_SETTINGS = False


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ[key])
    except (KeyError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ[key])
    except (KeyError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_first(keys: List[str], default: str = "") -> str:
    for key in keys:
        if key in os.environ and os.environ[key] != "":
            return os.environ[key]
    return default


def _env_float_first(keys: List[str], default: float) -> float:
    for key in keys:
        value = os.environ.get(key, "")
        if value == "":
            continue
        try:
            return float(value)
        except ValueError:
            continue
    return default


DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173,http://localhost:3000,http://localhost:8000"
DEFAULT_PROVIDER_ORDER = "nvidia_openai,nvidia_deepseek,claude,azure,deepseek,gemini,huggingface"
DEFAULT_NVIDIA_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_HF_URL_TEMPLATE = "https://api-inference.huggingface.co/models/{model}"


class _CommonSettings:
    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.FASTAPI_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_origins_set(self) -> Set[str]:
        return set(self.allowed_origins_list)

    @property
    def provider_list(self) -> List[str]:
        return [p.strip() for p in self.AI_PROVIDER_ORDER.split(",") if p.strip()]

    @property
    def AI_PROVIDER_PRIORITY(self) -> str:
        return self.AI_PROVIDER_ORDER

    @property
    def HTTP_CONNECT_TIMEOUT(self) -> float:
        return self.FASTAPI_OUTBOUND_CONNECT_TIMEOUT

    @property
    def HTTP_READ_TIMEOUT(self) -> float:
        return self.FASTAPI_OUTBOUND_READ_TIMEOUT

    @property
    def HTTP_WRITE_TIMEOUT(self) -> float:
        return self.FASTAPI_OUTBOUND_WRITE_TIMEOUT

    @property
    def HTTP_POOL_TIMEOUT(self) -> float:
        return self.FASTAPI_OUTBOUND_POOL_TIMEOUT

    @property
    def HTTP_MAX_KEEPALIVE(self) -> int:
        return self.FASTAPI_OUTBOUND_MAX_KEEPALIVE

    @property
    def HTTP_MAX_CONNECTIONS(self) -> int:
        return self.FASTAPI_OUTBOUND_MAX_CONNECTIONS


if _PYDANTIC_SETTINGS:

    class Settings(_CommonSettings, BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=True,
            extra="ignore",
        )

        # Server
        FASTAPI_HOST: str = Field("0.0.0.0")
        FASTAPI_PORT: int = Field(8001)
        FASTAPI_BASE_URL: str = Field(DEFAULT_BASE_URL)
        FASTAPI_WORKERS: int = Field(4)
        FASTAPI_RELOAD: bool = Field(False)
        FASTAPI_SECRET: str = Field("")

        # CORS
        FASTAPI_ALLOWED_ORIGINS: str = Field(DEFAULT_ALLOWED_ORIGINS)

        # AI providers
        OPENAI_API_KEY: str = Field("")
        ANTHROPIC_API_KEY: str = Field("")
        CLAUDE_API_KEY: str = Field("")
        CLAUDE_MODEL: str = Field("claude-sonnet-4-20250514")
        CLAUDE_URL: str = Field("https://api.anthropic.com/v1/messages")
        CLAUDE_API_VERSION: str = Field("2023-06-01")

        NVIDIA_OPENAI_API_KEY: str = Field("")
        NVIDIA_OPENAI_API_URL: str = Field(DEFAULT_NVIDIA_CHAT_URL)
        NVIDIA_OPENAI_MODEL: str = Field("openai/gpt-oss-20b")

        NVIDIA_DEEPSEEK_API_KEY: str = Field("")
        NVIDIA_DEEPSEEK_API_URL: str = Field(DEFAULT_NVIDIA_CHAT_URL)
        NVIDIA_DEEPSEEK_MODEL: str = Field("deepseek-ai/deepseek-v3.2")
        NVIDIA_DEEPSEEK_THINKING: bool = Field(True)

        DEEPSEEK_API_KEY: str = Field("")
        DEEPSEEK_API_URL: str = Field(DEFAULT_DEEPSEEK_URL)

        GEMINI_API_KEY: str = Field("")
        GEMINI_API_URL: str = Field(DEFAULT_GEMINI_URL)

        HUGGING_FACE_API_KEY: str = Field("")
        HUGGING_FACE_API_TOKEN: str = Field(
            "",
            validation_alias=AliasChoices("HUGGING_FACE_API_TOKEN", "HUGGING_FACE_API_KEY"),
        )
        HUGGING_FACE_API_URL_TEMPLATE: str = Field(DEFAULT_HF_URL_TEMPLATE)
        HUGGING_FACE_MODEL: str = Field("mistralai/Mixtral-8x7B-Instruct-v0.1")

        AZURE_OPENAI_API_KEY: str = Field("")
        AZURE_OPENAI_ENDPOINT: str = Field("")
        AZURE_OPENAI_DEPLOYMENT: str = Field("gpt-4o-mini-deployment")
        AZURE_OPENAI_API_VERSION: str = Field("2025-01-01-preview")

        # Search
        SEARCH_API_KEY: str = Field("")
        SEARCH_ENGINE_ID: str = Field("")
        SEARCH_TIMEOUT_SECONDS: int = Field(5)
        SERPAPI_API_KEY: str = Field("")

        # Routing
        AI_PROVIDER_ORDER: str = Field(
            DEFAULT_PROVIDER_ORDER,
            validation_alias=AliasChoices("AI_PROVIDER_ORDER", "AI_PROVIDER_PRIORITY"),
        )

        # Outbound HTTP client
        FASTAPI_OUTBOUND_MAX_CONNECTIONS: int = Field(100)
        FASTAPI_OUTBOUND_MAX_KEEPALIVE: int = Field(20)
        FASTAPI_OUTBOUND_CONNECT_TIMEOUT: float = Field(
            10.0,
            validation_alias=AliasChoices(
                "FASTAPI_OUTBOUND_CONNECT_TIMEOUT",
                "FASTAPI_OUTBOUND_TIMEOUT_CONNECT",
            ),
        )
        FASTAPI_OUTBOUND_READ_TIMEOUT: float = Field(
            90.0,
            validation_alias=AliasChoices(
                "FASTAPI_OUTBOUND_READ_TIMEOUT",
                "FASTAPI_OUTBOUND_TIMEOUT_READ",
            ),
        )
        FASTAPI_OUTBOUND_WRITE_TIMEOUT: float = Field(
            30.0,
            validation_alias=AliasChoices(
                "FASTAPI_OUTBOUND_WRITE_TIMEOUT",
                "FASTAPI_OUTBOUND_TIMEOUT_WRITE",
            ),
        )
        FASTAPI_OUTBOUND_POOL_TIMEOUT: float = Field(
            10.0,
            validation_alias=AliasChoices(
                "FASTAPI_OUTBOUND_POOL_TIMEOUT",
                "FASTAPI_OUTBOUND_TIMEOUT_POOL",
            ),
        )

        # Knowledge base
        KB_SEARCH_PROVIDER: str = Field("tfidf")  # "tfidf" | "openai"
        KB_FILE_PATH: str = Field("")              # explicit override; loader auto-resolves if empty

        # Flashcards
        FLASHCARDS_AI_MAX_CONCURRENT: int = Field(20)
        FLASHCARDS_AI_SEMAPHORE_WAIT_SECONDS: float = Field(10.0)

else:  # pragma: no cover

    class Settings(_CommonSettings, BaseSettings):  # type: ignore[no-redef]
        FASTAPI_HOST: str = _env("FASTAPI_HOST", "0.0.0.0")
        FASTAPI_PORT: int = _env_int("FASTAPI_PORT", 8001)
        FASTAPI_BASE_URL: str = _env("FASTAPI_BASE_URL", DEFAULT_BASE_URL)
        FASTAPI_WORKERS: int = _env_int("FASTAPI_WORKERS", 4)
        FASTAPI_RELOAD: bool = _env_bool("FASTAPI_RELOAD", False)
        FASTAPI_SECRET: str = _env("FASTAPI_SECRET", "")

        FASTAPI_ALLOWED_ORIGINS: str = _env(
            "FASTAPI_ALLOWED_ORIGINS",
            DEFAULT_ALLOWED_ORIGINS,
        )

        OPENAI_API_KEY: str = _env("OPENAI_API_KEY", "")
        ANTHROPIC_API_KEY: str = _env("ANTHROPIC_API_KEY", "")
        CLAUDE_API_KEY: str = _env("CLAUDE_API_KEY", "")
        CLAUDE_MODEL: str = _env("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        CLAUDE_URL: str = _env("CLAUDE_URL", "https://api.anthropic.com/v1/messages")
        CLAUDE_API_VERSION: str = _env("CLAUDE_API_VERSION", "2023-06-01")

        NVIDIA_OPENAI_API_KEY: str = _env("NVIDIA_OPENAI_API_KEY", "")
        NVIDIA_OPENAI_API_URL: str = _env(
            "NVIDIA_OPENAI_API_URL",
            DEFAULT_NVIDIA_CHAT_URL,
        )
        NVIDIA_OPENAI_MODEL: str = _env("NVIDIA_OPENAI_MODEL", "openai/gpt-oss-20b")

        NVIDIA_DEEPSEEK_API_KEY: str = _env("NVIDIA_DEEPSEEK_API_KEY", "")
        NVIDIA_DEEPSEEK_API_URL: str = _env(
            "NVIDIA_DEEPSEEK_API_URL",
            DEFAULT_NVIDIA_CHAT_URL,
        )
        NVIDIA_DEEPSEEK_MODEL: str = _env("NVIDIA_DEEPSEEK_MODEL", "deepseek-ai/deepseek-v3.2")
        NVIDIA_DEEPSEEK_THINKING: bool = _env_bool("NVIDIA_DEEPSEEK_THINKING", True)

        DEEPSEEK_API_KEY: str = _env("DEEPSEEK_API_KEY", "")
        DEEPSEEK_API_URL: str = _env(
            "DEEPSEEK_API_URL",
            DEFAULT_DEEPSEEK_URL,
        )

        GEMINI_API_KEY: str = _env("GEMINI_API_KEY", "")
        GEMINI_API_URL: str = _env(
            "GEMINI_API_URL",
            DEFAULT_GEMINI_URL,
        )

        HUGGING_FACE_API_KEY: str = _env("HUGGING_FACE_API_KEY", "")
        HUGGING_FACE_API_TOKEN: str = _env_first(["HUGGING_FACE_API_TOKEN", "HUGGING_FACE_API_KEY"], "")
        HUGGING_FACE_API_URL_TEMPLATE: str = _env(
            "HUGGING_FACE_API_URL_TEMPLATE",
            DEFAULT_HF_URL_TEMPLATE,
        )
        HUGGING_FACE_MODEL: str = _env(
            "HUGGING_FACE_MODEL",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
        )

        AZURE_OPENAI_API_KEY: str = _env("AZURE_OPENAI_API_KEY", "")
        AZURE_OPENAI_ENDPOINT: str = _env("AZURE_OPENAI_ENDPOINT", "")
        AZURE_OPENAI_DEPLOYMENT: str = _env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini-deployment")
        AZURE_OPENAI_API_VERSION: str = _env("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

        SEARCH_API_KEY: str = _env("SEARCH_API_KEY", "")
        SEARCH_ENGINE_ID: str = _env("SEARCH_ENGINE_ID", "")
        SEARCH_TIMEOUT_SECONDS: int = _env_int("SEARCH_TIMEOUT_SECONDS", 5)
        SERPAPI_API_KEY: str = _env("SERPAPI_API_KEY", "")

        AI_PROVIDER_ORDER: str = _env_first(
            ["AI_PROVIDER_ORDER", "AI_PROVIDER_PRIORITY"],
            DEFAULT_PROVIDER_ORDER,
        )

        FASTAPI_OUTBOUND_MAX_CONNECTIONS: int = _env_int("FASTAPI_OUTBOUND_MAX_CONNECTIONS", 100)
        FASTAPI_OUTBOUND_MAX_KEEPALIVE: int = _env_int("FASTAPI_OUTBOUND_MAX_KEEPALIVE", 20)
        FASTAPI_OUTBOUND_CONNECT_TIMEOUT: float = _env_float_first(
            ["FASTAPI_OUTBOUND_CONNECT_TIMEOUT", "FASTAPI_OUTBOUND_TIMEOUT_CONNECT"],
            10.0,
        )
        FASTAPI_OUTBOUND_READ_TIMEOUT: float = _env_float_first(
            ["FASTAPI_OUTBOUND_READ_TIMEOUT", "FASTAPI_OUTBOUND_TIMEOUT_READ"],
            90.0,
        )
        FASTAPI_OUTBOUND_WRITE_TIMEOUT: float = _env_float_first(
            ["FASTAPI_OUTBOUND_WRITE_TIMEOUT", "FASTAPI_OUTBOUND_TIMEOUT_WRITE"],
            30.0,
        )
        FASTAPI_OUTBOUND_POOL_TIMEOUT: float = _env_float_first(
            ["FASTAPI_OUTBOUND_POOL_TIMEOUT", "FASTAPI_OUTBOUND_TIMEOUT_POOL"],
            10.0,
        )

        KB_SEARCH_PROVIDER: str = _env("KB_SEARCH_PROVIDER", "tfidf")
        KB_FILE_PATH: str = _env("KB_FILE_PATH", "")

        FLASHCARDS_AI_MAX_CONCURRENT: int = _env_int("FLASHCARDS_AI_MAX_CONCURRENT", 20)
        FLASHCARDS_AI_SEMAPHORE_WAIT_SECONDS: float = _env_float(
            "FLASHCARDS_AI_SEMAPHORE_WAIT_SECONDS",
            10.0,
        )

settings = Settings()
