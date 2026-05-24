import json
import logging
import httpx
import openai
import anthropic
from typing import List, Optional, Union
from core.config import settings
from core.utils import _coerce_text, _extract_json_substring

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds — large-document prompts can take 15-25s to process
DEFAULT_PROVIDER_ORDER = ["openai", "nvidia_deepseek", "nvidia_openai", "claude"]


class APIIntegrationError(Exception):
    """Raised when all AI providers fail or a configured provider fails fatally."""
    pass


class AIClient:
    """
    Async AI provider orchestrator.

    Two public methods:
      generate_content(client, prompt, ...)
          One-shot text generation. Used by all existing service routes.

      generate_with_tools(messages, tools, ...)
          MCP orchestration step. Sends a messages list + tool definitions to
          the AI. Returns either a final text response or a list of tool calls.
          Primary: Claude (Anthropic native tool use).
          Fallback: OpenAI-compatible providers (NVIDIA, Azure).
          Last resort: text-mode (embed schemas in prompt, parse JSON).

    Provider priority (default): nvidia_deepseek → nvidia_openai → claude
    """
    def __init__(self, provider_priority: Optional[List[str]] = None):
        self.providers = provider_priority or DEFAULT_PROVIDER_ORDER
        self._refresh_keys()
        logger.info("AIClient initialized with providers: %s", self.providers)

    # Marker injected by wrap_document_context() in Django's prompts.py
    _DOC_MARKER = "STUDY MATERIAL — ANALYSE ONLY"

    def _system_msg(self, prompt: str) -> str:
        """
        Return an appropriate system message based on whether the prompt
        contains embedded study material (uploaded file context).

        When a document is present the system message must explicitly tell the
        model the content is inline — otherwise models trained to say "I can't
        access uploaded files" will refuse to use it.
        """
        if self._DOC_MARKER in prompt:
            return (
                "You are a helpful educational assistant. "
                "The user's message contains uploaded study material embedded between "
                "'====' separator lines. Read that material carefully and use it as "
                "your primary reference to answer the student's question at the end. "
                "Never say you cannot access files — the document content is right "
                "here in the message. Quote or paraphrase it directly in your response."
            )
        return "You are a helpful educational assistant. Provide accurate, structured responses."

    def _refresh_keys(self):
        # --- NVIDIA DeepSeek (OpenAI-compatible chat completions) ---
        self.nvidia_deepseek_key = settings.NVIDIA_DEEPSEEK_API_KEY
        self.nvidia_deepseek_url = settings.NVIDIA_DEEPSEEK_API_URL
        self.nvidia_deepseek_model = settings.NVIDIA_DEEPSEEK_MODEL
        self.nvidia_deepseek_thinking = settings.NVIDIA_DEEPSEEK_THINKING

        # --- Claude (Anthropic) ---
        self.claude_key = settings.CLAUDE_API_KEY
        self.claude_model = settings.CLAUDE_MODEL
        self._anthropic_client: Optional[anthropic.AsyncAnthropic] = (
            anthropic.AsyncAnthropic(api_key=self.claude_key)
            if self.claude_key else None
        )

        # --- NVIDIA OpenAI-compatible ---
        self.nvidia_openai_key = settings.NVIDIA_OPENAI_API_KEY
        self.nvidia_openai_url = settings.NVIDIA_OPENAI_API_URL
        self.nvidia_openai_model = settings.NVIDIA_OPENAI_MODEL

        # --- OpenAI ---
        self.openai_key = settings.OPENAI_API_KEY
        self.openai_model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        self._openai_client: Optional[openai.AsyncOpenAI] = (
            openai.AsyncOpenAI(api_key=self.openai_key)
            if self.openai_key else None
        )

        # --- Azure OpenAI ---
        self.azure_key = settings.AZURE_OPENAI_API_KEY
        self.azure_endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.azure_deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.azure_api_version = settings.AZURE_OPENAI_API_VERSION

        # --- DeepSeek ---
        self.deepseek_key = settings.DEEPSEEK_API_KEY
        self.deepseek_url = settings.DEEPSEEK_API_URL

        # --- Gemini ---
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_url = settings.GEMINI_API_URL

        # --- HuggingFace ---
        self.hf_token = settings.HUGGING_FACE_API_TOKEN
        self.hf_url_template = settings.HUGGING_FACE_API_URL_TEMPLATE

    async def generate_content(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        max_tokens: int = 1024,
        providers: Optional[List[str]] = None,
        raise_on_error: bool = True,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Union[dict, str]:
        provider_list = providers or self.providers
        errors = []

        for provider in provider_list:
            provider = provider.lower()
            try:
                if provider in ("nvidia_deepseek", "deepseek_nvidia") and self.nvidia_deepseek_key:
                    raw = await self._call_nvidia_deepseek(client, prompt, max_tokens, timeout)

                elif provider == "claude" and self.claude_key:
                    raw = await self._call_claude(client, prompt, max_tokens, timeout)

                elif provider == "nvidia_openai" and self.nvidia_openai_key:
                    raw = await self._call_nvidia_openai(client, prompt, max_tokens, timeout)

                elif provider == "openai" and self.openai_key:
                    raw = await self._call_openai(client, prompt, max_tokens, timeout)

                elif provider == "azure" and self.azure_key and (self.azure_endpoint or self.azure_deployment):
                    raw = await self._call_azure_openai(client, prompt, max_tokens, timeout)
                    if isinstance(raw, str) and "[Safety Block]" in raw:
                        logger.warning("Azure flagged content as unsafe. Trying next provider.")
                        errors.append((provider, "Content flagged by safety filter"))
                        continue

                elif provider == "deepseek" and self.deepseek_key:
                    raw = await self._call_deepseek(client, prompt, max_tokens, timeout)

                elif provider == "gemini" and self.gemini_key:
                    raw = await self._call_gemini(client, prompt, max_tokens, timeout)

                elif provider in ("huggingface", "hf") and self.hf_token:
                    raw = await self._call_huggingface(client, prompt, max_tokens, timeout)

                else:
                    errors.append((provider, "Provider not configured or missing API key"))
                    continue

                # --- Normalise the raw response to str or dict ---
                if isinstance(raw, dict):
                    text = json.dumps(raw)
                    if not text or text == "{}":
                        raise APIIntegrationError(f"{provider} returned empty JSON response")
                    return raw
                elif isinstance(raw, str):
                    text = raw.strip()
                    if not text:
                        raise APIIntegrationError(f"{provider} returned empty text")
                else:
                    text = str(raw).strip()
                    if not text:
                        raise APIIntegrationError(f"{provider} returned empty text")

                # Try full JSON parse first
                try:
                    parsed = json.loads(text)
                    # Extract content from OpenAI-style choices wrapper (Azure, NVIDIA OpenAI, DeepSeek)
                    if provider in ("azure", "nvidia_openai", "deepseek", "nvidia_deepseek", "openai") and isinstance(parsed, dict):
                        if "choices" in parsed:
                            content = _coerce_text(parsed["choices"][0].get("message", {}).get("content"))
                            if content:
                                logger.debug("%s extracted content: %s...", provider, content[:100])
                                return content
                    return parsed
                except json.JSONDecodeError:
                    parsed = _extract_json_substring(text)
                    if parsed is not None:
                        return parsed
                    return text

            except APIIntegrationError as e:
                logger.warning("Provider %s failed: %s", provider, str(e))
                errors.append((provider, str(e)))
                continue
            except Exception as e:
                logger.warning("Provider %s failed: %s", provider, str(e))
                errors.append((provider, str(e)))
                continue

        err_msg = "; ".join([f"{p}: {m}" for p, m in errors])
        if raise_on_error:
            raise APIIntegrationError(f"All AI providers failed: {err_msg}")
        return ""

    # ------------------------------------------------------------------ #
    #  MCP: generate_with_tools                                          #
    # ------------------------------------------------------------------ #

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],          # Anthropic-format tool definitions
        max_tokens: int = 1024,
        system: str = "",
        timeout: int = 60,
    ) -> dict:
        """
        Send a messages list + tool definitions to the AI.

        Returns:
            {
                "stop_reason": "tool_use" | "end_turn",
                "tool_calls":  [{"id": str, "name": str, "input": dict}],
                "text":        str | None,
                "raw_content": list,   # raw content blocks for history reconstruction
            }

        Provider cascade:
          1. Claude  — native Anthropic tool use (most reliable)
          2. NVIDIA OpenAI / Azure — OpenAI-format tool use
          3. Text-mode fallback — embed schemas in system prompt, parse JSON
        """
        # 1. Try Claude native tool use
        if self.claude_key and self._anthropic_client:
            try:
                return await self._claude_with_tools(messages, tools, max_tokens, system, timeout)
            except Exception as exc:
                logger.warning("[mcp:ai_client] Claude tool use failed: %s — trying next", exc)

        # 2. Try OpenAI native tool use
        if self.openai_key and self._openai_client:
            try:
                return await self._openai_with_tools(messages, tools, max_tokens, system, timeout)
            except Exception as exc:
                logger.warning("[mcp:ai_client] OpenAI tool use failed: %s — trying NVIDIA", exc)

        # 3. Try NVIDIA OpenAI-compatible tool use
        if self.nvidia_openai_key:
            try:
                return await self._openai_compat_with_tools(
                    self.nvidia_openai_url, self.nvidia_openai_model, self.nvidia_openai_key,
                    messages, tools, max_tokens, system, timeout,
                )
            except Exception as exc:
                logger.warning("[mcp:ai_client] NVIDIA OpenAI tool use failed: %s — trying Azure", exc)

        # 4. Try Azure OpenAI tool use
        if self.azure_key and self.azure_endpoint:
            try:
                return await self._openai_compat_with_tools(
                    self._azure_chat_url(), None, self.azure_key,
                    messages, tools, max_tokens, system, timeout, is_azure=True,
                )
            except Exception as exc:
                logger.warning("[mcp:ai_client] Azure tool use failed: %s — text-mode fallback", exc)

        # 5. Last resort: text-mode fallback
        logger.info("[mcp:ai_client] using text-mode tool fallback")
        return await self._text_mode_tool_fallback(messages, tools, max_tokens, system, timeout)

    async def _claude_with_tools(
        self, messages: list[dict], tools: list[dict],
        max_tokens: int, system: str, timeout: int,
    ) -> dict:
        """Claude native tool use via Anthropic SDK."""
        kwargs: dict = dict(model=self.claude_model, max_tokens=max_tokens,
                            tools=tools, messages=messages, timeout=timeout)
        if system:
            kwargs["system"] = system

        resp = await self._anthropic_client.messages.create(**kwargs)

        tool_calls, text_parts, raw_content = [], [], []
        for block in resp.content:
            raw_content.append(block)
            if block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})
            elif block.type == "text":
                text_parts.append(block.text)

        stop_reason = "tool_use" if tool_calls else "end_turn"
        logger.debug("[mcp:ai_client] claude stop_reason=%s calls=%d", stop_reason, len(tool_calls))
        return {
            "stop_reason": stop_reason,
            "tool_calls": tool_calls,
            "text": " ".join(text_parts).strip() or None,
            "raw_content": raw_content,
        }

    def _azure_chat_url(self) -> str:
        base = self.azure_endpoint.rstrip("/")
        if "/openai/deployments/" in base.lower():
            return f"{base}/chat/completions?api-version={self.azure_api_version}"
        return (f"{base}/openai/deployments/{self.azure_deployment}"
                f"/chat/completions?api-version={self.azure_api_version}")

    async def _openai_compat_with_tools(
        self, url: str, model: str | None, api_key: str,
        messages: list[dict], tools: list[dict],
        max_tokens: int, system: str, timeout: int,
        is_azure: bool = False,
    ) -> dict:
        """OpenAI-compatible tool use (NVIDIA, Azure)."""
        import json as _json

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

        all_messages = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload: dict = {"messages": all_messages, "tools": openai_tools,
                         "tool_choice": "auto", "max_tokens": max_tokens}
        if model:
            payload["model"] = model

        headers = ({"Content-Type": "application/json", "api-key": api_key} if is_azure
                   else {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice.get("message", {})
        tool_calls = []
        if choice.get("finish_reason") == "tool_calls":
            for tc in msg.get("tool_calls", []):
                raw_args = tc["function"].get("arguments", "{}")
                try:
                    args = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}
                tool_calls.append({"id": tc.get("id", ""), "name": tc["function"]["name"], "input": args})

        stop_reason = "tool_use" if tool_calls else "end_turn"
        logger.debug("[mcp:ai_client] openai-compat stop_reason=%s calls=%d", stop_reason, len(tool_calls))
        return {
            "stop_reason": stop_reason,
            "tool_calls": tool_calls,
            "text": msg.get("content") or None,
            "raw_content": [msg],
        }

    async def _text_mode_tool_fallback(
        self, messages: list[dict], tools: list[dict],
        max_tokens: int, system: str, timeout: int,
    ) -> dict:
        """
        Embed tool schemas in the system prompt and ask the AI to output a
        JSON action block when it wants to call a tool. Works on all providers
        but is less reliable than native tool use.
        """
        import json as _json

        tool_descs = "\n\n".join(
            f"Tool: {t['name']}\nDescription: {t.get('description', '')}\n"
            f"Input: {_json.dumps(t.get('input_schema', {}))}"
            for t in tools
        )
        tool_system = (
            f"{system}\n\nAvailable tools:\n\n{tool_descs}\n\n"
            f"To call a tool reply ONLY with this JSON (no other text):\n"
            f'{{"action":"tool_call","name":"<name>","input":{{...}}}}\n'
            f"If no tool is needed, reply normally."
        )
        history = ""
        for m in messages:
            role = m.get("role", "user").capitalize()
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
            history += f"{role}: {content}\n"

        full_prompt = f"{tool_system}\n\n{history}\nAssistant:"
        async with httpx.AsyncClient(timeout=timeout) as client:
            raw = await self.generate_content(client=client, prompt=full_prompt,
                                               max_tokens=max_tokens, timeout=timeout)

        text = raw if isinstance(raw, str) else _json.dumps(raw)
        text = text.strip()

        try:
            cleaned = text.lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = _json.loads(cleaned)
            if isinstance(parsed, dict) and parsed.get("action") == "tool_call":
                tc_id = f"textmode_{parsed['name']}_{id(parsed)}"
                logger.debug("[mcp:ai_client] text-mode detected tool_call name=%s", parsed["name"])
                return {
                    "stop_reason": "tool_use",
                    "tool_calls": [{"id": tc_id, "name": parsed["name"], "input": parsed.get("input", {})}],
                    "text": None,
                    "raw_content": [{"role": "assistant", "content": text}],
                }
        except Exception:
            pass

        return {
            "stop_reason": "end_turn",
            "tool_calls": [],
            "text": text,
            "raw_content": [{"role": "assistant", "content": text}],
        }

    # ------------------------------------------------------------------ #
    #  Provider implementations                                            #
    # ------------------------------------------------------------------ #

    async def _call_openai(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Call OpenAI via the official openai SDK (AsyncOpenAI)."""
        if self._openai_client is None:
            raise APIIntegrationError("OpenAI API key not configured (OPENAI_API_KEY)")

        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": self._system_msg(prompt)},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except openai.AuthenticationError as e:
            raise APIIntegrationError(f"OpenAI authentication failed: {e}") from e
        except openai.RateLimitError as e:
            raise APIIntegrationError(f"OpenAI rate limit exceeded: {e}") from e
        except openai.APIStatusError as e:
            raise APIIntegrationError(f"OpenAI API error ({e.status_code}): {e.message}") from e

        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise APIIntegrationError(f"OpenAI returned empty content. Finish reason: {resp.choices[0].finish_reason}")

        logger.debug("OpenAI response snippet: %s...", text[:120])
        return text

    async def _openai_with_tools(
        self, messages: list[dict], tools: list[dict],
        max_tokens: int, system: str, timeout: int,
    ) -> dict:
        """OpenAI native tool use via the official openai SDK."""
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

        all_messages = ([{"role": "system", "content": system}] if system else []) + list(messages)

        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.openai_model,
                messages=all_messages,
                tools=openai_tools,
                tool_choice="auto",
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except openai.AuthenticationError as e:
            raise APIIntegrationError(f"OpenAI authentication failed: {e}") from e
        except openai.RateLimitError as e:
            raise APIIntegrationError(f"OpenAI rate limit exceeded: {e}") from e
        except openai.APIStatusError as e:
            raise APIIntegrationError(f"OpenAI API error ({e.status_code}): {e.message}") from e

        choice = resp.choices[0]
        msg = choice.message
        tool_calls = []
        if choice.finish_reason == "tool_calls":
            for tc in (msg.tool_calls or []):
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except Exception:
                    args = {}
                tool_calls.append({"id": tc.id, "name": tc.function.name, "input": args})

        stop_reason = "tool_use" if tool_calls else "end_turn"
        logger.debug("[mcp:ai_client] openai stop_reason=%s calls=%d", stop_reason, len(tool_calls))
        return {
            "stop_reason": stop_reason,
            "tool_calls": tool_calls,
            "text": msg.content or None,
            "raw_content": [msg],
        }

    async def _call_claude(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        """
        Call Anthropic Claude using the official anthropic SDK.
        Docs: https://docs.anthropic.com/en/api/messages
        """
        if self._anthropic_client is None:
            raise APIIntegrationError("Claude API key not configured (CLAUDE_API_KEY)")

        try:
            message = await self._anthropic_client.messages.create(
                model=self.claude_model,
                max_tokens=max_tokens,
                system=self._system_msg(prompt),
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
        except anthropic.AuthenticationError as e:
            raise APIIntegrationError(f"Claude authentication failed: {e}") from e
        except anthropic.RateLimitError as e:
            raise APIIntegrationError(f"Claude rate limit exceeded: {e}") from e
        except anthropic.APIStatusError as e:
            raise APIIntegrationError(f"Claude API error ({e.status_code}): {e.message}") from e

        text = " ".join(
            block.text
            for block in message.content
            if block.type == "text"
        ).strip()

        if not text:
            raise APIIntegrationError(f"Claude returned empty content. Stop reason: {message.stop_reason}")

        logger.debug("Claude response snippet: %s...", text[:120])
        return text

    async def _call_nvidia_deepseek(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        """
        Call NVIDIA-hosted DeepSeek using OpenAI-compatible chat completions.
        """
        if not self.nvidia_deepseek_key:
            raise APIIntegrationError("NVIDIA DeepSeek API key not configured (NVIDIA_DEEPSEEK_API_KEY)")

        headers = {
            "Authorization": f"Bearer {self.nvidia_deepseek_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.nvidia_deepseek_model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_msg(prompt),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 1,
            "top_p": 0.95,
            "max_tokens": max_tokens,
            "stream": False,
        }

        if self.nvidia_deepseek_thinking:
            payload["chat_template_kwargs"] = {"thinking": True}

        resp = await client.post(self.nvidia_deepseek_url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()

        data = resp.json()
        content = _coerce_text(data.get("choices", [{}])[0].get("message", {}).get("content"))
        if not content:
            raise APIIntegrationError(f"NVIDIA DeepSeek returned empty content. Full response: {data}")

        logger.debug("NVIDIA DeepSeek response snippet: %s...", content[:120])
        return content

    async def _call_nvidia_openai(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        """
        Call NVIDIA-hosted models via their OpenAI-compatible chat completions endpoint.
        Docs: https://build.nvidia.com/explore/discover
        """
        if not self.nvidia_openai_key:
            raise APIIntegrationError("NVIDIA API key not configured (NVIDIA_OPENAI_API_KEY)")

        headers = {
            "Authorization": f"Bearer {self.nvidia_openai_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.nvidia_openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_msg(prompt),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 1,
            "stream": False,
        }

        resp = await client.post(self.nvidia_openai_url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {}) if isinstance(choice, dict) else {}

        # Standard OpenAI shape
        content = _coerce_text(message.get("content"))
        if not content:
            # Some NVIDIA-compatible models may place partial/truncated output in reasoning fields.
            reasoning = _coerce_text(message.get("reasoning_content")) or _coerce_text(message.get("reasoning"))
            if reasoning and "{" in reasoning and ("mcq_questions" in reasoning or "short_questions" in reasoning):
                logger.warning("NVIDIA returned null content; using reasoning fallback for downstream repair.")
                return reasoning

            finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
            raise APIIntegrationError(
                f"NVIDIA returned empty content (finish_reason={finish_reason}). Full response: {data}"
            )

        logger.debug("NVIDIA response snippet: %s...", content[:120])
        return content

    async def _call_deepseek(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_key}",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        resp = await client.post(self.deepseek_url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    async def _call_azure_openai(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> Union[dict, str]:
        if not self.azure_endpoint or not self.azure_key:
            raise APIIntegrationError("Azure OpenAI not configured")

        base_url = self.azure_endpoint.rstrip('/')
        if '/openai/deployments/' in base_url.lower():
            url = f"{base_url}/chat/completions?api-version={self.azure_api_version}"
        else:
            if not self.azure_deployment:
                raise APIIntegrationError("Azure OpenAI deployment name is required")
            url = f"{base_url}/openai/deployments/{self.azure_deployment}/chat/completions?api-version={self.azure_api_version}"

        headers = {"Content-Type": "application/json", "api-key": self.azure_key}
        payload = {
            "messages": [
                {"role": "system", "content": self._system_msg(prompt)},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        resp = await client.post(url, headers=headers, json=payload, timeout=timeout)

        if resp.status_code == 400:
            try:
                inner = resp.json().get("error", {}).get("innererror", {})
                if inner.get("code") == "ResponsibleAIPolicyViolation":
                    logger.warning("Azure content filter triggered.")
                    return "[Safety Block] Azure content filter"
            except Exception:
                pass

        if resp.status_code != 200:
            logger.error("Azure API Error: %s - %s", resp.status_code, resp.text)
            resp.raise_for_status()

        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise APIIntegrationError(f"Azure returned invalid JSON: {e}")

    async def _call_gemini(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        if not self.gemini_key or not self.gemini_url:
            raise APIIntegrationError("Gemini not configured")
        headers = {"Authorization": f"Bearer {self.gemini_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "max_output_tokens": max_tokens}
        resp = await client.post(self.gemini_url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    async def _call_huggingface(self, client: httpx.AsyncClient, prompt: str, max_tokens: int, timeout: int = DEFAULT_TIMEOUT) -> str:
        if not self.hf_token:
            raise APIIntegrationError("HuggingFace token not configured")
        model = settings.HUGGING_FACE_MODEL
        url = self.hf_url_template.format(model=model)
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}}
        resp = await client.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return resp.text


# ------------------------------------------------------------------ #
#  Global singleton                                                    #
# ------------------------------------------------------------------ #
ai_client = AIClient(provider_priority=settings.provider_list or DEFAULT_PROVIDER_ORDER)