#!/usr/bin/env node
// OpenAgent-X structural verification: required files + golden-task contracts.
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
let fail = 0;

// 1) every required file exists
const req = readFileSync(join(root, 'scripts/required-files.txt'), 'utf8')
  .split('\n').map(s => s.trim()).filter(Boolean);
for (const f of req) {
  if (!existsSync(join(root, f))) { console.error('MISSING', f); fail++; }
}

// 2) golden tasks are valid JSON with id + known drill
const drills = new Set(['loop', 'redact', 'trace', 'team', 'router', 'budget', 'stop',
                        'redact_nested', 'audit', 'pack', 'sbom', 'memory', 'compact',
                        'cache', 'hooks', 'fanout', 'structured', 'retry', 'breaker',
                        'planner', 'snapshot', 'prompt', 'jit', 'chaos', 'chain',
                        'diff', 'stats', 'bench', 'fuzz', 'property', 'pack2',
                        'graph', 'dashboard', 'mermaid', 'sweep', 'grep']);
const runnerDrills = new Set(['loop', 'redact', 'trace', 'budget', 'stop', 'redact_nested',
                              'cache', 'retry', 'breaker', 'jit', 'chaos', 'chain',
                              'diff', 'stats', 'sweep', 'grep']); // need script[]
const teamDrills = new Set(['team']);    // need lead_script[] + specialist_script[]
const routerDrills = new Set(['router']); // need fallback_script[]
const memoryDrills = new Set(['memory']); // need runs[] (each with script[]) + queries[]
const hooksDrills = new Set(['hooks']);   // need script[] + hooks.rules[]
const fanoutDrills = new Set(['fanout']); // need branches{}.script[] + coordinator_script[]
const structuredDrills = new Set(['structured']); // need script[] + cases[] + schema{}
const plannerDrills = new Set(['planner']); // need planner_script[] + step_scripts[][].script
const snapshotDrills = new Set(['snapshot']); // need script[] + expect.checkpoints[]
const promptDrills = new Set(['prompt']); // need layers{} + entry + expect.render
const gdir = join(root, 'golden_tasks');
let nTasks = 0;
if (existsSync(gdir)) {
  for (const f of readdirSync(gdir).filter(f => f.endsWith('.json')).sort()) {
    nTasks++;
    try {
      const t = JSON.parse(readFileSync(join(gdir, f), 'utf8'));
      if (!t.id || !t.drill) { console.error('BAD CONTRACT', f, '(needs id + drill)'); fail++; }
      else if (!drills.has(t.drill)) { console.error('UNKNOWN DRILL', f, t.drill); fail++; }
      else if (runnerDrills.has(t.drill) && (!Array.isArray(t.script) || t.script.length === 0)) {
        console.error('EMPTY SCRIPT', f); fail++;
      }
      else if (teamDrills.has(t.drill) && (!Array.isArray(t.lead_script) || !t.lead_script.length
                                           || !Array.isArray(t.specialist_script) || !t.specialist_script.length)) {
        console.error('EMPTY SCRIPT', f, '(team needs lead_script + specialist_script)'); fail++;
      }
      else if (routerDrills.has(t.drill) && (!Array.isArray(t.fallback_script) || !t.fallback_script.length)) {
        console.error('EMPTY SCRIPT', f, '(router needs fallback_script)'); fail++;
      }
      else if (memoryDrills.has(t.drill) && (!Array.isArray(t.runs) || !t.runs.length
                                           || !t.runs.every(r => Array.isArray(r.script) && r.script.length)
                                           || !Array.isArray(t.queries) || !t.queries.length)) {
        console.error('EMPTY SCRIPT', f, '(memory needs runs[].script + queries[])'); fail++;
      }
      else if (hooksDrills.has(t.drill) && (!Array.isArray(t.script) || !t.script.length
                                            || !t.hooks || !Array.isArray(t.hooks.rules) || !t.hooks.rules.length)) {
        console.error('EMPTY SCRIPT', f, '(hooks needs script[] + hooks.rules[])'); fail++;
      }
      else if (fanoutDrills.has(t.drill) && (!t.branches || !Object.keys(t.branches).length
                                             || !Object.values(t.branches).every(b => Array.isArray(b.script) && b.script.length)
                                             || !Array.isArray(t.coordinator_script) || !t.coordinator_script.length)) {
        console.error('EMPTY SCRIPT', f, '(fanout needs branches{}.script[] + coordinator_script[])'); fail++;
      }
      else if (structuredDrills.has(t.drill) && (!Array.isArray(t.script) || !t.script.length
                                                 || !Array.isArray(t.cases) || !t.cases.length
                                                 || !t.schema || typeof t.schema !== 'object')) {
        console.error('EMPTY SCRIPT', f, '(structured needs script[] + cases[] + schema{})'); fail++;
      }
      else if (plannerDrills.has(t.drill) && (!Array.isArray(t.planner_script) || t.planner_script.length < 2
                                              || !Array.isArray(t.step_scripts) || !t.step_scripts.length
                                              || !t.step_scripts.every(ss => Array.isArray(ss) && ss.length))) {
        console.error('EMPTY SCRIPT', f, '(planner needs planner_script[] + step_scripts[][])'); fail++;
      }
      else if (snapshotDrills.has(t.drill) && (!Array.isArray(t.script) || !t.script.length
                                               || !t.expect || !Array.isArray(t.expect.checkpoints) || !t.expect.checkpoints.length)) {
        console.error('EMPTY SCRIPT', f, '(snapshot needs script[] + expect.checkpoints[])'); fail++;
      }
      else if (promptDrills.has(t.drill) && (!t.layers || !Object.keys(t.layers).length
                                             || !t.entry || !t.expect || !t.expect.render)) {
        console.error('EMPTY SCRIPT', f, '(prompt needs layers{} + entry + expect.render)'); fail++;
      }
    } catch (e) { console.error('INVALID JSON', f, e.message); fail++; }
  }
} else { console.error('MISSING golden_tasks/'); fail++; }

// 3) eval count only moves forward (honest growth)
if (nTasks < 37) { console.error(`GOLDEN TASKS REGRESSED: ${nTasks} < 37`); fail++; }

// 4) docs stay in sync with the package (module guides + tutorial)
if (existsSync(join(root, 'docs/modules.md')) && existsSync(join(root, 'docs/tutorial.md'))) {
  const guides = readFileSync(join(root, 'docs/modules.md'), 'utf8');
  const tut = readFileSync(join(root, 'docs/tutorial.md'), 'utf8');
  const cliSrc = readFileSync(join(root, 'openagentx/cli.py'), 'utf8');
  for (const f of readdirSync(join(root, 'openagentx'))) {
    if (!f.endsWith('.py') || f === '__init__.py' || f === '__main__.py') continue;
    const base = f.slice(0, -3);
    if (!new RegExp(`\\b${base}\\b`).test(guides)) {
      console.error('DOCS MISSING module guide for', base); fail++;
    }
  }
  // the tutorial may only name real oax subcommands
  for (const m of tut.matchAll(/oax ([a-z0-9_]+)/g)) {
    if (!cliSrc.includes(`add_parser("${m[1]}"`)) {
      console.error('TUTORIAL names unknown subcommand oax', m[1]); fail++;
    }
  }
  // the tutorial may only reference real example files
  for (const m of tut.matchAll(/examples\/[0-9A-Za-z_]+\.py/g)) {
    if (!existsSync(join(root, m[0]))) {
      console.error('TUTORIAL names missing example', m[0]); fail++;
    }
  }
} else { console.error('MISSING docs/modules.md + docs/tutorial.md'); fail++; }

// 5) the ADR pack: every record structurally complete and indexed
const adrDir = join(root, 'docs/adr');
if (existsSync(adrDir)) {
  const recs = readdirSync(adrDir).filter(f => /^\d{4}-.*\.md$/.test(f)).sort();
  if (recs.length < 10) {
    console.error(`ADR PACK REGRESSED: ${recs.length} records < 10`); fail++;
  }
  const index = existsSync(join(adrDir, 'README.md'))
    ? readFileSync(join(adrDir, 'README.md'), 'utf8') : '';
  for (const f of recs) {
    const txt = readFileSync(join(adrDir, f), 'utf8');
    for (const sec of ['## Status', '## Context', '## Decision', '## Consequences']) {
      if (!txt.includes(sec)) { console.error('ADR INCOMPLETE', f, `(${sec})`); fail++; }
    }
    if (!index.includes(`(${f})`)) {
      console.error('ADR NOT INDEXED', f); fail++;
    }
  }
} else { console.error('MISSING docs/adr/'); fail++; }

// 6) the README cannot drift from the package it presents
const readmePath = join(root, 'README.md');
if (existsSync(readmePath)) {
  const rd = readFileSync(readmePath, 'utf8');
  const cliSrc = readFileSync(join(root, 'openagentx/cli.py'), 'utf8');
  // every `oax <sub>` in the README must be a real subcommand
  for (const m of rd.matchAll(/oax ([a-z0-9_]+)/g)) {
    if (!cliSrc.includes(`add_parser("${m[1]}"`)) {
      console.error('README names unknown subcommand oax', m[1]); fail++;
    }
  }
  // every example file the README references must exist
  for (const m of rd.matchAll(/examples\/[0-9A-Za-z_]+\.py/g)) {
    if (!existsSync(join(root, m[0]))) {
      console.error('README names missing example', m[0]); fail++;
    }
  }
  // every doc file the README references must exist
  for (const m of rd.matchAll(/docs\/[0-9A-Za-z_\-/]+\.md/g)) {
    if (!existsSync(join(root, m[0]))) {
      console.error('README names missing doc', m[0]); fail++;
    }
  }
  // eval-scale claims (badge + inline) must match the golden matrix
  for (const m of rd.matchAll(/eval-(\d+)_tasks/g)) {
    if (Number(m[1]) !== nTasks) {
      console.error(`README eval badge claims ${m[1]} tasks, golden matrix has ${nTasks}`); fail++;
    }
  }
  for (const m of rd.matchAll(/(\d+) tasks \/ \d+ checks/g)) {
    if (Number(m[1]) !== nTasks) {
      console.error(`README claims ${m[1]} tasks, golden matrix has ${nTasks}`); fail++;
    }
  }
} else { console.error('MISSING README.md'); fail++; }

// 7) CI runs the same gates the repo enforces locally — and installs nothing
const ciPath = join(root, '.github/workflows/ci.yml');
if (existsSync(ciPath)) {
  const ci = readFileSync(ciPath, 'utf8');
  for (const cmd of ['node scripts/verify.mjs',
                     'compileall -q openagentx examples',
                     '-m openagentx doctor',
                     '-m openagentx audit .',
                     '-m openagentx eval',
                     '-m openagentx examples']) {
    if (!ci.includes(cmd)) { console.error('CI MISSING gate:', cmd); fail++; }
  }
  if (/\bpip3?\s+install\b/.test(ci)) {
    console.error('CI INSTALLS PACKAGES (zero-dependency invariant)'); fail++;
  }
  if (/secrets\./.test(ci)) {
    console.error('CI CONSUMES SECRETS (offline CI needs none)'); fail++;
  }
  if (!ci.includes('"3.10"') && !ci.includes("'3.10'")) {
    console.error('CI does not test the 3.10 floor'); fail++;
  }
  // the README CI badge must point at a workflow that actually exists
  const rdci = readFileSync(join(root, 'README.md'), 'utf8');
  for (const m of rdci.matchAll(/actions\/workflows\/([A-Za-z0-9_.-]+)\/badge\.svg/g)) {
    if (!existsSync(join(root, '.github/workflows', m[1]))) {
      console.error('README badge names missing workflow', m[1]); fail++;
    }
  }
} else { console.error('MISSING .github/workflows/ci.yml'); fail++; }

console.log(fail ? `verify: FAIL (${fail})` : `verify: OK (${nTasks} golden tasks, ${req.length} required files)`);
process.exit(fail ? 1 : 0);
