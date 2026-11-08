"""Offline example 33 — oax chain: tamper evidence from the CLI.

The hash chain makes journal edits *detectable and localizable*: each
chained line carries ``{"prev", "digest"}``, so editing any stored byte
of line *k* breaks the link at *k* — and now the operator surface
matches the guarantee. ``oax chain <journal>`` prints the deterministic
one-line verdict (exit 0 intact / 1 when the chain is broken, the tail
is torn or the path is missing) and ``oax chain <journal> --seal``
prints the 64-hex head of a fully intact chain-written journal, refusing
— with the reason named, never a traceback — anything it cannot verify.
This example walks the whole surface the way golden task 44 grades it:
a chain-written fixture (written by the module's own line writer over
fixed canonical events), the CLI's render byte-identical to the
module's, one edited payload byte, one deleted line and one reordered
pair each localized at the first mislinked index, a torn tail that is
an incomplete file (the intact prefix still reports ok but the CLI
exits 1 with the ``+torn_tail`` mark), every seal refusal named, a
plain journal verified honestly as plain, and a missing journal named —
never blessed.
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.chain import (GENESIS, ChainedJournal, chain_report, head_of,
                              seal, verify_journal)
from openagentx.events import Event, read_events


def main() -> int:
    steps: list = []
    wd = tempfile.mkdtemp(prefix="oax-chain-demo-")

    def cli(*argv: str):
        return subprocess.run([sys.executable, "-m", "openagentx", "chain",
                               *argv], capture_output=True, text=True)

    # 1) the fixture: chain-written by the module's own writer, fixed ts
    jp = os.path.join(wd, "journal.jsonl")
    cj = ChainedJournal(jp)
    cj.start_run("chain-cli")
    events = []
    for i, (t, pay) in enumerate([
            ("run_start", {"run_id": "chain-cli"}),
            ("step_start", {"step": 0}),
            ("tool_call", {"tool": "write_file"}),
            ("reply", {"text": "done"})]):
        ev = Event(seq=i, run_id="chain-cli", ts=1000.0 + i, type=t,
                   payload=pay)
        events.append(ev)
        with open(jp, "a", encoding="utf-8") as fh:
            fh.write(cj._line(ev) + "\n")
    r = verify_journal(jp)
    line0 = json.loads(open(jp, encoding="utf-8").read().splitlines()[0])
    assert r["ok"] and r["chained"] and r["n"] == 4
    assert r["head"] == head_of(read_events(jp)), "stored == recomputed"
    assert line0["chain"]["prev"] == GENESIS, "genesis is 64 zeros"
    steps.append(f"chain-written fixture verifies; head={r['head'][:16]}")

    # 2) the CLI agrees: byte-identical render, exit 0, == module render
    c0, c0b = cli(jp), cli(jp)
    assert c0.returncode == 0 and c0.stdout == c0b.stdout
    assert c0.stdout.strip() == chain_report(jp)
    steps.append(f"oax chain verify: {c0.stdout.strip()} (exit 0)")

    # 3) --seal prints exactly the module's 64-hex seal
    cs = cli(jp, "--seal")
    assert cs.returncode == 0 and cs.stdout.strip() == seal(jp) == r["head"]
    assert len(seal(jp)) == 64
    steps.append(f"oax chain --seal: {seal(jp)[:16]}… (exit 0, == module)")

    # 4) tampering is localized: edit, delete, reorder
    lines = open(jp, encoding="utf-8").read().splitlines()

    def variant(name, mutated):
        path = os.path.join(wd, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(mutated) + "\n")
        return path

    obj = json.loads(lines[1])
    obj["payload"]["step"] = 99
    lines[1] = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    ct = cli(variant("tampered.jsonl", lines))
    assert ct.returncode == 1 and "BROKEN at index 1" in ct.stdout
    steps.append(f"edited payload byte -> {ct.stdout.strip()} (exit 1)")

    orig = open(jp, encoding="utf-8").read().splitlines()
    del orig[1]
    cd = cli(variant("deleted.jsonl", orig))
    assert cd.returncode == 1 and "BROKEN" in cd.stdout
    steps.append(f"deleted line -> {cd.stdout.strip()} (exit 1)")

    orig = open(jp, encoding="utf-8").read().splitlines()
    orig[0], orig[1] = orig[1], orig[0]
    cr = cli(variant("reordered.jsonl", orig))
    assert cr.returncode == 1 and "BROKEN" in cr.stdout
    steps.append(f"reordered pair -> {cr.stdout.strip()} (exit 1)")

    # 5) a torn tail is an incomplete file: prefix ok, CLI still exit 1
    orig = open(jp, encoding="utf-8").read().splitlines()
    ctor = cli(variant("torn.jsonl", orig[:-1] + [orig[-1][:40]]))
    rtorn = verify_journal(os.path.join(wd, "torn.jsonl"))
    assert rtorn["torn_tail"] and rtorn["ok"], "the intact prefix verifies"
    assert ctor.returncode == 1 and "+torn_tail" in ctor.stdout
    steps.append(f"torn tail -> {ctor.stdout.strip()} (exit 1 — incomplete)")

    # 6) every seal refusal is a named one-line rejection
    plain = os.path.join(wd, "plain.jsonl")
    with open(plain, "w", encoding="utf-8") as fh:
        fh.write("\n".join(ev.to_json() for ev in events[:2]) + "\n")
    empty = os.path.join(wd, "empty.jsonl")
    open(empty, "w", encoding="utf-8").close()
    cp, ce, ctor2 = cli(plain, "--seal"), cli(empty, "--seal"), \
        cli(os.path.join(wd, "torn.jsonl"), "--seal")
    for c, why in ((cp, "not chain-written"), (ce, "empty; nothing to seal"),
                   (ctor2, "torn tail")):
        assert c.returncode == 1 and why in c.stdout
        assert "Traceback" not in c.stdout
    steps.append("seal refused for plain / empty / torn — reasons named")

    # 7) a plain journal verifies honestly as plain
    cpl = cli(plain)
    assert cpl.returncode == 0 and cpl.stdout.strip().endswith("plain")
    assert verify_journal(plain)["chained"] is False
    steps.append(f"plain journal -> {cpl.stdout.strip()} (exit 0, honest)")

    # 8) a missing journal is named, never blessed
    cmiss = cli(os.path.join(wd, "gone.jsonl"))
    assert cmiss.returncode == 1 and "no journal" in cmiss.stdout
    steps.append(f"missing path -> {cmiss.stdout.strip()} (exit 1)")

    print("chain CLI tour:")
    for i, s in enumerate(steps, 1):
        print(f"  [{i:02d}] {s}")
    print("OK 33_chain_cli_tour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
