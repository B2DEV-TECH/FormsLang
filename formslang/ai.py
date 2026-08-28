"""AI provider layer.

One job: send messages, get text back. Every backend speaks raw HTTP over
``urllib`` from the standard library -- no SDK, no ``requests``, no
``httpx``. That is deliberate: FormsLang runs inside restricted corporate
networks where installing packages is a change request, and the code being
sent is the source under analysis. Fewer moving parts is a security argument,
not a style preference.

Backends: Anthropic, OpenAI, Azure OpenAI, Google, Ollama (local models --
the only option when the code may not leave the building) and Echo, an
offline stub that lets the workbench and the tests run with no network and
no key at all.

There are also two backends that are not endpoints at all: the Claude Code
CLI and the Codex CLI, driven as subprocesses. If you already pay for one of
those subscriptions, this is the cheapest way to run a portfolio -- no API
key to manage, no per-token bill, and the credentials stay wherever that CLI
already keeps them. FormsLang never reads them.

API keys come from the environment or from the settings file the in-app
Settings screen writes (see ``formslang.config``); the environment always
wins. A key is never logged, never included in an error message, and never
sent to the browser.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .config import load_config

DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_TOKENS = 4096
# An agent CLI boots a whole harness before it answers; 120s is not enough.
DEFAULT_CLI_TIMEOUT = 600.0


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
            f"{self.base_url}/v1beta/models/{self.model}:generateContent",
            # The key rides a header, never the URL: URLs end up in proxy
            # and server logs, headers do not.
            {"content-type": "application/json", "x-goog-api-key": self.api_key},
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

    The only backend where the source code never leaves the machine --
    which for some portfolios is the difference between using AI and not
    being allowed to.
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


class CliProvider(Provider):
    """Drive an agent CLI as a subprocess instead of calling an endpoint.

    Three rules make this safe enough to point at the source under
    analysis:

    * The prompt goes in on **stdin**, never on the command line. A single
      Forms trigger can be thousands of characters and Windows truncates a
      long argument list without saying so.
    * The process runs in an **empty scratch directory**. These CLIs are
      coding agents: started inside the source tree they would read
      project instruction files and wander into code we never meant to
      send. An empty cwd is the cheapest way to mean it.
    * Credentials are the CLI's business. FormsLang neither reads, stores nor
      forwards them, and ``describe()`` has nothing to leak.
    """

    binary = ""
    install_hint = ""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("timeout", DEFAULT_CLI_TIMEOUT)
        super().__init__(*args, **kwargs)

    # -- subclass hooks --------------------------------------------------

    def _argv(self, system: str, workdir: Path) -> list[str]:
        raise NotImplementedError

    def _extract(self, stdout: str, workdir: Path) -> str:
        raise NotImplementedError

    # -- the call --------------------------------------------------------

    def resolve(self) -> str:
        """Absolute path to the CLI, or a ProviderError naming the fix."""
        found = shutil.which(self.binary)
        if not found:
            raise ProviderError(
                f"{self.binary!r} is not on PATH. {self.install_hint}"
            )
        return found

    def complete(self, messages, max_tokens=DEFAULT_MAX_TOKENS):
        self.resolve()
        system, rest = _split_system(messages)
        prompt = "\n\n".join(m.content for m in rest)
        with tempfile.TemporaryDirectory(prefix="formslang-cli-") as tmp:
            workdir = Path(tmp)
            argv = self._argv(system, workdir)
            try:
                proc = subprocess.run(
                    argv,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=workdir,
                    timeout=self.timeout,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                raise ProviderError(
                    f"{self.binary} did not answer within {self.timeout:.0f}s"
                ) from None
            except OSError as e:
                raise ProviderError(f"could not run {self.binary}: {e}") from None

            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()[:400]
                raise ProviderError(f"{self.binary} exited {proc.returncode}: {detail}")
            return self._extract(proc.stdout, workdir)

    def describe(self) -> str:
        return f"{self.label} · {self.model or 'default'}"


class ClaudeCliProvider(CliProvider):
    """The Claude Code CLI in print mode.

    ``--system-prompt`` replaces the CLI's own agent prompt with the
    conversion doctrine, so the model is answering our question and not
    behaving like a coding assistant that happens to have been asked one.
    """

    type_id = "claude_cli"
    label = "Claude Code CLI"
    binary = "claude"
    default_model = "sonnet"
    install_hint = "Install it from https://claude.com/claude-code and run `claude` once to sign in."

    def _argv(self, system, workdir):
        argv = [
            self.resolve(),
            "-p",
            "--output-format", "json",
            "--strict-mcp-config",        # do not load the user's MCP servers
            "--no-session-persistence",   # analyzed code must not land in a session file
            "--exclude-dynamic-system-prompt-sections",
        ]
        if self.model:
            argv += ["--model", self.model]
        if system:
            argv += ["--system-prompt", system]
        return argv

    def _extract(self, stdout, workdir):
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            raise ProviderError(f"claude returned non-JSON: {stdout[:200]}") from None
        if data.get("is_error"):
            raise ProviderError(f"claude reported an error: {str(data.get('result'))[:300]}")
        return data.get("result", "")


class CodexCliProvider(CliProvider):
    """The Codex CLI in exec mode.

    ``-o`` writes the final message to a file, which is the only reliable way
    to get the answer out: stdout also carries the session banner, the token
    count and whatever the agent narrated on the way.
    """

    type_id = "codex_cli"
    label = "Codex CLI"
    binary = "codex"
    default_model = ""  # whatever the user configured in ~/.codex
    install_hint = "Install it with `npm i -g @openai/codex` and run `codex` once to sign in."

    def _argv(self, system, workdir):
        argv = [
            self.resolve(),
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",              # no session file holding analyzed code
            "-s", "read-only",          # it has no business writing anything
            "--color", "never",
            "-o", str(workdir / "answer.txt"),
        ]
        if self.model:
            argv += ["-m", self.model]
        return argv + ["-"]  # read the prompt from stdin

    def complete(self, messages, max_tokens=DEFAULT_MAX_TOKENS):
        # Codex has no system-prompt flag, so the doctrine leads the prompt.
        system, rest = _split_system(messages)
        if system:
            head = Message("user", system + "\n\n---\n\n" + (rest[0].content if rest else ""))
            messages = [head, *rest[1:]]
        return super().complete(messages, max_tokens)

    def _extract(self, stdout, workdir):
        answer = workdir / "answer.txt"
        if answer.exists():
            text = answer.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return text
        raise ProviderError(f"codex produced no final message: {stdout.strip()[-300:]}")


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
                        "-- Pick a model in Settings (the gear in the top bar)\n"
                        "-- for a real proposal, or write the APEX code yourself.\n",
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
        ClaudeCliProvider,
        CodexCliProvider,
        EchoProvider,
    )
}

# Model choices offered in the workbench. Free text is still accepted -- this
# is a shortcut, not a whitelist, and it goes stale the day a model ships.
MODEL_HINTS: dict[str, list[str]] = {
    "anthropic": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    "openai": ["gpt-5.2", "gpt-5.2-mini", "o4-mini"],
    "google": ["gemini-2.5-pro", "gemini-2.5-flash"],
    "ollama": ["qwen2.5-coder:32b", "codellama:34b", "llama3.3"],
    "claude_cli": ["opus", "sonnet", "haiku"],
    "codex_cli": [],  # whatever the user configured in ~/.codex
    "azure_openai": [],
    "echo": [],
}


# The environment variable behind each settings-file key. The environment
# always wins; the file (written by the in-app Settings screen) is the
# fallback that survives a restart.
ENV_FOR = {
    "provider": "FORMSLANG_AI_PROVIDER",
    "model": "FORMSLANG_AI_MODEL",
    "api_key": "FORMSLANG_AI_KEY",
    "base_url": "FORMSLANG_AI_BASE_URL",
    "deployment": "FORMSLANG_AI_DEPLOYMENT",
    "api_version": "FORMSLANG_AI_API_VERSION",
}


def setting(name: str, config: dict | None = None) -> str:
    """One AI setting: the environment wins, the saved file is the fallback."""
    value = os.environ.get(ENV_FOR[name], "").strip()
    if value:
        return value
    cfg = load_config() if config is None else config
    return str(cfg.get(name) or "").strip()


def provider_catalog() -> list[dict]:
    """Everything the UI needs to offer a provider picker."""
    has_key = bool(setting("api_key"))
    out = []
    for type_id, cls in sorted(PROVIDERS.items()):
        needs_key = not issubclass(cls, (CliProvider, EchoProvider, OllamaProvider))
        entry = {
            "id": type_id,
            "label": cls.label,
            "default_model": cls.default_model,
            "models": MODEL_HINTS.get(type_id, []),
            "needs_key": needs_key,
            "kind": "cli" if issubclass(cls, CliProvider) else "http",
        }
        if issubclass(cls, CliProvider):
            entry["available"] = shutil.which(cls.binary) is not None
            entry["hint"] = cls.install_hint
        elif needs_key:
            entry["available"] = has_key
            entry["hint"] = (
                "Add an API key in Settings, or set FORMSLANG_AI_KEY in the "
                "environment; either way it never travels through the browser."
            )
        out.append(entry)
    return out


def build_provider(type_id: str, **kwargs) -> Provider:
    cls = PROVIDERS.get((type_id or "").strip().lower())
    if cls is None:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"unknown AI provider {type_id!r} (known: {known})")
    return cls(**kwargs)


def provider_from_env(override: str = "") -> Provider:
    """Build the provider from the environment plus the saved settings.

    ``FORMSLANG_AI_PROVIDER``  anthropic | openai | azure_openai | google |
                               ollama | claude_cli | codex_cli | echo
    ``FORMSLANG_AI_MODEL``     model name (each provider has a default)
    ``FORMSLANG_AI_KEY``       API key -- the CLI providers need none, they
                               use their own login
    ``FORMSLANG_AI_BASE_URL``  override for a proxy or a private endpoint
    ``FORMSLANG_AI_DEPLOYMENT``/``FORMSLANG_AI_API_VERSION``  Azure only

    Each value falls back to the settings file the in-app Settings screen
    writes (``formslang.config``); an environment variable always wins over
    the file. Defaults to the offline provider, so nothing is ever sent
    anywhere by accident.
    """
    cfg = load_config()
    type_id = override or setting("provider", cfg) or "echo"
    return build_provider(
        type_id,
        model=setting("model", cfg),
        api_key=setting("api_key", cfg),
        base_url=setting("base_url", cfg),
        deployment=setting("deployment", cfg),
        api_version=setting("api_version", cfg),
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
