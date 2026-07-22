#!/usr/bin/env node
// humanize-guard: pre-push/pre-commit gate that keeps shipped prose human.
// Two checks on prose files (markdown, mdx, plain text) and any commit message:
//   1. Unicode dashes (em/en/horizontal-bar/minus/figure)  -> ERROR, always blocks.
//   2. AI-tell words/phrases                                -> WARN by default,
//      blocks in --gate mode (the mode the pre-push hook uses).
// Zero dependencies. Skips fenced ``` blocks and `inline code` so real command
// output is never flagged. Exit 1 on any blocking violation, else 0.
//
// Usage:
//   node humanize-guard.mjs [--gate] [--commit-msg <file>] [files...]
//   (no files given -> scans prose files changed vs the upstream/HEAD range)
'use strict';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
let commitMsgFile = null;
const explicit = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--gate') continue;
  if (args[i] === '--commit-msg') { commitMsgFile = args[++i]; continue; }
  explicit.push(args[i]);
}

const DASH = /[‒–—―−‐‑]/; // figure, en, em, horizontal bar, minus, hyphen, non-breaking hyphen
const PROSE = /\.(md|mdx|markdown|txt)$/i;

// Curated AI-tell lexicon. Tune per project via .humanize-allow (one term per line).
const AI_TELLS = [
  'delve', 'tapestry', 'in the realm of', 'realm of', "it's worth noting",
  'it is worth noting', "it's important to note", 'it is important to note',
  'boasts', 'seamless', 'seamlessly', 'robust', 'leverage', 'leverages',
  'leveraging', 'utilize', 'utilizes', 'utilizing', 'testament to',
  'underscores', 'underscoring', 'moreover', 'furthermore', 'in conclusion',
  'elevate', 'elevates', 'unlock', 'unlocks', 'harness the power',
  'game-changer', 'game changer', 'cutting-edge', 'ever-evolving',
  'ever-changing', 'embark', 'embarks', 'a myriad of', 'myriad', 'plethora',
  'paramount', 'pivotal', 'foster', 'fosters', 'navigating the',
  'in the ever-evolving', 'when it comes to', 'rich tapestry',
  'at the end of the day', 'needless to say', 'first and foremost',
  'meticulous', 'meticulously', 'crucial role', 'vibrant landscape',
];

let allow = new Set();
if (existsSync('.humanize-allow')) {
  for (const l of readFileSync('.humanize-allow', 'utf8').split('\n')) {
    const t = l.trim().toLowerCase();
    if (t && !t.startsWith('#')) allow.add(t);
  }
}
const tells = AI_TELLS.filter((t) => !allow.has(t.toLowerCase()));
const tellRe = new RegExp('\\b(' + tells.map((t) =>
  t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\b', 'i');

function stripCode(md) {
  // Blank out fenced blocks and inline code so command output is not flagged.
  return md.replace(/```[\s\S]*?```/g, (m) => m.replace(/[^\n]/g, ' '))
           .replace(/`[^`\n]*`/g, (m) => ' '.repeat(m.length));
}

function targetFiles() {
  if (explicit.length) return explicit.filter((f) => PROSE.test(f) && existsSync(f));
  const git = (a) => execFileSync('git', a, { stdio: ['ignore', 'pipe', 'ignore'] }).toString();
  const prose = (out) => out.split('\n').map((s) => s.trim())
    .filter((f) => f && PROSE.test(f) && existsSync(f) && statSync(f).isFile());
  let up = null;
  try { up = git(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']).trim(); } catch {}
  if (up) { // range is a single argv element, never a shell string
    try { return prose(git(['diff', '--name-only', '--diff-filter=ACM', up + '..HEAD'])); } catch {}
  }
  // First push or no upstream: scan all tracked prose so nothing slips through.
  try { return prose(git(['ls-files'])); } catch { return []; }
}

let dashHits = [], tellHits = [];
function scan(label, raw) {
  const text = label.endsWith('.txt') ? raw : stripCode(raw);
  text.split('\n').forEach((line, i) => {
    if (DASH.test(line)) dashHits.push(`${label}:${i + 1}: ${line.trim().slice(0, 100)}`);
    const m = line.match(tellRe);
    if (m) tellHits.push(`${label}:${i + 1}: "${m[1]}"  ->  ${line.trim().slice(0, 100)}`);
  });
}

for (const f of targetFiles()) { try { scan(f, readFileSync(f, 'utf8')); } catch {} }
if (commitMsgFile && existsSync(commitMsgFile)) {
  scan('COMMIT_MSG', readFileSync(commitMsgFile, 'utf8'));
}

const C = { red: '\x1b[31m', yel: '\x1b[33m', grn: '\x1b[32m', dim: '\x1b[2m', off: '\x1b[0m' };
if (dashHits.length) {
  console.log(`${C.red}humanize-guard: ${dashHits.length} unicode dash(es) (use , : ; or .):${C.off}`);
  dashHits.forEach((h) => console.log('  ' + h));
}
if (tellHits.length) {
  const tag = GATE ? `${C.red}BLOCK` : `${C.yel}warn`;
  console.log(`${tag}: ${tellHits.length} AI-tell phrase(s) (rewrite plain, or allowlist in .humanize-allow):${C.off}`);
  tellHits.forEach((h) => console.log('  ' + h));
}
const blocked = dashHits.length > 0 || (GATE && tellHits.length > 0);
if (blocked) {
  console.log(`${C.dim}Fix, or run the humanize command, or bypass once with HUMANIZE_SKIP=1.${C.off}`);
  process.exit(1);
}
if (!dashHits.length && !tellHits.length) console.log(`${C.grn}humanize-guard: clean.${C.off}`);
process.exit(0);
