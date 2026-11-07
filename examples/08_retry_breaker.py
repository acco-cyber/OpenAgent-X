"""Offline example 08 — retry + breaker: transient faults are retried on a
deterministic backoff schedule; a dead dependency trips the circuit.

A flaky adapter (fails its first two calls) is recovered by ``RetryLLM`` —
every attempt logged with its delay, the final reply unchanged. A second
scenario lets ``CircuitBreaker`` trip after repeated failures: calls are
then rejected without touching the dead inner, the cooldown elapses
call-by-call, and one successful probe closes the circuit again.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.breaker import CircuitBreaker, CircuitOpen
from openagentx.llm import LLMUnavailable, ScriptedLLM
from openagentx.retry import BackoffPolicy, RetryLLM


class FlakyLLM:
    """Fails the first *fail_first* calls with a transient outage."""

    def __init__(self, script, fail_first):
        self.inner = ScriptedLLM(script)
        self.fail_first = int(fail_first)
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise LLMUnavailable(f"transient outage (call {self.calls})")
        return self.inner.complete(messages)


class DownThenGoodLLM:
    """Fails the first *fail_first* calls, then serves the script."""

    def __init__(self, fail_first, script):
        self.inner = ScriptedLLM(script)
        self.fail_first = int(fail_first)
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise LLMUnavailable("dependency down")
        return self.inner.complete(messages)


def main() -> int:
    wd = tempfile.mkdtemp(prefix="oax-example-08-")

    # 1) retry: two transient failures, then success — scars on the log
    flaky = FlakyLLM(['{"reply": "the answer is 42"}'], fail_first=2)
    retry = RetryLLM(flaky, BackoffPolicy(max_attempts=4, base_delay=0.001,
                                          factor=2.0))
    turn = retry.complete([{"role": "user", "content": "compute"}])
    print(f"retry: turn={turn}")
    print(f"retry: attempts={retry.attempts}")

    assert turn == {"reply": "the answer is 42"}
    assert [a["ok"] for a in retry.attempts] == [False, False, True]
    assert [a["delay"] for a in retry.attempts] == [0.001, 0.002, 0.0]
    assert flaky.calls == 3

    # 2) breaker: trip on repeated failures, fast-fail, probe recovers
    dtg = DownThenGoodLLM(fail_first=3, script=['{"reply": "recovered"}'])
    breaker = CircuitBreaker(dtg, threshold=3, cooldown_calls=2)
    failures = 0
    for _ in range(3):
        try:
            breaker.complete([])
        except LLMUnavailable:
            failures += 1
    print(f"breaker: after trip snapshot={breaker.snapshot()}")
    assert failures == 3 and breaker.snapshot()["state"] == "open"

    rejected = 0
    for _ in range(2):
        try:
            breaker.complete([])
        except CircuitOpen:
            rejected += 1
    inner_calls_at_reject = dtg.calls
    print(f"breaker: rejections={rejected} inner_calls={inner_calls_at_reject}")
    assert rejected == 2
    assert inner_calls_at_reject == 3, "rejections never consult the inner"
    assert breaker.snapshot()["state"] == "open", "cooldown not yet elapsed"

    probe = breaker.complete([])  # cooldown elapsed: this call IS the probe
    print(f"breaker: probe={probe} snapshot={breaker.snapshot()}")
    assert probe == {"reply": "recovered"}
    assert breaker.snapshot()["state"] == "closed"
    assert breaker.snapshot()["probes"] == 1
    print("OK 08_retry_breaker (deterministic backoff recovery,"
          " trip -> fast-fail -> probe close)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
