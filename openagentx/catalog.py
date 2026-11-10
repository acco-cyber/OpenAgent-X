"""The specialist agent catalog — every kind of work, contract-backed.

The blueprint's workforce (§7) ships eight frozen profiles.  This module
scales the same discipline out to **every category of knowledge work**: a
curated catalog of 700+ specialist agent specs across 30+ work categories
(writing, coding, research, data, finance, legal, ops, ...), each carrying

* a one-line bounded mandate (the spec's whole job, stated honestly),
* the category's capability profile (tools drawn from the §11 tier table),
* the public agent lineage it adapts (grounded in a sweep of the public
  agent ecosystem — AutoGPT, BabyAGI, AutoGen, CrewAI, MetaGPT, Aider,
  SWE-agent, OpenHands, Adala, AgentVerse, CAMEL, ...), and
* a materialization path: ``to_definition(spec)`` builds a real
  :class:`openagentx.workforce.AgentDefinition`, so a catalog agent is a
  governed contract with a permission ceiling and an allowlist — never a
  sticker sheet.

Least privilege by construction: the default catalog ships **no P3/P4
tool** — external side effects and privileged operations stay outside
every spec's reach, and the shipped ceilings top out at P2 (sandboxed).

Composition: :func:`compose` turns one task into a bounded work order —
a planner, k category specialists, and an independent critic — with the
task text pushed through :mod:`openagentx.redact` *before* any prompt is
rendered.  Deterministic and offline: the catalog decides *who* works and
under what contract; it never executes work itself.

Purity: Python 3.10+ standard library only.

Doctests:

>>> from openagentx import catalog
>>> spec = catalog.get("blog_post_drafter")
>>> spec.category
'writing'
>>> d = catalog.to_definition(spec)
>>> d.permission_ceiling
'P1'
>>> wo = catalog.compose("write a launch email for the beta")
>>> wo["category"] in catalog.categories()
True
>>> [p["phase"] for p in wo["phases"]]
['plan', 'work', 'work', 'work', 'critique']
>>> from openagentx.tools import vault_value
>>> leaky = catalog.compose("ship it with " + vault_value("github"))
>>> any("[REDACTED:" in p["prompt"] for p in leaky["phases"])
True
"""

from __future__ import annotations

from dataclasses import dataclass

from . import redact, workforce
from .catalog_data import CATEGORIES

__all__ = [
    "AgentSpec", "CatalogError", "SPECS", "total", "categories", "get",
    "search", "to_definition", "compose", "check_catalog", "lineages",
    "detect",
]

#: workforce.AGENT_ID admits at most 31 chars — ids are built to fit.
_MAX_ID = 31

#: Honest floors the catalog pins about itself (checked in check_catalog,
#: the drill and the CLI).  Raised as the catalog grows.
CATALOG_FLOOR = 700
CATEGORY_FLOOR = 30

_PLANNER_ID = "requirement_interpreter"
_CRITIC_ID = "copy_editor"

_CEILING_POLICY = {
    "P0": ("citation_check",),
    "P1": ("evidence_consistency",),
    "P2": ("independent_evidence",),
}
_CEILING_BUDGET = {"P0": (25, 12000), "P1": (20, 16000), "P2": (30, 20000)}

#: Deterministic task->category hints.  First matching keyword wins;
#: unmatched tasks land in research (the broadest read-only charter).
_DETECT: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("coding", ("code", "refactor", "bug", "compile", "function", "script")),
    ("qa_testing", ("test", "flaky", "regression", "coverage")),
    ("devops", ("deploy", "pipeline", "docker", "k8s", "ci ", "rollout")),
    ("data", ("sql", "csv", "dataset", "metric", "spreadsheet")),
    ("legal", ("contract", "clause", "nda", "terms", "compliance")),
    ("finance", ("budget", "invoice", "cash", "runway", "pricing model")),
    ("security", ("vulnerab", "threat", "auth flow", "hardening")),
    ("marketing", ("campaign", "launch", "audience", "positioning")),
    ("writing", ("write", "draft", "blog", "copy", "newsletter", "email")),
)


class CatalogError(ValueError):
    """Raised when the catalog violates one of its own invariants."""


@dataclass(frozen=True)
class AgentSpec:
    """One catalog specialist: a bounded mandate plus its contract shape."""

    agent_id: str
    name: str
    category: str
    blurb: str
    charter: str
    tools: tuple[str, ...]
    ceiling: str
    task_types: tuple[str, ...]
    capabilities: tuple[str, ...]
    lineage: tuple[str, ...]


def _build() -> tuple[AgentSpec, ...]:
    """Materialize the frozen catalog deterministically from the data file."""
    out: list[AgentSpec] = []
    seen: set[str] = set()
    for cat in sorted(CATEGORIES):
        c = CATEGORIES[cat]
        for slug, name, blurb in c["roles"]:
            agent_id = slug
            if not workforce.AGENT_ID.match(agent_id) or len(agent_id) > _MAX_ID:
                raise CatalogError(f"agent_id {agent_id!r} violates the id contract")
            if agent_id in seen:
                raise CatalogError(f"duplicate agent_id {agent_id!r}")
            seen.add(agent_id)
            for t in c["tools"]:
                if t not in workforce.TOOL_TIERS:
                    raise CatalogError(f"{agent_id}: tool {t!r} is outside the tier table")
                if workforce.TIERS[workforce.TOOL_TIERS[t]] > workforce.TIERS[c["ceiling"]]:
                    raise CatalogError(
                        f"{agent_id}: tool {t!r} needs {workforce.TOOL_TIERS[t]} "
                        f"but the ceiling is {c['ceiling']}")
            if c["ceiling"] not in ("P0", "P1", "P2"):
                raise CatalogError(
                    f"{agent_id}: catalog ships P0..P2 only (got {c['ceiling']})")
            out.append(AgentSpec(
                agent_id=agent_id, name=name, category=cat, blurb=blurb,
                charter=c["charter"], tools=tuple(c["tools"]),
                ceiling=c["ceiling"], task_types=tuple(c["task_types"]),
                capabilities=tuple(c["capabilities"]),
                lineage=tuple(c["lineage"])))
    return tuple(out)


_SPECS: tuple[AgentSpec, ...] | None = None


def SPECS() -> tuple[AgentSpec, ...]:
    """The full frozen catalog, in deterministic (category, id) order."""
    global _SPECS
    if _SPECS is None:
        _SPECS = _build()
    return _SPECS


def total() -> int:
    """Number of specialists in the catalog.

    >>> from openagentx import catalog
    >>> catalog.total() >= catalog.CATALOG_FLOOR
    True
    """
    return len(SPECS())


def categories() -> tuple[str, ...]:
    """Sorted category names.

    >>> from openagentx import catalog
    >>> len(catalog.categories()) >= catalog.CATEGORY_FLOOR
    True
    """
    return tuple(sorted(CATEGORIES))


def get(agent_id: str) -> AgentSpec:
    """Return one spec by id; unknown ids raise :class:`CatalogError`."""
    for s in SPECS():
        if s.agent_id == agent_id:
            return s
    raise CatalogError(f"no catalog agent {agent_id!r}")


def search(query: str, category: str | None = None,
           k: int = 8) -> tuple[AgentSpec, ...]:
    """Deterministic keyword search over name/blurb/category/charter.

    Scoring is token overlap; ties break by agent_id so the same query
    always returns the same roster.
    """
    tokens = [t for t in "".join(ch if ch.isalnum() else " " for ch in
                                 query.lower()).split() if len(t) > 2]
    scored: list[tuple[int, str, AgentSpec]] = []
    for s in SPECS():
        if category is not None and s.category != category:
            continue
        hay = " ".join((s.agent_id, s.name, s.blurb, s.category, s.charter))
        hl = "".join(ch if ch.isalnum() else " " for ch in hay.lower()).split()
        score = sum(1 for w in hl if any(w.startswith(t) for t in tokens))
        if score > 0:
            scored.append((-score, s.agent_id, s))
    scored.sort()
    return tuple(s for _, _, s in scored[:max(1, k)])


def to_definition(spec: AgentSpec) -> workforce.AgentDefinition:
    """Materialize a spec as a governed §7 contract.

    >>> from openagentx import catalog
    >>> d = catalog.to_definition(catalog.get("blog_post_drafter"))
    >>> d.agent_id, d.version, d.allowed_tools[0]
    ('blog_post_drafter', '1.0.0', 'search')
    """
    calls, tokens = _CEILING_BUDGET[spec.ceiling]
    return workforce.AgentDefinition(
        agent_id=spec.agent_id, version="1.0.0",
        supported_task_types=spec.task_types,
        required_capabilities=spec.capabilities,
        allowed_tools=spec.tools, permission_ceiling=spec.ceiling,
        max_tool_calls=calls, max_tokens=tokens,
        verification_policy=_CEILING_POLICY[spec.ceiling],
        runtime_adapter="builtin")


def detect(task: str) -> str:
    """Route a task string to its best-guess category (deterministic)."""
    low = task.lower()
    for cat, keywords in _DETECT:
        if any(k in low for k in keywords):
            return cat
    return "research"


def _prompt(spec: AgentSpec, task: str) -> str:
    lineage = spec.lineage[0] if spec.lineage else "public agent lineage"
    return (f"[{spec.name} — {spec.category} specialist]\n"
            f"Charter: {spec.charter}\n"
            f"Role: {spec.blurb}\n"
            f"Lineage: {lineage}\n"
            f"Task: {task}\n"
            f"Deliver your bounded portion; cite evidence; stay within "
            f"tools {', '.join(spec.tools)} under ceiling {spec.ceiling}.")


def compose(task: str, category: str | None = None, k: int = 3) -> dict:
    """Turn one task into a bounded work order over the catalog.

    The task is redacted *before* any prompt is rendered; the roster is a
    planner, ``k`` specialists from the matching category, and an
    independent critic.  Returns a deterministic dict of phases, events
    and the materialized workforce contracts.
    """
    clean, n = redact.redact(str(task))
    cat = category if category in CATEGORIES else detect(clean)
    if cat not in CATEGORIES:
        raise CatalogError(f"unknown category {cat!r}")
    events = [f"catalog:task_redacted:{n}"] if n else ["catalog:task_clean"]
    events.append(f"catalog:category:{cat}")
    roster: list[tuple[str, AgentSpec]] = [("plan", get(_PLANNER_ID))]
    picks = search(clean, category=cat, k=max(1, k))
    if not picks:
        picks = SPECS()[:1]
    for s in picks:
        roster.append(("work", s))
    roster.append(("critique", get(_CRITIC_ID)))
    phases = [{"phase": phase, "agent": s.agent_id, "name": s.name,
               "category": s.category, "prompt": _prompt(s, clean)}
              for phase, s in roster]
    events.append(f"catalog:roster:1+{len(picks)}+1")
    return {
        "task": clean,
        "category": cat,
        "phases": phases,
        "events": events,
        "contracts": {s.agent_id: to_definition(s)
                      for _, s in roster},
    }


def lineages() -> tuple[str, ...]:
    """The public agent families the catalog adapts, sorted and unique."""
    out: set[str] = set()
    for c in CATEGORIES.values():
        out.update(c["lineage"])
    return tuple(sorted(out))


def check_catalog() -> dict:
    """Re-verify every catalog invariant; return honest summary counts.

    Raises :class:`CatalogError` on the first violated invariant; a clean
    pass returns the totals the drill and the CLI report.
    """
    specs = SPECS()
    ids = [s.agent_id for s in specs]
    if len(ids) != len(set(ids)):
        raise CatalogError("duplicate agent_id in catalog")
    if total() < CATALOG_FLOOR:
        raise CatalogError(
            f"catalog holds {total()} agents — the floor is {CATALOG_FLOOR}")
    if len(categories()) < CATEGORY_FLOOR:
        raise CatalogError(
            f"catalog holds {len(categories())} categories — "
            f"floor is {CATEGORY_FLOOR}")
    defs = [to_definition(s) for s in specs]
    for spec, d in zip(specs, defs):
        if d.agent_id != spec.agent_id:
            raise CatalogError("definition mismatch")
        for t in d.allowed_tools:
            decision = workforce.check_permission(d, t)
            if not decision.allowed:
                raise CatalogError(
                    f"{spec.agent_id}: allowlisted tool {t!r} failed its own gate")
    return {"agents": total(), "categories": len(categories()),
            "contracts": len(defs), "lineages": len(lineages())}
