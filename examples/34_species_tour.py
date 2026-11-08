"""Offline example 34 — redaction species round three: eleven shapes, one table.

The redaction table is the boundary's grammar of danger: high-confidence
credential shapes become ``[REDACTED:<kind>]`` while everything else
passes untouched. Round three taught it six more species — Google
``AIza…`` API keys (exactly 35 chars of tail; the length itself is the
confidence), GitLab ``glpat-`` personal access tokens, Stripe
``sk_live_``/``sk_test_`` secret keys, ``npm_`` tokens, three-segment
JSON web tokens (the signature segment is required, so an ``alg=none``
header stays honest prose) and PEM private key blocks (RSA, OPENSSH and
PGP ``BLOCK`` variants) — and because ``oax audit``, the runner's
journal boundary, every re-redacting view and ``oax grep`` all walk the
same ``PATTERNS`` table, every surface hardened at once with zero new
code paths. This example walks the whole story the way golden task 45
grades it: each new shape planted at runtime by concatenation and
caught kind-by-kind, the near-misses left alone (a short tail, a JWT
missing its signature, a CERTIFICATE block — high-confidence, not a
spell-checker), the five legacy species still caught, a mixed line
reporting exactly three redactions, a planted temp tree found by the
audit kind-by-kind with the snippets themselves redacted, the
repository still auditing to 0 findings, and a journal carrying a raw
secret rendering through grep only in redacted form — byte-identically
twice.
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.audit import run_audit
from openagentx.events import Event
from openagentx.grep import grep_journal, render_grep
from openagentx.redact import PATTERNS, redact
from openagentx.tools import vault_value as vv


def main() -> int:
    steps: list = []
    wd = tempfile.mkdtemp(prefix="oax-species-demo-")

    def cli(*argv: str):
        return subprocess.run([sys.executable, "-m", "openagentx", *argv],
                              capture_output=True, text=True)

    # 1) the table knows eleven species
    kinds = [k for k, _rx in PATTERNS]
    steps.append(f"table: {len(kinds)} species — {' '.join(kinds)}")

    # 2) each new species caught kind-by-kind (runtime-assembled)
    new = [("google_api_key", vv("google")), ("gitlab_pat", vv("gitlab")),
           ("stripe_secret", vv("stripe")), ("npm_token", vv("npm")),
           ("jwt", vv("jwt")), ("private_key_block", vv("private_key"))]
    for kind, raw in new:
        out, n = redact("field=" + raw)
        assert n == 1 and raw not in out and f"[REDACTED:{kind}]" in out
        steps.append(f"caught {kind}: {len(raw)}-char value -> [REDACTED:{kind}]")

    # 3) near-misses stay invisible
    near = ["AIza" + "a" * 34, "glpat-" + "a" * 19, "sk_live_" + "a" * 15,
            "npm_" + "a" * 35, "eyJabcdefgh.ijklmnop.qr",
            "-----BEGIN CERTIFICATE-----"]
    near_ok = all(redact(s)[1] == 0 for s in near)
    steps.append(f"near-misses left alone: {sum(redact(s)[1] == 0 for s in near)}/{len(near)} -> {near_ok}")

    # 4) the five legacy species still caught
    legacy = [("github_token", vv("github")), ("aws_key", vv("aws")),
              ("slack_token", "xoxb-" + "ab12CD34ef56" + "-x"),
              ("anthropic_key", "sk-ant-" + "api03-longstring_value_123456"),
              ("openai_key", "sk-proj-" + "aVeryLongKeyString_1234567890")]
    hits = sum(1 for kind, raw in legacy
               if redact("v=" + raw) == (f"v=[REDACTED:{kind}]", 1))
    steps.append(f"legacy species still caught: {hits}/5")

    # 5) one line, three species, exactly three redactions
    mixed = ("ghp=" + vv("github") + " ai=" + vv("google") +
             " token=" + vv("jwt"))
    out, n = redact(mixed)
    steps.append(f"mixed line: {n} redactions, {out.count('[REDACTED:')} marks, raw gone: "
                 f"{not any(raw in out for _k, raw in new)}")

    # 6) the audit finds a planted tree kind-by-kind, snippets redacted
    planted = {}
    for i, (kind, raw) in enumerate(new):
        with open(os.path.join(wd, f"planted_{i}.py"), "w", encoding="utf-8") as fh:
            fh.write("N = 1\n" + f'key = "{raw}"\n')
        planted[f"planted_{i}.py"] = (kind, raw)
    findings = run_audit(wd)
    kinds_ok = all(any(f["file"] == name and f["kind"] == kind for f in findings)
                   for name, (kind, _raw) in planted.items())
    snippets_safe = all("[REDACTED:" in f["snippet"] and not any(
        raw in f["snippet"] for _k, raw in planted.values()) for f in findings)
    steps.append(f"audit: {len(findings)} findings, kinds matched: {kinds_ok}, "
                 f"snippets redacted: {snippets_safe}")

    # 7) the repository itself still audits to 0
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    repo = run_audit(repo_root)
    steps.append(f"repo self-audit: {len(repo)} findings (runtime concatenation is invisible)")

    # 8) a raw secret in a journal renders only redacted through grep
    raw = vv("google")
    jp = os.path.join(wd, "journal.jsonl")
    with open(jp, "w", encoding="utf-8") as fh:
        for i, (t, pay) in enumerate([
                ("run_start", {"run_id": "species"}),
                ("tool_result", {"tool": "write_file", "text": "cfg=" + raw})]):
            fh.write(Event(seq=i, run_id="species", ts=1000.0 + i,
                           type=t, payload=pay).to_json() + "\n")
    rep = grep_journal(jp, etype="tool_result")
    r1, r2 = render_grep(rep), render_grep(grep_journal(jp, etype="tool_result"))
    steps.append(f"grep: {rep['matched']}/{rep['total']} matched, {rep['redactions']} redaction, "
                 f"raw absent: {raw not in r1}, byte-identical: {r1 == r2}")

    # 9) the CLI agrees: grep exits 0 with redacted stdout, audit prints 0
    g = cli("grep", jp, "--type", "tool_result")
    a = cli("audit", ".")
    steps.append(f"CLI: grep exit {g.returncode} with "
                 f"{'[REDACTED:google_api_key]' in g.stdout and raw not in g.stdout}, "
                 f"audit exit {a.returncode} ('{a.stdout.strip()}')")

    for i, s in enumerate(steps, 1):
        print(f"  [{i:02d}] {s}")
    print("OK 34_species_tour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
