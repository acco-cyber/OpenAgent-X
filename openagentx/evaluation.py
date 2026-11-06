"""X-Eval: golden tasks + offline evaluation harness.

The benchmark plan (``docs/evaluation/benchmark-plan.md``) requires evidence,
not vibes. This module is the smallest honest step toward that: golden tasks
defined as **data**, run **deterministically offline** (zero API keys), and
reported as reproducible JSON with kernel/model metadata.

A golden task is one JSON file in ``golden_tasks/``:

```json
{
  "task_id": "read-then-report",
  "description": "agent lists files, then reports",
  "task": "List the files here, then report.",
  "max_iterations": 5,
  "script": ["{...model response 1...}", "{...model response 2...}"],
  "expect_status": "run.done",
  "expect_min_iterations": 2,
  "expect_max_iterations": 2,
  "expect_tools_used": ["fs_list"],
  "expect_denials": ["shell"],
  "expect_reply_contains": ["files"],
  "expect_budget_stopped": false
}
```

Only ``task_id`` and ``task`` are required. Everything else has a sane
default; unknown fields are rejected (a silent typo in an expectation must
not silently pass).

* ``script`` replays model responses in order (the last repeats on
  overrun). Absent ``script`` → :class:`openagentx.llm.EchoLLM` behavior.
  Scripts ending in a ``{"reply": …}`` finish cleanly; scripts that never
  finish drive the budget to stop them — both are testable.
* ``expect_tools_used`` — the tool was attempted **and** allowed by policy.
* ``expect_denials`` — the tool was attempted but **never allowed**: policy
  refused it outright (deny) or asked a human nobody could grant (ask).
* ``expect_budget_stopped`` — the run ended via budget/degeneracy guard.

Reports carry ``kernel_version`` + config so any run can be re-created —
the plan's reproducibility rule at v0.1 scale.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openagentx
from openagentx.budget import Budget
from openagentx.events import EventType
from openagentx.llm import EchoLLM, LLMResponse
from openagentx.loop import RUN_DONE, AgentKernel
from openagentx.policy import default_policy
from openagentx.tools import ToolRegistry
from openagentx.builtins import register_builtins
from openagentx.trace import TraceLog

BUDGET_STOPPED_STATUSES = ("budget_exceeded", "degeneracy")


# ------------------------------------------------------------------- model


class ScriptedLLM(EchoLLM):
    """Replays pre-written model responses, in order, forever-stubborn.

    The last response repeats on overrun: a script ending with
    ``{"reply": …}`` terminates the run; a script without one keeps acting
    until the budget stops it (exactly what budget golden tasks assert).
    Token usage accounting matches EchoLLM so reports stay comparable.
    """

    def __init__(self, script: list[str]) -> None:
        if not script:
            raise ValueError("ScriptedLLM needs at least one response")
        self.script = script
        self.calls = 0

    def complete(self, messages, *, temperature=0.2, max_tokens=None):  # type: ignore[override]
        text = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        usage = super().complete(messages, temperature=temperature, max_tokens=max_tokens).usage
        return LLMResponse(text=text, model=self.model, usage=usage)


# ------------------------------------------------------------------- tasks


_REQUIRED_FIELDS = ("task_id", "task")
_KNOWN_FIELDS = frozenset(
    {
        "task_id", "description", "task", "max_iterations", "script", "include_exec",
        "expect_status", "expect_min_iterations", "expect_max_iterations",
        "expect_tools_used", "expect_denials", "expect_reply_contains",
        "expect_budget_stopped",
    }
)


@dataclass
class GoldenTask:
    """One deterministic, offline-checkable agent scenario."""

    task_id: str
    task: str
    description: str = ""
    max_iterations: int = 4
    script: list[str] | None = None
    include_exec: bool = False   # register shell/python so guardrail tasks can assert denials
    expect_status: str = RUN_DONE
    expect_min_iterations: int = 1
    expect_max_iterations: int = 8
    expect_tools_used: list[str] = field(default_factory=list)
    expect_denials: list[str] = field(default_factory=list)
    expect_reply_contains: list[str] = field(default_factory=list)
    expect_budget_stopped: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: Path | None = None) -> "GoldenTask":
        where = f" ({source})" if source else ""
        missing = [f for f in _REQUIRED_FIELDS if not data.get(f)]
        if missing:
            raise ValueError(f"golden task missing fields {missing}{where}")
        unknown = set(data) - _KNOWN_FIELDS
        if unknown:
            raise ValueError(f"unknown expectation fields {sorted(unknown)}{where} — fix the typo")
        script = data.get("script")
        return cls(
            task_id=str(data["task_id"]),
            task=str(data["task"]),
            description=str(data.get("description", "")),
            max_iterations=int(data.get("max_iterations", 4)),
            script=[str(s) for s in script] if script else None,
            include_exec=bool(data.get("include_exec", False)),
            expect_status=str(data.get("expect_status", RUN_DONE)),
            expect_min_iterations=int(data.get("expect_min_iterations", 1)),
            expect_max_iterations=int(data.get("expect_max_iterations", 8)),
            expect_tools_used=[str(t) for t in data.get("expect_tools_used", [])],
            expect_denials=[str(t) for t in data.get("expect_denials", [])],
            expect_reply_contains=[str(s).lower() for s in data.get("expect_reply_contains", [])],
            expect_budget_stopped=bool(data.get("expect_budget_stopped", False)),
        )


def load_suite(suite_dir: str | Path | None = None) -> list[GoldenTask]:
    """Load every ``*.json`` golden task in the suite directory.

    Lookup order: explicit dir → ``./golden_tasks`` → the repo copy that
    ships next to the package (so the CLI works from anywhere).
    """
    candidates = (
        [Path(suite_dir)] if suite_dir
        else [Path("golden_tasks"), Path(__file__).resolve().parent.parent / "golden_tasks"]
    )
    root = next((c for c in candidates if c.is_dir()), None)
    if root is None:
        raise FileNotFoundError(
            f"golden task suite not found (looked in: {', '.join(map(str, candidates))})"
        )

    tasks: list[GoldenTask] = []
    for path in sorted(root.glob("*.json")):
        tasks.append(GoldenTask.from_dict(json.loads(path.read_text(encoding="utf-8")), source=path))
    if not tasks:
        raise ValueError(f"no golden tasks found in {root}")
    return tasks


# ------------------------------------------------------------------- runner


@dataclass
class TaskResult:
    """Outcome of one golden task: verdict plus the evidence behind it."""

    task_id: str
    passed: bool
    status: str
    iterations: int
    total_tokens: int
    model: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "status": self.status,
            "iterations": self.iterations,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "checks": self.checks,
            **({"error": self.error} if self.error else {}),
        }


def _check(result: TaskResult, name: str, ok: bool, detail: str) -> None:
    result.checks.append({"check": name, "passed": bool(ok), "detail": detail})
    if not ok:
        result.passed = False


def run_golden_task(golden: GoldenTask) -> TaskResult:
    """Run one golden task offline and check every declared expectation."""
    result = TaskResult(
        task_id=golden.task_id, passed=True, status="not-run", iterations=0,
        total_tokens=0, model="echo-1",
    )
    try:
        with tempfile.TemporaryDirectory() as td:
            trace = TraceLog(path=Path(td) / f"{golden.task_id}.jsonl")
            registry = ToolRegistry(policy=default_policy(), trace=trace)
            register_builtins(registry, include_exec=golden.include_exec, include_network=False)

            llm = ScriptedLLM(golden.script) if golden.script else EchoLLM()
            result.model = llm.model
            kernel = AgentKernel(
                llm,
                trace,
                tools=registry,
                budget=Budget(max_iterations=golden.max_iterations),
            )
            run = kernel.run(golden.task)

            result.status = run.status
            result.iterations = run.iterations
            result.total_tokens = int(run.usage.get("total_tokens", 0))

            started = {e.payload.get("tool") for e in trace.find(EventType.AGENT_TOOL_CALL_STARTED)}
            verdicts: dict[str, set[str]] = {}
            for e in trace.find(EventType.POLICY_DECISION):
                verdicts.setdefault(e.payload.get("tool"), set()).add(e.payload.get("verdict"))
            allows = {tool for tool, vs in verdicts.items() if "allow" in vs}

            _check(
                result, "status", run.status == golden.expect_status,
                f"got {run.status!r}, expected {golden.expect_status!r}",
            )
            _check(
                result, "iterations",
                golden.expect_min_iterations <= run.iterations <= golden.expect_max_iterations,
                f"got {run.iterations}, expected "
                f"[{golden.expect_min_iterations}, {golden.expect_max_iterations}]",
            )
            for tool in golden.expect_tools_used:
                _check(
                    result, f"tool_used:{tool}",
                    tool in started and tool in allows,
                    f"started={tool in started}, allowed={tool in allows}",
                )
            for tool in golden.expect_denials:
                refused = tool in started and tool not in allows
                _check(
                    result, f"refused:{tool}", refused,
                    f"attempted={tool in started}, verdicts={sorted(verdicts.get(tool, set()))}",
                )
            for needle in golden.expect_reply_contains:
                _check(
                    result, f"reply_contains:{needle[:24]!r}",
                    needle in run.reply.lower(),
                    f"reply: {run.reply[:90]!r}",
                )
            _check(
                result, "budget_stopped",
                (run.status in BUDGET_STOPPED_STATUSES) == golden.expect_budget_stopped,
                f"status={run.status!r}, expected_stop={golden.expect_budget_stopped}",
            )
    except Exception as exc:  # a crashing task is a failing task, not a crash
        result.passed = False
        result.error = f"{type(exc).__name__}: {exc}"
        _check(result, "harness_error", False, result.error)
    return result


# ------------------------------------------------------------------- suite


def run_suite(suite_dir: str | Path | None = None) -> dict[str, Any]:
    """Run every golden task; return a reproducible report dict."""
    tasks = load_suite(suite_dir)
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    results = [run_golden_task(task) for task in tasks]
    passed = sum(1 for r in results if r.passed)
    return {
        "suite": "golden_tasks",
        "kernel_version": openagentx.__version__,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "offline": True,
        "models": sorted({r.model for r in results}),
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tasks": [r.to_dict() for r in results],
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": round(passed / len(results), 4) if results else 0.0,
        },
    }


def render_text(report: dict[str, Any]) -> str:
    """Compact human view of a suite report (the JSON is the artifact)."""
    lines = [
        f"golden tasks — {report['summary']['passed']}/{report['summary']['total']} passed "
        f"(kernel v{report['kernel_version']}, offline={report['offline']})"
    ]
    for task in report["tasks"]:
        mark = "PASS" if task["passed"] else "FAIL"
        lines.append(f"  {mark}  {task['task_id']:24s} status={task['status']:16s} "
                     f"iters={task['iterations']} tokens={task['total_tokens']}")
        if not task["passed"]:
            for check in task["checks"]:
                if not check["passed"]:
                    lines.append(f"         x {check['check']}: {check['detail']}")
    summary = report["summary"]
    lines.append(f"pass_rate: {summary['pass_rate']:.0%}")
    return "\n".join(lines)


def save_report(report: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
