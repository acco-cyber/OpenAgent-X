#!/usr/bin/env node
/**
 * OpenAgent-X repository verifier.
 * Runs after every part (locally and in CI) before a part is considered done.
 *
 * Checks:
 *  1. Every file listed in scripts/required-files.txt exists and is non-trivial.
 *  2. Every .json file in the repo parses.
 *  3. Every agent definition (.yaml in agents/) declares the mandatory AgentDefinition fields.
 *  4. AGENTS.md contains the mandatory section anchors.
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const errors = [];
const warnings = [];

// ---------- 1. required files ----------
const reqPath = join(ROOT, 'scripts', 'required-files.txt');
if (!existsSync(reqPath)) {
  errors.push('scripts/required-files.txt is missing');
} else {
  const required = readFileSync(reqPath, 'utf8')
    .split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#'));
  for (const rel of required) {
    const p = join(ROOT, rel);
    if (!existsSync(p)) { errors.push(`missing required file: ${rel}`); continue; }
    const content = readFileSync(p, 'utf8');
    if (content.trim().length < 20) errors.push(`required file too small (suspect stub): ${rel}`);
  }
}

// ---------- 2. JSON validity ----------
function walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (entry === '.git' || entry === 'node_modules') continue;
    const p = join(dir, entry);
    const st = statSync(p);
    if (st.isDirectory()) walk(p);
    else if (entry.endsWith('.json')) {
      try { JSON.parse(readFileSync(p, 'utf8')); }
      catch (e) { errors.push(`invalid JSON: ${p.replace(ROOT + '/', '')}: ${e.message}`); }
    }
  }
}
walk(ROOT);

// ---------- 3. agent definition shape ----------
const AGENT_DIR = join(ROOT, 'agents');
if (existsSync(AGENT_DIR)) {
  const MANDATORY = ['agent_id', 'version', 'supported_task_types', 'required_capabilities',
    'allowed_tools', 'default_model_profile', 'max_budget', 'permission_ceiling', 'runtime_adapter'];
  for (const f of readdirSync(AGENT_DIR).filter((f) => f.endsWith('.yaml') || f.endsWith('.yml'))) {
    const text = readFileSync(join(AGENT_DIR, f), 'utf8');
    for (const field of MANDATORY) {
      if (!new RegExp(`^\\s*${field}:`, 'm').test(text)) errors.push(`agents/${f}: missing mandatory field '${field}'`);
    }
  }
}

// ---------- 4. AGENTS.md anchors ----------
const AGENTS = join(ROOT, 'AGENTS.md');
if (existsSync(AGENTS)) {
  const md = readFileSync(AGENTS, 'utf8');
  const anchors = ['Prime Directives', 'Task Lifecycle', 'Permission Model', 'Agent Workforce',
    'Model Gateway', 'Repository Map', 'Event', 'Memory'];
  for (const a of anchors) if (!md.includes(a)) errors.push(`AGENTS.md missing section: ${a}`);
} else {
  warnings.push('AGENTS.md not present yet');
}

// ---------- report ----------
if (warnings.length) { console.log('WARNINGS:'); warnings.forEach((w) => console.log('  !', w)); }
if (errors.length) {
  console.error('VERIFY FAILED:');
  errors.forEach((e) => console.error('  x', e));
  process.exit(1);
}
console.log('VERIFY OK — required files present, JSON valid, contracts consistent.');
