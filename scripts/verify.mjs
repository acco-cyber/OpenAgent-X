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
const drills = new Set(['loop', 'redact', 'trace', 'team', 'router', 'budget', 'stop']);
const runnerDrills = new Set(['loop', 'redact', 'trace', 'budget', 'stop']); // need script[]
const teamDrills = new Set(['team']);    // need lead_script[] + specialist_script[]
const routerDrills = new Set(['router']); // need fallback_script[]
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
    } catch (e) { console.error('INVALID JSON', f, e.message); fail++; }
  }
} else { console.error('MISSING golden_tasks/'); fail++; }

// 3) eval count only moves forward (honest growth)
if (nTasks < 5) { console.error(`GOLDEN TASKS REGRESSED: ${nTasks} < 5`); fail++; }

console.log(fail ? `verify: FAIL (${fail})` : `verify: OK (${nTasks} golden tasks, ${req.length} required files)`);
process.exit(fail ? 1 : 0);
