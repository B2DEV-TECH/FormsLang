"""AI provider layer.

One job: send messages, get text back. Every backend speaks raw HTTP over
``urllib`` from the standard library -- no SDK, no ``requests``, no
``httpx``. That is deliberate: FormsLang runs inside customer networks where
installing packages is a change request, and the code being sent is the
customer's own source. Fewer moving parts is a security argument, not a
style preference.

Backends: Anthropic, OpenAI, Azure OpenAI, Google, Ollama (local models --
the only option when the code may not leave the building) and Echo, an
offline stub that lets the workbench and the tests run with no network and
no key at all.

API keys are read from the environment and never written to disk, never
logged, and never included in an error message.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_TOKENS = 4096


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


class ProviderError(Exception):
    """Provider call failed: network, auth, rate limit or malformed answer."""


def _post_json(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    """POST JSON, return parsed JSON. Raises ProviderError with the body."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise ProviderError(f"HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        # e.reason may carry the host, never the key.
        raise ProviderError(f"connection failed: {e.reason}") from None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ProviderError(f"provider returned non-JSON: {raw[:200]}") from None


def _split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    rest = [m for m in messages if m.role != "system"]
    return system, rest


class Provider:
    """Base class. Subclasses implement ``complete``."""

    type_id = ""
    label = ""
    default_model = ""
    default_base_url = ""

    def __init__(
        self,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        **extra: str,
    ):
        self.model = model or self.default_model
        self.api_key = api_key
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.timeout = timeout
        self.extra = extra

    def complete(self, messages: list[Message], max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
        raise NotImplementedError

    def describe(self) -> str:
        """What to show in the UI. Never includes the key."""
        return f"{self.label} · {self.model}"


class AnthropicProvider(Provider):
    type_id = "anthropic"
    label = "Claude (Anthropic)"
    default_model = "claude-sonnet-4-6"
    default_base_url = "https://api.anthropic.com"
    api_version = "2023-06-01"

    def complete(self, messages, max_tokens=DEFAULT_MAX_TOKENS):
        system, rest = _split_system(messages)
        payload: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in rest],
        }
        if system:
            payload["system"] = system
        data = _post_json(
            f"{self.base_url}/v1/messages",
            {
                "x-api-key": self.api_key,
                "anthropic-version": self.api_version,
                "content-type": "application/json",
            },
            payload,
            self.timeout,
        )
        return "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )


class OpenAIProvider(Provider):
    type_id = "openai"
    label = "OpenAI"
    default_model = "gpt-4o"
    default_base_url = "https://api.openai.com"

    def _url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def _headers(self) -> dict:
        return {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

    def _payload(self, messages, max_tokens) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_completion_tokens": max_tokens,
        }

    def complete(self, messages, max_tokens=DEFAULT_MAX_TOKENS):
        data = _post_json(self._url(), self._headers(), self._payload(messages, max_tokens), self.timeout)
        out = []
        for choice in data.get("choices", []):
            text = (choice.get("message") or {}).get("content")
            if text:
                out.append(text)
        return "".join(out)


class AzureOpenAIProvider(OpenAIProvider):
    """Same wire format as OpenAI; different URL shape and auth header."""

    type_id = "azure_openai"
    label = "Azure OpenAI"
    default_api_version = "2024-08-01-preview"

    def _url(self) -> str:
        deployment = self.extra.get("deployment") or self.model
        version = self.extra.get("api_version") or self.default_api_version
        return (
            f"{self.base_url}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={version}"
        )

    def _headers(self) -> dict:
        return {"api-key": self.api_key, "content-type": "application/json"}

    def _payload(self, messages, max_tokens) -> dict:
        payload = super()._payload(messages, max_tokens)
        payload.pop("model", None)  # the deployment is the model on Azure
        return payload


class GoogleProvider(Provider):
    type_id = "google"
    label = "Gemini (Google)"
    default_model = "gemini-2.5-pro"
    default_base_url = "https://generativelanguage.googleapis.com"

    def complete(self, messages, max_tokens=DEFAULT_MAX_TOKENS):
        system, rest = _split_system(messages)
        payload: dict = {
            "contents": [
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in rest
            ],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        data = _post_json(
            f"{self.base_url}/v1beta/models/{self.model}:generateContent?key={self.api_key}",
            {"content-type": "application/json"},
            payload,
            self.timeout,
        )
        out = []
        for cand in data.get("candidates", []):
            for part in (cand.get("content") or {}).get("parts", []):
                if part.get("text"):
                    out.append(part["text"])
        return "".join(out)


class OllamaProvider(Provider):
    """Local model over the Ollama HTTP API.

    The only backend where the customer's source code never leaves the
    machine -- which for some portfolios is the difference between using AI
    and not being allowed to.
    """

    type_id = "ollama"
    label = "Ollama (local)"
    default_model = "qwen2.5-coder:14b"
    default_base_url = "http://127.0.0.1:11434"

    def complete(self, messages, max_tokens=DEFAULT_MAX_TOKENS):
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        data = _post_json(
            f"{self.base_url}/api/chat",
            {"content-type": "application/json"},
            payload,
            self.timeout,
        )
        return (data.get("message") or {}).get("content", "")


class EchoProvider(Provider):
    """Offline stub. No network, no key, deterministic.

    It answers with a well-formed proposal whose confidence is zero and whose
    note says plainly that no model ran. That matters: a demo of the
    workbench must never be mistakable for a real conversion.
    """

    type_id = "echo"
    label = "Offline (no model)"
    default_model = "echo"

    def complete(self, messages, max_tokens=DEFAULT_MAX_TOKENS):
        source = messages[-1].content if messages else ""
        return json.dumps(
            {
                "apex_target": "UNDECIDED",
                "code": "-- No AI provider configured; nothing was converted.\n"
                        "-- Configure FORMSLANG_AI_PROVIDER to get a real proposal.\n",
                "notes": ["Offline provider: this is a placeholder, not a conversion."],
                "open_questions": ["Which AI provider should this portfolio use?"],
                "confidence": 0.0,
                "source_chars": len(source),
            }
        )


PROVIDERS: dict[str, type[Provider]] = {
    p.type_id: p
    for p in (
        AnthropicProvider,
        OpenAIProvider,
        AzureOpenAIProvider,
        GoogleProvider,
        OllamaProvider,
        EchoProvider,
    )
}


def build_provider(type_id: str, **kwargs) -> Provider:
    cls = PROVIDERS.get((type_id or "").strip().lower())
    if cls is None:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"unknown AI provider {type_id!r} (known: {known})")
    return cls(**kwargs)


def provider_from_env(override: str = "") -> Provider:
    """Build the provider from the environment.

    ``FORMSLANG_AI_PROVIDER``  anthropic | openai | azure_openai | google | ollama | echo
    ``FORMSLANG_AI_MODEL``     model name (each provider has a default)
    ``FORMSLANG_AI_KEY``       API key -- read here, never persisted
    ``FORMSLANG_AI_BASE_URL``  override for a proxy or a private endpoint
    ``FORMSLANG_AI_DEPLOYMENT``/``FORMSLANG_AI_API_VERSION``  Azure only

    Defaults to the offline provider, so nothing is ever sent anywhere by
    accident.
    """
    type_id = override or os.environ.get("FORMSLANG_AI_PROVIDER", "") or "echo"
    return build_provider(
        type_id,
        model=os.environ.get("FORMSLANG_AI_MODEL", ""),
        api_key=os.environ.get("FORMSLANG_AI_KEY", ""),
        base_url=os.environ.get("FORMSLANG_AI_BASE_URL", ""),
        deployment=os.environ.get("FORMSLANG_AI_DEPLOYMENT", ""),
        api_version=os.environ.get("FORMSLANG_AI_API_VERSION", ""),
    )


def check_provider(provider: Provider) -> tuple[bool, str]:
    """Short round trip to validate credentials and connectivity."""
    try:
        out = provider.complete(
            [
                Message("system", "Answer with one word."),
                Message("user", 'Say "ok".'),
            ],
            max_tokens=16,
        ).strip()
    except ProviderError as e:
        return False, str(e)
    except Exception as e:  # never leak a key through an unexpected traceback
        return False, f"{type(e).__name__}: {e}"
    if not out:
        return False, "provider answered with empty text"
    return True, out[:80]
