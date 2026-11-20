"""Django's in-process AI engine, introduced alongside the FastAPI engine."""

from .client import AIClient, APIIntegrationError, ai_client

__all__ = ["AIClient", "APIIntegrationError", "ai_client"]
