"""Compatibility settings adapter for Django's in-process AI engine."""

from __future__ import annotations

import os

from django.conf import settings as django_settings


_DEFAULTS = {
    "OPENAI_API_KEY": "",
    "OPENAI_MODEL": "gpt-4o-mini",
    "CLAUDE_API_KEY": "",
    "CLAUDE_MODEL": "claude-sonnet-4-20250514",
    "NVIDIA_OPENAI_API_KEY": "",
    "NVIDIA_OPENAI_API_URL": "https://integrate.api.nvidia.com/v1/chat/completions",
    "NVIDIA_OPENAI_MODEL": "openai/gpt-oss-20b",
    "NVIDIA_DEEPSEEK_API_KEY": "",
    "NVIDIA_DEEPSEEK_API_URL": "https://integrate.api.nvidia.com/v1/chat/completions",
    "NVIDIA_DEEPSEEK_MODEL": "deepseek-ai/deepseek-v3.2",
    "NVIDIA_DEEPSEEK_THINKING": True,
    "AZURE_OPENAI_API_KEY": "",
    "AZURE_OPENAI_ENDPOINT": "",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-4o-mini-deployment",
    "AZURE_OPENAI_API_VERSION": "2025-01-01-preview",
    "DEEPSEEK_API_KEY": "",
    "DEEPSEEK_API_URL": "https://api.deepseek.com/v1/chat/completions",
    "GEMINI_API_KEY": "",
    "GEMINI_API_URL": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    "HUGGING_FACE_API_URL_TEMPLATE": "https://api-inference.huggingface.co/models/{model}",
    "HUGGING_FACE_MODEL": "mistralai/Mixtral-8x7B-Instruct-v0.1",
}


class AISettings:
    """Mirror the FastAPI engine's provider settings contract in Django."""

    def __getattr__(self, name: str):
        if name == "OPENAI_MODEL":
            return (
                getattr(django_settings, name, None)
                or getattr(django_settings, "TUTOR_MODEL", None)
                or os.getenv(name)
                or os.getenv("TUTOR_MODEL")
                or _DEFAULTS[name]
            )
        if name == "NVIDIA_DEEPSEEK_THINKING":
            configured = getattr(django_settings, name, None)
            if configured is None:
                configured = os.getenv(name)
            if configured is None:
                return _DEFAULTS[name]
            if isinstance(configured, str):
                return configured.strip().lower() in {"1", "true", "yes", "on"}
            return bool(configured)
        if name == "HUGGING_FACE_API_TOKEN":
            return (
                getattr(django_settings, name, None)
                or os.getenv(name)
                or os.getenv("HUGGING_FACE_API_KEY", "")
            )
        if name == "provider_list":
            value = (
                getattr(django_settings, "AI_PROVIDER_ORDER", None)
                or os.getenv("AI_PROVIDER_ORDER")
                or os.getenv("AI_PROVIDER_PRIORITY")
                or "nvidia_openai,nvidia_deepseek,claude,azure,deepseek,gemini,huggingface"
            )
            return [item.strip() for item in value.split(",") if item.strip()]

        if name in {
            "FASTAPI_OUTBOUND_CONNECT_TIMEOUT",
            "FASTAPI_OUTBOUND_READ_TIMEOUT",
            "FASTAPI_OUTBOUND_WRITE_TIMEOUT",
            "FASTAPI_OUTBOUND_POOL_TIMEOUT",
        }:
            defaults = {
                "FASTAPI_OUTBOUND_CONNECT_TIMEOUT": 10.0,
                "FASTAPI_OUTBOUND_READ_TIMEOUT": 90.0,
                "FASTAPI_OUTBOUND_WRITE_TIMEOUT": 30.0,
                "FASTAPI_OUTBOUND_POOL_TIMEOUT": 10.0,
            }
            return getattr(django_settings, name, defaults[name])

        if name in {"FASTAPI_OUTBOUND_MAX_CONNECTIONS", "FASTAPI_OUTBOUND_MAX_KEEPALIVE"}:
            defaults = {"FASTAPI_OUTBOUND_MAX_CONNECTIONS": 100, "FASTAPI_OUTBOUND_MAX_KEEPALIVE": 20}
            return getattr(django_settings, name, defaults[name])

        default = _DEFAULTS.get(name)
        if default is None:
            raise AttributeError(name)
        configured = getattr(django_settings, name, None)
        if configured is None:
            configured = os.getenv(name)
        return default if configured is None else configured


settings = AISettings()
