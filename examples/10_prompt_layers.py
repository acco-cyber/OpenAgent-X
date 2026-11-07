"""Offline example 10 — prompt layers: one entry layer, ordered includes,
loud cycles, injection-safe substitution.

A four-layer prompt (guard → task → role → base) assembles in declared
order. A diamond include expands once per path. A cycle is reported with
its full path instead of looping, missing layers and variables name
themselves, and a variable value containing ``[[include ...]]`` stays
literal text — data can never add structure to the prompt.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openagentx.prompt import PromptLayers


def main() -> int:
    layers = {
        "base": "You are {{product}}, an offline agent runtime.",
        "role": "Plan carefully. [[include base]] Answer in {{language}}.",
        "task": "Task: {{task}}\n[[include role]]",
        "guard": "Never invent facts. [[include task]]",
        "extra": "[[include role]] [[include base]]",
    }
    p = PromptLayers(layers)

    out = p.render("guard", {"product": "OpenAgent-X",
                             "language": "English",
                             "task": "assemble the launch prompt"})
    print(f"render: {out!r}")
    assert out == ("Never invent facts. Task: assemble the launch prompt\n"
                   "Plan carefully. You are OpenAgent-X, an offline agent "
                   "runtime. Answer in English.")
    assert "[[include" not in out and "{{" not in out

    # diamond: 'extra' reaches base twice (once inside role, once directly)
    diamond = p.resolve("extra")
    n = diamond.count("offline agent runtime")
    print(f"diamond: base reached {n} times, deterministic across renders")
    assert n == 2
    assert p.resolve("extra") == diamond

    # failures are loud and name themselves
    for label, fn in [
        ("cycle a->b->a", lambda: PromptLayers(
            {"a": "x [[include b]]", "b": "y [[include a]]"}).resolve("a")),
        ("self include", lambda: PromptLayers(
            {"s": "me [[include s]]"}).resolve("s")),
        ("unknown layer", lambda: PromptLayers(layers).resolve("nope")),
        ("missing var", lambda: PromptLayers(
            {"x": "hi {{who}}"}).render("x")),
    ]:
        try:
            fn()
            raise AssertionError(f"{label} was not rejected")
        except ValueError as e:
            print(f"rejected {label}: {str(e)[:52]}")

    # injection safety: values are literal text, never re-scanned
    inj = p.render("guard", {"product": "[[include base]]",
                             "language": "English",
                             "task": "t"})
    assert inj.count("[[include base]]") == 1  # appears once, unexpanded
    print("injection: variable value stayed literal, structure unchanged")

    print("OK 10_prompt_layers (ordered includes, loud cycles,"
          " injection-safe substitution)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
