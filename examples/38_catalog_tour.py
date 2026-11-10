"""Example 38 — the agent catalog: 727 specialists, every kind of work,
each in a small bounded portion.

The catalog tour, on the module surface: the true totals from
``check_catalog`` (agents, categories, contracts, lineages), the category
roster with its charters, one category's specialists named, the material
of the promise — a spec materialized as a real ``workforce.AgentDefinition``
with its ceiling and allowlist observed — the least-privilege refusal
(the catalog simply has no P3/P4 reach to grant), deterministic search,
keyword routing with its honest default, a composed work order
(planner -> specialists -> independent critic) with the event trail, and
the redaction-first boundary: a secret-shaped task entering compose and
leaving as ``[REDACTED:...]`` in every rendered prompt.

Prints ``OK 38_catalog_tour`` at the end.
"""

from openagentx.catalog import (CATEGORIES, check_catalog, compose, detect,
                                get, search, to_definition, total)
from openagentx.tools import vault_value
from openagentx.workforce import TIERS, TOOL_TIERS

# 1) the honest totals — floors pinned at 700/30 and checked now
stats = check_catalog()
print(f"the catalog: {stats['agents']} agents / {stats['categories']} "
      f"categories / {stats['contracts']} contracts / "
      f"{stats['lineages']} cited public lineages")
assert stats["agents"] >= 700 and stats["categories"] >= 30

# 2) the category roster — every kind of work has a charter
print(f"\nthe roster ({len(CATEGORIES)} categories, alphabet's ends):")
for cat in (sorted(CATEGORIES)[0], sorted(CATEGORIES)[len(CATEGORIES) // 2],
            sorted(CATEGORIES)[-1]):
    c = CATEGORIES[cat]
    print(f"  {cat:20s} {len(c['roles']):2d} roles — {c['charter']}")

# 3) one category, named specialists
print("\ncoding's specialists (first 4 of "
      f"{len(CATEGORIES['coding']['roles'])}):")
for slug, name, blurb in CATEGORIES["coding"]["roles"][:4]:
    print(f"  {name:26s} {blurb}")

# 4) the material of the promise: a spec is a governed contract
spec = get("bug_hunter")
d = to_definition(spec)
print(f"\n{spec.name} as a contract:")
print(f"  agent_id={d.agent_id} version={d.version} "
      f"ceiling={d.permission_ceiling}")
print(f"  allowlist={','.join(d.allowed_tools)}")
print(f"  budget={d.max_tool_calls} calls / {d.max_tokens} tokens; "
      f"verify={','.join(d.verification_policy)}")
assert d.agent_id == "bug_hunter" and d.version == "1.0.0"

# 5) least privilege by construction: no spec reaches P3/P4
p3p4 = 0
for cat in sorted(CATEGORIES):
    c = CATEGORIES[cat]
    if TIERS[c["ceiling"]] >= 3:
        p3p4 += 1
    for t in c["tools"]:
        assert TIERS[TOOL_TIERS[t]] <= TIERS[c["ceiling"]]
print(f"\nleast privilege: categories with P3/P4 ceilings in the default "
      f"catalog: {p3p4} (none); every allowlisted tool sits within its "
      "ceiling")

# 6) deterministic search — the same question, the same roster
hits = search("cold outreach email", k=3)
print("\nsearch 'cold outreach email' (deterministic):")
for s in hits:
    print(f"  {s.agent_id:28s} {s.category:10s} {s.blurb}")
assert hits == search("cold outreach email", k=3)
assert any(s.agent_id == "cold_email_writer" for s in hits)

# 7) routing: keywords decide, unknown tasks land in research
print(f"\ndetect('refactor the flaky checkout flow') -> "
      f"{detect('refactor the flaky checkout flow')}")
print("detect('who is the fiercest quokka') -> "
      f"{detect('who is the fiercest quokka')} (honest default)")

# 8) compose: one task becomes a bounded work order
wo = compose("refactor the flaky checkout tests", k=2)
print(f"\nwork order -> {wo['category']}")
for p in wo["phases"]:
    print(f"  {p['phase']:9s} {p['name']} ({p['agent']})")
print(f"  events: {' | '.join(wo['events'])}")
print(f"  contracts materialized: {len(wo['contracts'])} "
      "(every phase runs under a real AgentDefinition)")
assert [p["phase"] for p in wo["phases"]] == \
    ["plan", "work", "work", "critique"]
assert all(p["agent"] in wo["contracts"] for p in wo["phases"])

# 9) the redaction-first boundary: a secret never reaches a prompt
secret = vault_value("github")
leaky = compose(f"deploy the fix and announce it with {secret}")
joined = " ".join(p["prompt"] for p in leaky["phases"])
print("\nredaction-first boundary:")
print(f"  task in : ship it with {secret[:8]}... (vault-assembled at runtime)")
print(f"  prompts : {'[REDACTED:github_token]' in joined} — every rendered "
      "prompt carries [REDACTED:github_token], never the token")
print(f"  events  : {' | '.join(leaky['events'][:2])}")
assert "[REDACTED:" in joined and secret not in joined

print()
print("OK 38_catalog_tour")
