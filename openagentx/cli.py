"""X-CLI: ``oax`` — doctor, packs, validate, trace, replay, eval, run.

stdlib-only. Credentials are never printed; ``doctor`` reports only whether
environment variables are *set*.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import openagentx
from openagentx.trace import DEFAULT_TRACE_DIR, newest_trace


# ----------------------------------------------------------------- doctor


def cmd_doctor(_args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []

    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    checks.append(("python >= 3.10", sys.version_info >= (3, 10), f"found {version}"))
    checks.append(("openagentx imports", True, f"v{openagentx.__version__}"))

    for env_name, purpose in (
        ("OPENAGENTX_API_KEY", "online model calls (offline runs work without it)"),
        ("OPENAGENTX_BASE_URL", "custom OpenAI-compatible endpoint"),
        ("OPENAGENTX_MODEL", "model name for online runs"),
        ("OPENAGENTX_WORKSPACE", "workspace confinement root"),
    ):
        value = os.environ.get(env_name)
        state = "set" if value else "not set"
        checks.append((f"env {env_name}", True, f"{state} — {purpose}"))  # presence only, never values

    trace_dir = Path(os.environ.get("OPENAGENTX_TRACE_DIR", DEFAULT_TRACE_DIR))
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        checks.append(("trace dir writable", True, str(trace_dir)))
    except OSError as exc:
        checks.append(("trace dir writable", False, f"{trace_dir}: {exc}"))

    from openagentx.packs import PackLoader

    packs = PackLoader().catalog()
    checks.append(("packs discoverable", len(packs) > 0, f"{len(packs)} packs found"))

    from openagentx.llm import EchoLLM

    try:
        EchoLLM().complete([{"role": "user", "content": "ping"}])
        checks.append(("offline model (EchoLLM)", True, "deterministic replies, zero keys"))
    except Exception as exc:  # pragma: no cover - defensive
        checks.append(("offline model (EchoLLM)", False, str(exc)))

    failed = 0
    print("oax doctor")
    for name, ok, detail in checks:
        mark = "✓" if ok else "✗"
        if not ok:
            failed += 1
        print(f"  {mark} {name}: {detail}")
    print("doctor:", "PASS" if failed == 0 else f"{failed} check(s) failed")
    return 0 if failed == 0 else 1


# ------------------------------------------------------------------- packs


def cmd_packs(args: argparse.Namespace) -> int:
    from openagentx.packs import PackLoader

    loader = PackLoader()
    if args.show:
        pack = loader.get(args.show)
        if pack is None:
            print(f"no pack named {args.show!r}")
            return 1
        print(json.dumps(pack.to_dict(), indent=2))
        if pack.body:
            head = "\n".join(pack.body.splitlines()[:12])
            print(f"\n--- {pack.name}/PACK.md (head) ---\n{head}")
        return 0
    packs = loader.catalog()
    if not packs:
        print("no packs found (expected packs/*/pack.json)")
        return 1
    print(f"{len(packs)} packs:")
    for pack in packs:
        print(f"  {pack.name:14s} v{pack.version:8s} triggers: {', '.join(pack.triggers[:6])}…")
    return 0


# ---------------------------------------------------------------- validate


def cmd_validate(_args: argparse.Namespace) -> int:
    from openagentx.packs import PackLoader, PACK_MANIFEST

    errors: list[str] = []

    loader = PackLoader()
    pack_dirs = [d for d in Path("packs").iterdir() if d.is_dir()] if Path("packs").is_dir() else []
    for child in pack_dirs:
        manifest = child / PACK_MANIFEST
        if not manifest.is_file():
            errors.append(f"packs/{child.name}: missing {PACK_MANIFEST}")
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            for field in ("name", "version", "description", "triggers"):
                if not data.get(field):
                    errors.append(f"packs/{child.name}: manifest field {field!r} missing/empty")
        except json.JSONDecodeError as exc:
            errors.append(f"packs/{child.name}: invalid JSON ({exc})")
        if not (child / "PACK.md").is_file():
            errors.append(f"packs/{child.name}: missing PACK.md knowledge body")

    base = Path("prompts/base")
    for section_file in ("10-identity.md", "20-guardrails.md", "30-protocol.md", "40-output-contract.md"):
        if not (base / section_file).is_file():
            errors.append(f"prompts/base: missing {section_file}")

    if Path("openagent-x.manifest.json").is_file():
        try:
            json.loads(Path("openagent-x.manifest.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"openagent-x.manifest.json: invalid JSON ({exc})")

    if errors:
        print("VALIDATE FAILED:")
        for e in errors:
            print("  x", e)
        return 1
    print("VALIDATE OK — packs, prompts, and manifest are consistent.")
    return 0


# ------------------------------------------------------------------- trace


def cmd_trace(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else newest_trace()
    if not path or not path.exists():
        print("no trace file found (run `oax run --offline` first)")
        return 1
    from openagentx.events import iter_envelopes

    events = list(iter_envelopes(path.open("r", encoding="utf-8")))
    if args.summary:
        from openagentx.trace import TraceLog

        log = TraceLog(path=path)
        summary = log.summary(path)
        print(f"run {summary['run_id']} — {summary['events']} events")
        for event_type, count in summary["by_type"].items():
            print(f"  {count:3d} × {event_type}")
        return 0

    shown = 0
    for event in events:
        if args.type and event.event_type != args.type:
            continue
        actor = f"{event.actor.type}:{event.actor.id}"
        payload = json.dumps(event.payload, ensure_ascii=False)
        print(f"#{event.sequence:03d} {event.occurred_at} {event.event_type:28s} [{actor}] {payload[:160]}")
        shown += 1
        if args.limit and shown >= args.limit:
            break
    return 0


# ------------------------------------------------------------------ replay


def cmd_replay(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else newest_trace()
    if not path or not path.exists():
        print("no trace file found (run `oax run --offline` first)")
        return 1

    from openagentx.replay import load_timeline, render_text, replay_to_html

    timeline = load_timeline(path)
    print(render_text(timeline, limit=args.limit))

    if not args.text:
        out = replay_to_html(path, args.out)
        size = out.stat().st_size
        print(f"\nHTML timeline: {out} ({size:,} bytes, self-contained — open it in any browser)")
    return 0


# --------------------------------------------------------------------- eval


def cmd_eval(args: argparse.Namespace) -> int:
    from openagentx.evaluation import render_text, run_suite, save_report

    try:
        report = run_suite(args.suite)
    except (FileNotFoundError, ValueError) as exc:
        print(f"EVAL ERROR: {exc}")
        return 1
    print(render_text(report))

    stamp = time.strftime("%Y%m%d-%H%M%S")
    default_out = Path(".openagentx/reports") / f"eval-{stamp}.json"
    out = save_report(report, args.out or default_out)
    print(f"report: {out} (reproducible JSON — kernel version, model, config included)")
    summary = report["summary"]
    print("eval:", "PASS" if summary["failed"] == 0 else f"{summary['failed']} task(s) failed")
    return 0 if summary["failed"] == 0 else 1


# --------------------------------------------------------------------- run


def cmd_run(args: argparse.Namespace) -> int:
    from openagentx.budget import Budget
    from openagentx.llm import EchoLLM, OpenAICompatLLM
    from openagentx.loop import AgentKernel
    from openagentx.memory import MemoryStore
    from openagentx.packs import PackLoader
    from openagentx.policy import default_policy
    from openagentx.prompts import PromptCompiler, project_override_dirs
    from openagentx.tools import ToolRegistry
    from openagentx.builtins import register_builtins
    from openagentx.trace import TraceLog

    task = " ".join(args.task).strip()
    if not task:
        print("usage: oax run <task text> [--online]")
        return 2

    trace = TraceLog()
    policy = default_policy()
    registry = ToolRegistry(policy=policy, trace=trace)
    register_builtins(registry, include_exec=not args.no_exec, include_network=not args.no_network)

    activation = PackLoader().match(task)
    print(f"[packs] {activation.describe_activation()}")

    memory = MemoryStore()
    memory_block = memory.context_block(task, token_budget=256)
    compiler = PromptCompiler(override_dirs=[*activation.override_dirs(), *project_override_dirs()])
    system_prompt = compiler.compile(
        tools_section=registry.prompt_section(),
        memory_block=memory_block,
        token_budget=args.prompt_budget,
    )

    if args.online:
        llm = OpenAICompatLLM()  # reads OPENAGENTX_API_KEY / _BASE_URL / _MODEL
    else:
        llm = EchoLLM()

    kernel = AgentKernel(
        llm,
        trace,
        tools=registry,
        budget=Budget(max_iterations=args.max_iterations),
        system_prompt=system_prompt,
        memory_context=memory_block or None,
    )
    result = kernel.run(task)
    print(f"\nstatus: {result.status} | iterations: {result.iterations} | model: {result.model}")
    print(f"tokens: {result.usage['total_tokens']} | trace: {result.trace_file}")
    print(f"\nreply:\n{result.reply}")
    return 0 if result.ok else 1


# -------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oax", description="OpenAgent-X kernel CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="verify environment (offline-capable)").set_defaults(func=cmd_doctor)

    p_packs = sub.add_parser("packs", help="list/show knowledge packs")
    p_packs.add_argument("show", nargs="?", help="pack name to show in detail")
    p_packs.set_defaults(func=cmd_packs)

    sub.add_parser("validate", help="validate packs, prompts, and manifest").set_defaults(func=cmd_validate)

    p_trace = sub.add_parser("trace", help="inspect a run trace (newest by default)")
    p_trace.add_argument("path", nargs="?", help="trace .jsonl path")
    p_trace.add_argument("--type", dest="type", help="filter by event_type")
    p_trace.add_argument("--summary", action="store_true", help="counts per event type")
    p_trace.add_argument("--limit", type=int, default=50)
    p_trace.set_defaults(func=cmd_trace)

    p_replay = sub.add_parser("replay", help="render a run as a timeline (text + self-contained HTML)")
    p_replay.add_argument("path", nargs="?", help="trace .jsonl path (newest by default)")
    p_replay.add_argument("--out", help="HTML output path (default .openagentx/replays/<run>.html)")
    p_replay.add_argument("--text", action="store_true", help="print the terminal timeline only")
    p_replay.add_argument("--limit", type=int, default=40, help="rows shown in the terminal view")
    p_replay.set_defaults(func=cmd_replay)

    p_eval = sub.add_parser("eval", help="run the offline golden-task suite and write a report")
    p_eval.add_argument("--suite", help="golden task dir (default: ./golden_tasks or the repo copy)")
    p_eval.add_argument("--out", help="report path (default .openagentx/reports/eval-<ts>.json)")
    p_eval.set_defaults(func=cmd_eval)

    p_run = sub.add_parser("run", help="run the agent kernel on a task")
    p_run.add_argument("task", nargs="+", help="task text (quote it)")
    p_run.add_argument("--online", action="store_true", help="use OPENAGENTX_API_KEY model instead of EchoLLM")
    p_run.add_argument("--max-iterations", type=int, default=8)
    p_run.add_argument("--prompt-budget", type=int, default=1600, help="system prompt token budget")
    p_run.add_argument("--no-exec", action="store_true", help="exclude shell/python tools")
    p_run.add_argument("--no-network", action="store_true", help="exclude web_fetch")
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
