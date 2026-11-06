"""X-Gateway: model-agnostic LLM interface with capability-aware routing.

One tiny protocol, three concrete behaviors:

* :class:`EchoLLM` — deterministic offline model. Runs with **zero API keys**,
  which makes examples, CI, and onboarding work anywhere.
* :class:`OpenAICompatLLM` — thin adapter for any OpenAI-compatible endpoint
  (OpenAI, Azure, vLLM, Ollama, OpenRouter, ...). Uses stdlib ``urllib`` only.
  Credentials are read from environment variables by name — never hardcoded,
  never logged, and redacted if they ever reach a trace.
* :class:`RouterLLM` — capability-aware routing (the blueprint's cost thesis):
  cheap profiles handle classification/extraction; reasoning profiles handle
  planning and hard synthesis. One router, many endpoints.

Anti-pattern avoided (lesson from the reference analysis): never hand-roll a
bespoke client per vendor. One wire adapter (OpenAI-compatible), thin
profile configuration for everything else.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from openagentx.events import redact


@dataclass(frozen=True)
class Usage:
    """Token accounting for one completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LLMResponse:
    """One model completion, provider-agnostic."""

    text: str
    model: str
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = "stop"
    raw: dict[str, Any] | None = None  # provider payload (secrets redacted at trace boundary)


class GatewayError(RuntimeError):
    """Raised when a model call fails after normalizing provider errors."""


class LLM(Protocol):
    """Anything that can complete a chat — the kernel's only model dependency."""

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:  # pragma: no cover - protocol
        ...


# --------------------------------------------------------------------- Echo


class EchoLLM:
    """Deterministic offline model for demos, smoke tests, and CI.

    It never touches a network. It produces a short deterministic "reasoning"
    reply that echoes the latest user instruction, so agent-loop examples
    demonstrate tracing, budget accounting, and tool dispatch without keys.
    """

    model = "echo-1"

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        snippet = " ".join(str(last_user).split())[:160]
        text = (
            "[echo-1] Understood. Plan: (1) restate the goal — "
            f"{snippet!r}; (2) take the smallest reversible action; "
            "(3) report evidence. This is a deterministic offline reply "
            "from EchoLLM — wire a real provider via OPENAGENTX_API_KEY."
        )
        prompt_tokens = sum(len(str(m.get("content", ""))) // 4 + 1 for m in messages)
        completion_tokens = len(text) // 4 + 1
        return LLMResponse(
            text=text,
            model=self.model,
            usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        )


# ------------------------------------------------------- OpenAI-compatible


class OpenAICompatLLM:
    """Minimal adapter for any OpenAI-compatible ``/chat/completions`` API.

    Credentials come from an **environment variable name** (not a value):
    pass ``api_key_env="OPENAI_API_KEY"`` and the key is read at call time.
    This keeps secrets out of code, config files, and traces.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key_env: str = "OPENAGENTX_API_KEY",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model or os.environ.get("OPENAGENTX_MODEL", "gpt-4o-mini")
        self.base_url = (
            base_url or os.environ.get("OPENAGENTX_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise GatewayError(
                f"environment variable {self.api_key_env!r} is not set; "
                "export it or use EchoLLM for offline runs"
            )
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise GatewayError(f"model gateway HTTP {exc.code}: {redact(detail)}") from exc
        except urllib.error.URLError as exc:
            raise GatewayError(f"model gateway unreachable: {exc.reason}") from exc

        try:
            choice = payload["choices"][0]
            usage = payload.get("usage", {})
            return LLMResponse(
                text=choice["message"]["content"] or "",
                model=payload.get("model", self.model),
                usage=Usage(
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                ),
                finish_reason=choice.get("finish_reason", "stop"),
                raw=payload,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayError(
                f"unexpected gateway payload shape: {redact(str(payload))[:300]}"
            ) from exc


# ------------------------------------------------------------------ Routing


@dataclass(frozen=True)
class ModelProfile:
    """One routable model endpoint with its capability class."""

    name: str
    llm: LLM
    capability: str = "general"  # cheap | general | reasoning | code
    cost_per_1k: float = 0.0     # informational; drives routing demos


class RouterLLM:
    """Capability-aware router: pick the cheapest profile that can do the job.

    Callers pass ``capability=`` ("cheap" | "general" | "reasoning" | "code");
    the router selects the first matching profile by preference order.
    Which profile served the request is recorded by the loop as
    ``agent.model_selected``.
    """

    _PREFERENCE: dict[str, tuple[str, ...]] = {
        "cheap": ("cheap", "general", "reasoning", "code"),
        "general": ("general", "reasoning", "cheap", "code"),
        "reasoning": ("reasoning", "general", "code", "cheap"),
        "code": ("code", "reasoning", "general", "cheap"),
    }

    def __init__(self, profiles: list[ModelProfile]) -> None:
        if not profiles:
            raise ValueError("RouterLLM needs at least one ModelProfile")
        self.profiles = profiles
        self.last_profile: ModelProfile | None = None

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        capability: str = "general",
    ) -> LLMResponse:
        order = self._PREFERENCE.get(capability, self._PREFERENCE["general"])
        available = {p.capability: p for p in self.profiles}
        for cap in order:
            profile = available.get(cap)
            if profile is not None:
                self.last_profile = profile
                return profile.llm.complete(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
        fallback = self.profiles[0]
        self.last_profile = fallback
        return fallback.llm.complete(messages, temperature=temperature, max_tokens=max_tokens)
