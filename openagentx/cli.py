"""oax — the OpenAgent-X command line.

Subcommands: eval | doctor | audit | examples | trace | report | run | pack |
sbom | recall | compact | diff | stats | bench | fuzz | property | pack2 |
graph. Every subcommand is offline and stdlib-only; exit codes are contracts
(0 = green, 1 = anything else).
"""

from __future__ import annotations

import argparse
import json
import os
import runpy
import sys
import tempfile

from .audit import run_audit
from .doctor import run_doctor


def _cmd_eval(args) -> int:
    from .evaluation import run_eval

    reports, ok = run_eval(args.dir)
    for r in reports:
        print(f"{r.task_id:<28} {r.drill:<10} {r.passed}/{len(r.checks):<3} "
              f"{'OK' if r.ok else 'FAIL'}")
        if not r.ok:
            for c in r.checks:
                if not c.ok:
                    print(f"   FAIL {c.name}: {c.detail}")
    total = sum(len(r.checks) for r in reports)
    green = sum(r.passed for r in reports)
    print(f"eval: {len(reports)} tasks, {green}/{total} checks "
          f"{'green' if ok else 'FAILING'}")
    return 0 if ok else 1


def _cmd_doctor(args) -> int:
    checks = run_doctor(args.root)
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL':<5} {name:<22} {detail}")
    bad = [c for c in checks if not c[1]]
    print(f"doctor: {'OK' if not bad else 'FAIL'} ({len(checks) - len(bad)}/{len(checks)})")
    return 0 if not bad else 1


def _cmd_audit(args) -> int:
    findings = run_audit(args.root)
    for f in findings:
        print(f"LEAK {f['file']}:{f['line']} {f['kind']} :: {f['snippet']}")
    print(f"audit: {len(findings)} findings")
    return 0 if not findings else 1


def _cmd_examples(args) -> int:
    ex_dir = args.dir
    if not os.path.isdir(ex_dir):
        print(f"examples: no dir {ex_dir}")
        return 1
    fails = 0
    for name in sorted(os.listdir(ex_dir)):
        if not name.endswith(".py"):
            continue
        print(f"--- {name}")
        try:
            runpy.run_path(os.path.join(ex_dir, name), run_name="__main__")
        except SystemExit as e:
            if e.code not in (None, 0):
                fails += 1
                print(f"FAIL {name}: exit {e.code}")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"examples: {'OK' if fails == 0 else f'{fails} failed'}")
    return 0 if fails == 0 else 1


def _cmd_pack(args) -> int:
    """Deterministic manifest: build (+write) or honestly verify."""
    from .pack import build_manifest, manifest_json, verify_manifest

    if args.check:
        with open(args.check, encoding="utf-8") as fh:
            manifest = json.load(fh)
        ok, problems = verify_manifest(args.root, manifest)
        for p in problems:
            print(f"PACK {p}")
        print(f"pack: {'OK' if ok else 'FAIL'} ({args.check})")
        return 0 if ok else 1
    m = build_manifest(args.root)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(manifest_json(m))
        print(f"pack: wrote {args.out}")
    print(f"pack: {m['file_count']} files tree_sha256={m['tree_sha256']}")
    return 0


def _cmd_pack2(args) -> int:
    """Signed manifest v2: HMAC over the canonical bytes; verify both layers."""
    from .pack2 import sign_manifest, signed_json, verify_signed

    if args.check:
        with open(args.check, encoding="utf-8") as fh:
            manifest = json.load(fh)
        ok, problems = verify_signed(args.root, manifest, args.key)
        for p in problems:
            print(f"PACK2 {p}")
        print(f"pack2: {'OK' if ok else 'FAIL'} ({args.check})")
        return 0 if ok else 1
    m = sign_manifest(args.root, args.key)
    out = args.out or os.path.join(args.root, "pack.signed.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(signed_json(m))
    print(f"pack2: signed {m['file_count']} files "
          f"key_id={m['sig']['key_id']} -> {out}")
    return 0


def _cmd_sbom(args) -> int:
    """Stdlib BOM: purity is a computed verdict; exit 1 on any foreign import."""
    from .sbom import build_sbom, sbom_json

    s = build_sbom(args.root, args.pkg_dir)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(sbom_json(s))
        print(f"sbom: wrote {args.out}")
    print(f"sbom: {s['module_count']} modules package={s['package']} "
          f"stdlib_only={s['stdlib_only']} "
          f"network={','.join(s['network_modules']) or 'none'} "
          f"bom_sha256={s['bom_sha256']}")
    return 0 if s["stdlib_only"] else 1


def _cmd_trace(args) -> int:
    from .trace import text_timeline

    print(text_timeline(args.journal))
    return 0


def _cmd_report(args) -> int:
    from .trace import html_report

    out = args.out or (os.path.splitext(args.journal)[0] + ".html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html_report(args.journal, title=args.title))
    print(f"report: wrote {out}")
    return 0


def _cmd_run(args) -> int:
    """Run a single-line-JSON script file against builtin tools, offline."""
    from .events import sequence_dense
    from .llm import ScriptedLLM
    from .runner import AgentRunner
    from .trace import load_trace, text_timeline

    with open(args.script, encoding="utf-8") as fh:
        script = [line.strip() for line in fh if line.strip()]
    wd = args.workdir or tempfile.mkdtemp(prefix="oax-run-")
    os.makedirs(wd, exist_ok=True)
    jp = os.path.join(wd, "journal.jsonl")
    result = AgentRunner(ScriptedLLM(script), _tools_for(wd), jp,
                         max_steps=args.max_steps, workdir=wd,
                         run_id=args.run_id).run(args.task)
    events, _torn = load_trace(jp)
    if args.timeline:
        print(text_timeline(jp))
    dense = sequence_dense(events)
    print(f"run: stop={result.stop_reason} steps={result.steps} "
          f"events={result.events} dense={dense} journal={jp}")
    return 0 if result.stop_reason in ("reply", "stop_tool") and dense else 1


def _cmd_recall(args) -> int:
    """TF-IDF recall over past-run journals (read-only, deterministic)."""
    from .memory import MemoryLite

    mem = MemoryLite()
    indexed = mem.index_dir(args.dir)
    hits = mem.recall(args.query, k=args.k) if args.query else []
    for h in hits:
        print(f"HIT {h['run_id']:<16} score={h['score']:<10} {h['snippet'][:70]}")
    print(f"recall: {len(hits)} hit(s) over {indexed} indexed journal(s)")
    return 0


def _cmd_compact(args) -> int:
    """Fold a journal into a denser secondary journal; original untouched."""
    from .compact import compact_journal

    out = args.out or (os.path.splitext(args.journal)[0] + ".compact.jsonl")
    stats = compact_journal(args.journal, out)
    print(f"compact: {stats['src_events']} -> {stats['dst_events']} events "
          f"(tool_folds={stats['tool_folds']}, ratio={stats['ratio']})")
    print(f"compact: wrote {out}")
    return 0


def _cmd_diff(args) -> int:
    """Event-level journal diff; exit 0 = semantically same, 1 = different."""
    from .jdiff import diff_journals, render_diff

    try:
        d = diff_journals(args.a, args.b, strict=args.strict)
    except FileNotFoundError as e:
        print(f"diff: {e}")
        return 1
    print(render_diff(d))
    return 0 if d["same"] else 1


def _cmd_stats(args) -> int:
    """Deterministic run analytics for one journal."""
    from .stats import render_stats, run_stats

    if not os.path.exists(args.journal):
        print(f"stats: journal {args.journal} does not exist")
        return 1
    s = run_stats(args.journal)
    print(render_stats(s))
    return 0


def _cmd_bench(args) -> int:
    """Journal throughput microbench (wall-clock, reported not graded)."""
    from .bench import render_bench, run_bench

    b = run_bench(events=args.events)
    print(render_bench(b))
    return 0 if b["events"] == b["planned_events"] and b["dense"] else 1


def _cmd_fuzz(args) -> int:
    """Seeded fuzz over the journal contract; exit 0 iff zero violations."""
    from .fuzz import render_fuzz, run_fuzz_suite

    seeds = [int(s) for s in str(args.seeds).split(",") if s.strip()]
    reports = run_fuzz_suite(seeds=seeds, n_ops=args.ops)
    for r in reports:
        print(render_fuzz(r))
        for v in r["violations"]:
            print(f"   VIOLATION {v}")
    bad = sum(len(r["violations"]) for r in reports)
    print(f"fuzz: {'OK' if not bad else 'FAILING'} "
          f"({len(reports)} seed(s), {bad} violation(s))")
    return 0 if not bad else 1


def _cmd_property(args) -> int:
    """Property suite: invariants after every step; exit 0 iff zero violations."""
    from .property import render_property, run_property_suite

    seeds = [int(s) for s in str(args.seeds).split(",") if s.strip()]
    reports = run_property_suite(seeds=seeds, n_ops=args.ops)
    for r in reports:
        print(render_property(r))
        for v in r["violations"]:
            print(f"   VIOLATION {v}")
    bad = sum(len(r["violations"]) for r in reports)
    print(f"property: {'OK' if not bad else 'FAILING'} "
          f"({len(reports)} seed(s), {bad} violation(s))")
    return 0 if not bad else 1


def _tools_for(wd: str):
    from .tools import builtin_tools

    return builtin_tools(wd)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oax", description="OpenAgent-X control plane")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("eval", help="run every golden task drill")
    e.add_argument("dir", nargs="?", default="golden_tasks")
    e.set_defaults(fn=_cmd_eval)

    d = sub.add_parser("doctor", help="purity + integrity gate")
    d.add_argument("root", nargs="?", default=".")
    d.set_defaults(fn=_cmd_doctor)

    a = sub.add_parser("audit", help="secret-scan a tree")
    a.add_argument("root", nargs="?", default=".")
    a.set_defaults(fn=_cmd_audit)

    x = sub.add_parser("examples", help="execute all offline examples")
    x.add_argument("dir", nargs="?", default="examples")
    x.set_defaults(fn=_cmd_examples)

    t = sub.add_parser("trace", help="print a journal timeline")
    t.add_argument("journal")
    t.set_defaults(fn=_cmd_trace)

    r = sub.add_parser("report", help="render a self-contained HTML report")
    r.add_argument("journal")
    r.add_argument("--out", default="")
    r.add_argument("--title", default="OpenAgent-X trace")
    r.set_defaults(fn=_cmd_report)

    pk = sub.add_parser("pack", help="deterministic tree manifest (build/check)")
    pk.add_argument("root", nargs="?", default=".")
    pk.add_argument("--out", default="", help="write canonical manifest JSON here")
    pk.add_argument("--check", default="", help="verify ROOT against this manifest")
    pk.set_defaults(fn=_cmd_pack)

    pk2 = sub.add_parser("pack2",
                         help="signed tree manifest (HMAC-SHA256 sign/check)")
    pk2.add_argument("root", nargs="?", default=".")
    pk2.add_argument("--key", required=True,
                     help="signing/verifying key (kept out of the manifest)")
    pk2.add_argument("--out", default="", help="write the signed manifest here")
    pk2.add_argument("--check", default="",
                     help="verify ROOT against this signed manifest")
    pk2.set_defaults(fn=_cmd_pack2)

    sb = sub.add_parser("sbom", help="stdlib bill of materials (exit 1 if not pure)")
    sb.add_argument("root", nargs="?", default=".")
    sb.add_argument("--pkg-dir", default="", help="package dir (default: <root>/openagentx)")
    sb.add_argument("--out", default="", help="write canonical BOM JSON here")
    sb.set_defaults(fn=_cmd_sbom)

    rn = sub.add_parser("run", help="run a scripted agent turn-loop offline")
    rn.add_argument("script", help="file of single-line JSON turns")
    rn.add_argument("--task", default="oax run")
    rn.add_argument("--workdir", default="")
    rn.add_argument("--max-steps", type=int, default=8)
    rn.add_argument("--run-id", default="")
    rn.add_argument("--timeline", action="store_true")
    rn.set_defaults(fn=_cmd_run)

    rc = sub.add_parser("recall", help="TF-IDF recall over past-run journals")
    rc.add_argument("dir", help="directory containing *.jsonl journals")
    rc.add_argument("--query", required=True, help="natural-language query")
    rc.add_argument("--k", type=int, default=3, help="max hits (default 3)")
    rc.set_defaults(fn=_cmd_recall)

    cp = sub.add_parser("compact", help="fold a journal into a denser copy")
    cp.add_argument("journal")
    cp.add_argument("--out", default="", help="destination (default <stem>.compact.jsonl)")
    cp.set_defaults(fn=_cmd_compact)

    df = sub.add_parser("diff", help="event-level diff of two journals (exit 1 = different)")
    df.add_argument("a", help="first journal (.jsonl)")
    df.add_argument("b", help="second journal (.jsonl)")
    df.add_argument("--strict", action="store_true",
                    help="compare every field including ts (default ignores wall-clock)")
    df.set_defaults(fn=_cmd_diff)

    st = sub.add_parser("stats", help="deterministic run analytics for one journal")
    st.add_argument("journal")
    st.set_defaults(fn=_cmd_stats)

    bn = sub.add_parser("bench", help="journal throughput microbench (synthetic, timed)")
    bn.add_argument("--events", type=int, default=2000,
                    help="synthetic events to append (default 2000)")
    bn.set_defaults(fn=_cmd_bench)

    fz = sub.add_parser("fuzz", help="seeded fuzz over the journal contract")
    fz.add_argument("--seeds", default="0,1,2", help="comma-separated seeds")
    fz.add_argument("--ops", type=int, default=200,
                    help="events per seed (default 200)")
    fz.set_defaults(fn=_cmd_fuzz)

    pp = sub.add_parser("property",
                        help="property suite: invariants under random traces")
    pp.add_argument("--seeds", default="0,1,2", help="comma-separated seeds")
    pp.add_argument("--ops", type=int, default=120,
                    help="trace steps per seed (default 120)")
    pp.set_defaults(fn=_cmd_property)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)
