"""Circuit breaker: fail fast while a dependency is down, probe to recover.

The classic closed → open → half-open state machine, offline-deterministic:

- **closed**: calls pass through; ``threshold`` consecutive failures trip the
  breaker. The failure that trips still raises the *original* error — the
  caller sees the real fault, not a breaker artifact.
- **open**: calls fast-fail with :class:`CircuitOpen` *without consulting the
  inner adapter* (zero load while the dependency is down).
- **half-open**: after ``cooldown_calls`` rejected calls, exactly one probe
  goes through; success closes the circuit, failure re-opens it.

Time is a deterministic tick: every ``complete()`` call — rejected ones
included — advances the clock by one, so cooldown behavior is exact and
reproducible. :class:`CircuitOpen` subclasses ``LLMUnavailable``, so runners
journal an honest ``model_unavailable`` stop instead of crashing. The
``snapshot()`` is a plain dict of observed counters — nothing hidden.
"""

from __future__ import annotations

from .llm import LLMUnavailable

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class CircuitOpen(LLMUnavailable):
    """The circuit is open: the call was rejected without reaching the inner."""


class CircuitBreaker:
    """Wrap an adapter with the closed/open/half-open protection pattern."""

    def __init__(self, inner, threshold: int = 3, cooldown_calls: int = 2,
                 clock=None, name: str = "breaker"):
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        if cooldown_calls < 1:
            raise ValueError("cooldown_calls must be >= 1")
        self.inner = inner
        self.threshold = int(threshold)
        self.cooldown_calls = int(cooldown_calls)
        self._ticks = 0
        self._clock = clock or (lambda: self._ticks)
        self.name = name
        self.state = CLOSED
        self.failures = 0
        self.successes = 0
        self.rejections = 0
        self.opens = 0
        self.probes = 0
        self.last_error = ""
        self._opened_at = 0

    def _trip(self, why: str) -> None:
        self.state = OPEN
        self.opens += 1
        self._opened_at = self._clock()
        self.last_error = why

    def complete(self, messages) -> dict:
        self._ticks += 1  # every call advances deterministic time
        if self.state == OPEN:
            elapsed = self._clock() - self._opened_at
            if elapsed > self.cooldown_calls:
                self.state = HALF_OPEN  # cooldown elapsed: allow one probe
            else:
                self.rejections += 1
                raise CircuitOpen(
                    f"circuit {self.name!r} is open; probe allowed after "
                    f"{self.cooldown_calls - elapsed + 1} more calls")
        probing = self.state == HALF_OPEN
        if probing:
            self.probes += 1
        try:
            turn = self.inner.complete(messages)
        except LLMUnavailable as e:
            self.failures += 1
            self.last_error = f"{type(e).__name__}: {e}"
            if probing:
                self._trip(f"probe failed: {self.last_error}")
                raise
            if self.failures >= self.threshold:
                self._trip(self.last_error)
            raise
        self.successes += 1
        self.failures = 0
        if probing:
            self.state = CLOSED  # probe succeeded: close the circuit
        return turn

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "failures": self.failures,
            "successes": self.successes,
            "rejections": self.rejections,
            "opens": self.opens,
            "probes": self.probes,
        }
