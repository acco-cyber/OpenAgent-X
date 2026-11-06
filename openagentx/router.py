"""Multi-model fallback routing — deterministic, offline, honest.

:class:`FallbackRouter` walks its adapter chain on every ``complete()`` call:
the first adapter that answers serves the turn, and *every* attempt — success
or failure — is recorded in the router's attempt log for this run. If the whole
chain fails, ``NoModelAvailable`` (an ``LLMUnavailable``) is raised; the runner
journals an ``error`` event and stops with the explicit reason
``model_unavailable``. Availability failures are first-class, observable
outcomes — never silent retries, never improvised replies.
"""

from __future__ import annotations

from .llm import LLMUnavailable


class ModelUnavailable(LLMUnavailable):
    """One adapter refused the call (offline stand-in for a 429/5xx/timeout)."""


class NoModelAvailable(LLMUnavailable):
    """Every adapter in the chain failed for this turn."""


class FailingLLM:
    """Fault-injection adapter: always raises ModelUnavailable."""

    def __init__(self, name: str = "failing", message: str = "simulated outage"):
        self.name = name
        self.message = str(message)
        self.calls = 0

    def complete(self, messages) -> dict:
        self.calls += 1
        raise ModelUnavailable(f"model '{self.name}' unavailable: {self.message}")


class FallbackRouter:
    """Route each turn to the first healthy adapter; record every attempt.

    ``log`` is the honest, per-run record of routing decisions (one entry per
    attempt, in order). A scripted adapter that exhausts its script counts as
    unavailable for that turn — the log says so, and the chain moves on.
    """

    def __init__(self, adapters, name: str = "router"):
        self.adapters = [(str(n), llm) for n, llm in adapters]
        self.name = name
        self.log: list = []
        self.served = 0

    def complete(self, messages) -> dict:
        failures: list = []
        for model_name, llm in self.adapters:
            try:
                out = llm.complete(messages)
            except Exception as e:  # noqa: BLE001 — routing observes, then moves on
                self.log.append({"model": model_name, "ok": False,
                                 "error": f"{type(e).__name__}: {e}"})
                failures.append(model_name)
                continue
            self.log.append({"model": model_name, "ok": True, "error": ""})
            self.served += 1
            return dict(out)
        raise NoModelAvailable(
            f"all {len(self.adapters)} models failed this turn: {', '.join(failures)}"
        )

    def attempts(self) -> list:
        """Copy of this run's routing attempts (no shared mutable state)."""
        return list(self.log)
