# AI Provider System

The Django AI engine uses a multi-provider AI orchestrator (`apps/core/ai_engine/client.py`) that tries
providers in priority order and falls back automatically when one fails.

## How It Works

`AIClient.generate_content()` iterates through the configured provider list. The first
provider that returns a non-empty response wins. If every provider fails, an
`APIIntegrationError` is raised (or an empty string is returned when
`raise_on_error=False`).

```
Request → nvidia_deepseek → nvidia_openai → claude   (default order)
               ↓ fail            ↓ fail         ↓ success → response
```

Provider order is set at startup via `AI_PROVIDER_ORDER` env var or the default
`["nvidia_deepseek", "nvidia_openai", "claude"]`.

## Supported Providers

| Provider key      | Env var(s)                                                              | Notes                              |
|-------------------|-------------------------------------------------------------------------|------------------------------------|
| `claude`          | `CLAUDE_API_KEY`, `CLAUDE_MODEL`                                        | Anthropic SDK; see section below   |
| `nvidia_deepseek` | `NVIDIA_DEEPSEEK_API_KEY`, `NVIDIA_DEEPSEEK_MODEL`, `NVIDIA_DEEPSEEK_THINKING` | OpenAI-compatible endpoint         |
| `nvidia_openai`   | `NVIDIA_OPENAI_API_KEY`, `NVIDIA_OPENAI_MODEL`                          | OpenAI-compatible endpoint         |
| `azure`           | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | Has content-filter fallback        |
| `deepseek`        | `DEEPSEEK_API_KEY`, `DEEPSEEK_API_URL`                                  |                                    |
| `gemini`          | `GEMINI_API_KEY`, `GEMINI_API_URL`                                      |                                    |
| `huggingface`     | `HUGGING_FACE_API_TOKEN`, `HUGGING_FACE_MODEL`                          |                                    |

A provider is silently skipped when its API key is missing — no error is raised, the
orchestrator just moves to the next one.

## Claude Integration

Claude uses the official **`anthropic` Python SDK** (`anthropic.AsyncAnthropic`), not raw
HTTP. The SDK client is created once per `AIClient` instance (in `_refresh_keys`) and
reused across requests so the underlying HTTP connection pool stays warm.

### Environment variables

| Variable       | Required | Default             | Description                        |
|----------------|----------|---------------------|------------------------------------|
| `CLAUDE_API_KEY` | Yes    | —                   | Anthropic API key                  |
| `CLAUDE_MODEL`   | No     | `claude-opus-4-6`   | Model ID — see valid IDs below     |

### Valid model IDs

| Model              | ID                    |
|--------------------|-----------------------|
| Claude Opus 4.6    | `claude-opus-4-6`     |
| Claude Sonnet 4.6  | `claude-sonnet-4-6`   |
| Claude Haiku 4.5   | `claude-haiku-4-5`    |

Do **not** append date suffixes (e.g. `claude-opus-4-6-20250514`) — that will cause a
404 error.

### Minimal local setup

Add to `backend/.env`:

```bash
CLAUDE_API_KEY=sk-ant-...
# Optional — override the model
# CLAUDE_MODEL=claude-sonnet-4-6
```

To make Claude the first (or only) provider:

```bash
AI_PROVIDER_ORDER=claude
```

### Error mapping

The SDK raises typed exceptions which `_call_claude` maps to `APIIntegrationError` so
the orchestrator's fallback logic works uniformly:

| SDK exception                | Mapped to                                   |
|------------------------------|---------------------------------------------|
| `anthropic.AuthenticationError` | `APIIntegrationError` (bad key)          |
| `anthropic.RateLimitError`      | `APIIntegrationError` (rate limit)       |
| `anthropic.APIStatusError`      | `APIIntegrationError` (other HTTP error) |

## Adding a New Provider

1. Add key attributes in `_refresh_keys()`.
2. Add a branch in `generate_content()` matching on the provider name string.
3. Implement `_call_<name>(self, client, prompt, max_tokens, timeout)` returning `str`.
4. Document the new env vars in this file and in `QUICK_REFERENCE.md`.
