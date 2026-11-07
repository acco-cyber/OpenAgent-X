"""Retry with deterministic exponential backoff — transient faults are real.

Real model endpoints fail transiently. :class:`RetryLLM` wraps any adapter
and retries *retryable* failures (subclasses of
:class:`~openagentx.llm.LLMUnavailable`) on a fixed, inspectable schedule.
Contracts:

- Honest bookkeeping: every attempt lands in ``attempts`` — outcome, error
  text, and the delay that followed it. A recovered call shows its scars.
- Deterministic schedule: :meth:`BackoffPolicy.delays` is the exact delay
  sequence; ``base_delay=0.0`` means offline-fast (no real sleeping).
- Non-retryable failures propagate immediately: a malformed script turn
  (``ScriptParseError``) or an exhausted script is a bug in the plan, not a
  transient fault — retrying it would launder the failure.
- Giving up is loud: :class:`RetryExhausted` (itself an ``LLMUnavailable``)
  names the attempt count, so runners journal an honest stop.
- Like the cache, retries are invisible to the journal: the runner sees one
  ``complete()`` and journals exactly what a healthy run would.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .llm import LLMUnavailable, ScriptExhausted, ScriptParseError


class RetryExhausted(LLMUnavailable):
    """Every attempt failed; the last error rides along as the cause."""


@dataclass(frozen=True)
class BackoffPolicy:
    """Deterministic exponential backoff schedule (no randomness)."""

    max_attempts: int = 3
    base_delay: float = 0.0
    factor: float = 2.0

    def delays(self) -> list:
        """Delays *between* attempts: exactly ``max_attempts - 1`` entries."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        out: list = []
        cur = float(self.base_delay)
        for _ in range(self.max_attempts - 1):
            out.append(round(cur, 6))
            cur *= self.factor
        return out


class RetryLLM:
    """Retry an unreliable adapter on a deterministic backoff schedule."""

    def __init__(self, inner, policy: BackoffPolicy = None,
                 retry_on=(LLMUnavailable,), name: str = "retry"):
        self.inner = inner
        self.policy = policy or BackoffPolicy()
        self.retry_on = tuple(retry_on)
        self.name = name
        self.calls = 0
        self.attempts: list = []  # {"ok": bool, "error": str, "delay": float}

    def schedule(self) -> list:
        return self.policy.delays()

    def complete(self, messages) -> dict:
        self.calls += 1
        delays = self.schedule()
        last_error = ""
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                turn = self.inner.complete(messages)
            except self.retry_on as e:  # transient — record, maybe wait, retry
                last_error = f"{type(e).__name__}: {e}"
                delay = delays[attempt - 1] if attempt - 1 < len(delays) else 0.0
                self.attempts.append({"ok": False, "error": last_error[:100],
                                      "delay": delay})
                if attempt >= self.policy.max_attempts:
                    raise RetryExhausted(
                        f"gave up after {attempt} attempts; last error: {last_error}"
                    ) from e
                if delay:
                    time.sleep(delay)
                continue
            # non-retryable exceptions (ScriptExhausted, ScriptParseError, ...)
            # intentionally propagate: they are plan bugs, not transient faults
            self.attempts.append({"ok": True, "error": "", "delay": 0.0})
            return turn
        raise RetryExhausted(f"unreachable retry state; last error: {last_error}")
