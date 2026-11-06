#!/usr/bin/env python3
"""X-Packs + X-Memory demo — knowledge activates on triggers, memory recalls.

    python examples/pack_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openagentx.memory import MemoryStore  # noqa: E402
from openagentx.packs import PackLoader  # noqa: E402


def main() -> None:
    loader = PackLoader()

    print("installed packs:")
    for pack in loader.catalog():
        print(f"  {pack.name:14s} — {pack.description[:70]}…")

    task = "Create a responsive React landing page, then analyze the signup dataset"
    activation = loader.match(task)
    print(f"\ntask: {task!r}")
    print("activated:", activation.describe_activation())
    head = "\n".join(activation.knowledge_block(max_chars=600).splitlines()[:8])
    print("\nknowledge head:\n" + head)

    with tempfile.TemporaryDirectory() as td:
        memory = MemoryStore(root=Path(td) / "mem", project_id="demo")
        memory.remember("The brand color is #1a1a2e and the product name is 'Nimbus'", tier="context", type="decision")
        memory.remember("Signup dataset lives at data/signups-2024.csv", tier="context", type="fact")
        verified = memory.remember("Landing page must pass WCAG AA contrast", tier="context", type="decision")
        memory.promote(verified.memory_id)

        print("\nmemory recall for this task (budgeted block):")
        print(memory.context_block(task, token_budget=120))


if __name__ == "__main__":
    main()
