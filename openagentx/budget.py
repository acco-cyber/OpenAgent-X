"""X-Budget: every run has hard ceilings, checked *before* action.

The blueprint's cost thesis in one module:

* No loop iteration starts without headroom (``BudgetLedger.claim``).
* Context is filled newest-first under a computed window budget with a
  reserved response area and a safety margin (**write-before-compaction** —
  nothing gets evicted that a rolling summary has not covered yet).
* Exceeding a ceiling is an *event* (``kernel.budget_exceeded``), not a
  silent overrun.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from openagentx.llm import LLMResponse, Usage


class BudgetExceededError(RuntimeError):
    """Raised when a ceiling would be crossed by the next action."""

    def __init__(self, ceiling: str, detail: str) -> None:
        super().__init__(f"budget exceeded: {ceiling} — {detail}")
        self.ceiling = ceiling
        self.detail = detail


@dataclass(frozen=True)
class Budget:
    """Hard ceilings for one run. ``None`` means unlimited (use sparingly)."""

    max_tokens: int | None = 60_000          # total model tokens (prompt + completion)
    max_tool_calls: int | None = 40          # tool executions per run
    max_iterations: int = 24                 # loop iterations per run
    deadline_seconds: float | None = 600.0   # wall clock per run
    response_reserve_tokens: int = 1_024     # always kept free for the model's answer
    context_margin_tokens: int = 256         # safety margin under the window

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_tokens": self.max_tokens,
            "max_tool_calls": self.max_tool_calls,
            "max_iterations": self.max_iterations,
            "deadline_seconds": self.deadline_seconds,
            "response_reserve_tokens": self.response_reserve_tokens,
            "context_margin_tokens": self.context_margin_tokens,
        }


@dataclass
class BudgetLedger:
    """Mutable accounting state for one run, bound to a :class:`Budget`."""

    budget: Budget
    usage: Usage = field(default_factory=Usage)
    tool_calls: int = 0
    iterations: int = 0
    started_at: float = field(default_factory=time.monotonic)

    # ------------------------------------------------------------- accounting

    def charge(self, response: LLMResponse) -> None:
        """Record token usage of one completion."""
        self.usage = Usage(
            prompt_tokens=self.usage.prompt_tokens + response.usage.prompt_tokens,
            completion_tokens=self.usage.completion_tokens + response.usage.completion_tokens,
        )

    def charge_tool_call(self) -> None:
        self.tool_calls += 1

    def next_iteration(self) -> int:
        """Claim the next loop iteration, enforcing every ceiling first."""
        if self.iterations + 1 > self.budget.max_iterations:
            raise BudgetExceededError(
                "max_iterations",
                f"{self.iterations}/{self.budget.max_iterations} used",
            )
        if self.budget.max_tool_calls is not None and self.tool_calls >= self.budget.max_tool_calls:
            raise BudgetExceededError(
                "max_tool_calls",
                f"{self.tool_calls}/{self.budget.max_tool_calls} used",
            )
        if self.budget.max_tokens is not None:
            # Reserve room for the *next* completion, not just what was spent.
            projected = self.usage.total_tokens + self.budget.response_reserve_tokens
            if projected > self.budget.max_tokens:
                raise BudgetExceededError(
                    "max_tokens",
                    f"{self.usage.total_tokens}/{self.budget.max_tokens} used "
                    f"(+{self.budget.response_reserve_tokens} reserved)",
                )
        if (
            self.budget.deadline_seconds is not None
            and time.monotonic() - self.started_at > self.budget.deadline_seconds
        ):
            raise BudgetExceededError(
                "deadline_seconds",
                f"{time.monotonic() - self.started_at:.0f}s elapsed",
            )
        self.iterations += 1
        return self.iterations

    # -------------------------------------------------- context window budget

    def context_token_budget(self, model_window_tokens: int) -> int:
        """Tokens available for history under the write-before-compaction rule.

        ``window − max_response − margin`` — the response area is reserved
        *before* history is filled, so the model can always answer.
        """
        return max(
            0,
            model_window_tokens
            - self.budget.response_reserve_tokens
            - self.budget.context_margin_tokens,
        )

    def to_payload(self) -> dict[str, Any]:
        """Event-payload snapshot of the ledger."""
        return {
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "tool_calls": self.tool_calls,
            "iterations": self.iterations,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 3),
            "ceilings": self.budget.to_dict(),
        }
