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
                        'diff', 'stats', 'bench', 'fuzz']);
const runnerDrills = new Set(['loop', 'redact', 'trace', 'budget', 'stop', 'redact_nested',
                              'cache', 'retry', 'breaker', 'jit', 'chaos', 'chain',
                              'diff', 'stats']); // need script[]
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
if (nTasks < 27) { console.error(`GOLDEN TASKS REGRESSED: ${nTasks} < 27`); fail++; }

console.log(fail ? `verify: FAIL (${fail})` : `verify: OK (${nTasks} golden tasks, ${req.length} required files)`);
process.exit(fail ? 1 : 0);
