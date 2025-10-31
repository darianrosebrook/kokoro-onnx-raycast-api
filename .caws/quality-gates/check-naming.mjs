#!/usr/bin/env node

/**
 * Quality Gate: Naming Conventions (Rust-focused, Git-correct, regression-aware)
 *
 * @author: @darianrosebrook
 * @date: 2025-10-28
 * @version: 1.0.0
 * @license: MIT
 * @copyright: 2025 Darian Rosebrook
 * @description: Detects naming violations and blocks commits that would create or worsen them.
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import yaml from 'js-yaml';
import micromatch from 'micromatch';
import os from 'os';
import path from 'path';
import { getFilesToCheck } from './file-scope-manager.mjs';
import {
  getEnforcementLevel as getGlobalEnforcementLevel,
  processViolations,
} from './shared-exception-framework.mjs';

/* ----------------------- config ----------------------- */

const DEFAULT_BANNED_MODIFIERS = [
  'enhanced',
  'unified',
  'simplified',
  'better',
  'new',
  'next',
  'final',
  'copy',
  'revamp',
  'improved',
  'alt',
  'tmp',
  'scratch',
];

const DEFAULT_EXTS = [
  '.rs',
  '.ts',
  '.tsx',
  '.js',
  '.jsx',
  '.mjs',
  '.cjs',
  '.mts',
  '.cts',
  '.swift',
  '.go',
  '.java',
  '.kt',
];

const CONVENTION_FILES = new Set([
  'lib.rs',
  'mod.rs',
  'main.rs',
  'Cargo.toml',
  'index.ts',
  'index.js',
]);

const NAMING_EXC_JSON = '.caws/naming-exceptions.json';
const CANONICAL_MAP_YAML = '.caws/canonical-map.yaml';

const DEFAULT_POLICY = {
  bannedModifiers: DEFAULT_BANNED_MODIFIERS,
  extensions: DEFAULT_EXTS,
  // Words that often appear as legitimate domain terms; don’t treat them as modifiers
  falsePositives: ['nextjs', 'finalize', 'copywriter', 'unify', 'unification'],
  // Allow “v2”, “v3”, “v10” and date stamps to be normalized out
  versionPattern: /(?:^|[-_.])v?\d{1,3}(?:$|[-_.])/gi,
  datestampPattern: /\b(20\d{2}[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01]))\b/g,
  // “Canonical” comment pragma at top of file (first 50 lines)
  canonicalPragma: /CAWS:\s*canonical-of\s+(.+)/i,
  // Default enforcement
  enforcement: { commit: 'warning', push: 'block', ci: 'fail' },
  // Clusters larger than this are always investigated
  clusterWarnSize: 2,
};

function normalizePath(p) {
  // Normalize paths for cross-platform compatibility
  return os.platform() === 'win32' ? p.replace(/\\/g, '/') : p;
}

function repoRoot() {
  try {
    return execFileSync('git', ['rev-parse', '--show-toplevel'], {
      encoding: 'utf8',
    }).trim();
  } catch (error) {
    throw new Error(
      `Not a git repository or git command failed: ${error.message}. Run from within a git repository.`
    );
  }
}

function loadJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}
function loadYaml(p) {
  if (!fs.existsSync(p)) return null;
  return yaml.load(fs.readFileSync(p, 'utf8')) || null;
}

function loadNamingPolicy(root) {
  const exc = loadJson(path.join(root, NAMING_EXC_JSON)) || {
    exceptions: [],
    enforcement_levels: DEFAULT_POLICY.enforcement,
  };
  const canonicalMap = loadYaml(path.join(root, CANONICAL_MAP_YAML)) || {
    canonicals: {}, // normalizedStem -> repo-relative canonical path
    overrides: [], // { pattern, canonical }
  };
  return { policy: DEFAULT_POLICY, exceptions: exc, canonicalMap };
}

function nowIso() {
  return new Date().toISOString();
}

/* ----------------------- git helpers ----------------------- */

function readStagedText(root, relPath) {
  try {
    return execFileSync('git', ['show', `:${relPath}`], {
      cwd: root,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
    });
  } catch {
    return null;
  }
}

/* ----------------------- normalization ----------------------- */

function stemOf(filePath) {
  const base = path.basename(filePath, path.extname(filePath));
  return base;
}

function normalizeStem(raw, policy) {
  // lower, split on separators, drop banned words, version/date tokens, empty parts
  const lower = raw.toLowerCase();
  if (policy.falsePositives.some((w) => lower.includes(w))) {
    // let it pass normalization but don’t ban purely for containing that substring
  }
  const stripped = lower
    .replace(policy.versionPattern, '.')
    .replace(policy.datestampPattern, '.')
    .replace(/[-_.]+/g, '.'); // normalize separators

  const parts = stripped.split('.').filter(Boolean);
  const bannedSet = new Set(policy.bannedModifiers);
  const keep = [];
  for (const p of parts) {
    if (bannedSet.has(p)) continue;
    if (p.length === 1 && /\d/.test(p)) continue;
    keep.push(p);
  }
  return keep.join('.');
}

function crateRootOf(absPath, root) {
  // Walk up to find Cargo.toml (crate boundary) or package.json (for TS)
  let cur = path.dirname(absPath);
  while (cur.startsWith(root)) {
    if (fs.existsSync(path.join(cur, 'Cargo.toml'))) return cur;
    if (fs.existsSync(path.join(cur, 'package.json'))) return cur;
    const parent = path.dirname(cur);
    if (parent === cur) break;
    cur = parent;
  }
  return path.dirname(absPath);
}

/* ----------------------- exception & enforcement ----------------------- */

function getEnforcementLevel(context) {
  const { exceptions } = loadNamingPolicy(repoRoot());
  const levels = exceptions.enforcement_levels || DEFAULT_POLICY.enforcement;
  const ctx = context || process.env.CAWS_ENFORCEMENT_CONTEXT || 'commit';
  return levels[ctx] || 'warning';
}

function matchException(fileRel, modifier, exceptionsConf) {
  const now = new Date();
  for (const ex of exceptionsConf.exceptions || []) {
    const pat = ex.file_pattern;
    const isMatch = micromatch.isMatch(fileRel, pat, { dot: true });
    if (!isMatch) continue;
    if (ex.modifier && modifier && ex.modifier.toLowerCase() !== modifier.toLowerCase()) continue;
    if (ex.expires_at && new Date(ex.expires_at) < now)
      return { valid: false, expired: true, entry: ex };
    return { valid: true, entry: ex };
  }
  return { valid: false };
}

/* ----------------------- file discovery ----------------------- */

function filteredFilesByScope(context, policy, exts) {
  const root = repoRoot();
  const abs = getFilesToCheck(context);
  return abs
    .filter((p) => exts.some((e) => p.endsWith(e)))
    .filter((p) => !CONVENTION_FILES.has(path.basename(p)))
    .map((p) => ({ abs: p, rel: path.relative(root, p) }));
}

/* ----------------------- canonical resolution ----------------------- */

function canonicalOf(relPath, policy, canonicalMap, stagedText) {
  // 1) explicit comment pragma in file
  if (stagedText) {
    const head = stagedText.split(/\r?\n/).slice(0, 50).join('\n');
    const m = head.match(policy.canonicalPragma);
    if (m) return m[1].trim();
  }
  // 2) map override by pattern
  for (const ov of canonicalMap.overrides || []) {
    if (micromatch.isMatch(relPath, ov.pattern, { dot: true })) return ov.canonical;
  }
  // 3) otherwise: none declared
  return null;
}

/* ----------------------- cluster analysis ----------------------- */

function groupByNormalizedStem(files, policy, root) {
  const clusters = new Map(); // key: crateRoot + '|' + normStem -> { key, normStem, crateRoot, members[] }
  for (const f of files) {
    const crate = crateRootOf(f.abs, root);
    const stem = stemOf(f.rel);
    const norm = normalizeStem(stem, policy);
    const key = crate + '|' + norm;
    if (!clusters.has(key))
      clusters.set(key, { key, crateRoot: crate, normStem: norm, members: [] });
    clusters.get(key).members.push(f);
  }
  return [...clusters.values()];
}

/* ----------------------- symbol heuristic ----------------------- */

function symbolHeuristics(rel, stagedText, policy) {
  // look for banned modifiers embedded in exported or public symbol names
  if (!stagedText) return [];
  const banned = new RegExp(`\\b(${policy.bannedModifiers.join('|')})\\b`, 'i');
  const out = [];
  const lines = stagedText.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    if (
      /\b(export\s+(class|function|const|type|interface)|pub\s+(struct|enum|trait|mod|fn|impl))\b/.test(
        L
      )
    ) {
      if (banned.test(L)) {
        const m = L.match(banned);
        out.push({
          type: 'symbol_banned_modifier',
          file: rel,
          line: i + 1,
          issue: `Public symbol uses banned modifier: ${m ? m[0] : '<unknown>'}`,
          rule: "Public API names must not encode 'enhanced/new/final' variants.",
        });
      }
    }
  }
  return out;
}

/* ----------------------- main checks ----------------------- */

export function checkNamingViolations(context = 'commit') {
  const root = repoRoot();
  const { policy, exceptions, canonicalMap } = loadNamingPolicy(root);
  const enforcement = getEnforcementLevel(context);
  const files = filteredFilesByScope(context, policy, policy.extensions);

  // Build clusters within crate boundaries
  const clusters = groupByNormalizedStem(files, policy, root);

  const violations = [];
  const warnings = [];

  for (const cl of clusters) {
    if (!cl.normStem) continue; // e.g., file with only modifiers stripped; unlikely but safe

    // Gather per-file facts
    const members = cl.members.map((m) => {
      const staged = readStagedText(root, m.rel);
      const canonicalDecl = canonicalOf(m.rel, policy, canonicalMap, staged);
      return {
        ...m,
        stagedText: staged,
        canonicalDecl,
        fileStem: stemOf(m.rel),
        hasBannedToken: new RegExp(`\\b(${policy.bannedModifiers.join('|')})\\b`, 'i').test(
          stemOf(m.rel)
        ),
      };
    });

    // Determine canonical reference for the cluster
    // Priority: explicit per-file pragma > canonical map entry > pick longest-lived file (oldest commit)
    let clusterCanonical = null;
    for (const m of members) {
      if (m.canonicalDecl) {
        clusterCanonical = m.canonicalDecl;
        break;
      }
    }
    if (!clusterCanonical && canonicalMap.canonicals && canonicalMap.canonicals[cl.normStem]) {
      clusterCanonical = canonicalMap.canonicals[cl.normStem];
    }
    if (!clusterCanonical && members.length > 1) {
      // Heuristic: choose the earliest introduced file as canonical
      let best = null;
      for (const m of members) {
        let ts = Number.MAX_SAFE_INTEGER;
        try {
          const out = execFileSync('git', ['log', '--follow', '--format=%ct', '--', m.rel], {
            cwd: root,
            encoding: 'utf8',
          });
          const times = out
            .split(/\r?\n/)
            .filter(Boolean)
            .map((s) => parseInt(s, 10));
          ts = Math.min(...times);
        } catch {
          // ignore
        }
        if (!best || ts < best.ts) best = { rel: m.rel, ts };
      }
      if (best) clusterCanonical = best.rel;
    }

    // If cluster size > 1 and no canonical declared -> warn
    if (members.length >= policy.clusterWarnSize && !clusterCanonical) {
      warnings.push({
        type: 'missing_canonical_declaration',
        file: members.map((m) => m.rel).join(', '),
        issue: `Duplicate stem cluster '${cl.normStem}' has no canonical reference.`,
        rule: `Declare canonical via 'CAWS: canonical-of <path>' pragma or ${CANONICAL_MAP_YAML}.`,
      });
    }

    // For each member with banned tokens, validate exception or canonical role
    for (const m of members) {
      const fileNameNoExt = path.basename(m.rel, path.extname(m.rel));
      const bannedMatch = fileNameNoExt.match(
        new RegExp(`\\b(${policy.bannedModifiers.join('|')})\\b`, 'i')
      );
      if (
        bannedMatch &&
        !policy.falsePositives.some((w) => fileNameNoExt.toLowerCase().includes(w))
      ) {
        const exc = matchException(m.rel, bannedMatch[0], exceptions);
        if (exc.valid) {
          warnings.push({
            type: 'exception_used',
            file: m.rel,
            issue: `Approved exception for modifier '${bannedMatch[0]}'`,
            reason: exc.entry.reason,
            approved_by: exc.entry.approved_by,
            expires_at: exc.entry.expires_at,
          });
        } else if (exc.expired) {
          violations.push({
            type: 'expired_exception',
            file: m.rel,
            issue: `Exception expired for '${bannedMatch[0]}'`,
            rule: 'Renew exception or rename to purpose-first canonical name.',
            severity: enforcement,
            original_exception: exc.entry,
          });
        } else {
          // If this file is the canonical of the cluster, we still suggest renaming unless map says it's canonical by intent
          const isCanonical =
            clusterCanonical && path.normalize(clusterCanonical) === path.normalize(m.rel);
          violations.push({
            type: 'filename_banned_modifier',
            file: m.rel,
            issue: `Banned modifier in filename: '${bannedMatch[0]}'`,
            rule: "Avoid 'enhanced/new/final/…' forks; converge on canonical.",
            severity: enforcement,
            suggestion: isCanonical
              ? 'Rename canonical to a purpose-first name; update canonical map/pragma.'
              : `Rename to match canonical: ${clusterCanonical ?? '<declare canonical>'} `,
          });
        }
      }

      // Symbol-level hints
      const sym = symbolHeuristics(m.rel, m.stagedText, policy);
      for (const s of sym) violations.push({ ...s, severity: enforcement });
    }

    // Shadow detection: same normalized stem with multiple files, where this change adds or touches a non-canonical member
    if (members.length > 1) {
      const rels = members.map((m) => m.rel);
      for (const m of members) {
        const isCanonical =
          clusterCanonical && path.normalize(clusterCanonical) === path.normalize(m.rel);
        if (!isCanonical) {
          violations.push({
            type: 'shadow_file',
            file: m.rel,
            cluster: rels,
            issue: `File shadows canonical stem '${cl.normStem}'.`,
            rule: 'One canonical entry point per stem within a crate. Merge or delete shadows.',
            severity: enforcement,
            suggestion: clusterCanonical
              ? `Move logic into canonical '${clusterCanonical}' and remove this file.`
              : 'Declare canonical and consolidate.',
          });
        }
      }
    }
  }

  // Let exception framework finalize severities / waivers
  const processed = processViolations('naming', [...violations], context, {
    defaultSeverity: (v) => v.severity || enforcement || 'warning',
  });

  return {
    violations: processed.violations,
    warnings: processed.warnings,
    enforcementLevel: processed.enforcementLevel || enforcement,
  };
}

export function checkSymbolNaming(context = 'commit') {
  // Kept for API parity, symbol checks are folded into checkNamingViolations now.
  const res = checkNamingViolations(context);
  return res.violations.filter((v) => v.type === 'symbol_banned_modifier');
}

/* ----------------------- CLI ----------------------- */

function main() {
  const context = process.argv[2] || 'commit';
  const res = checkNamingViolations(context);

  const blocking = res.violations.filter((v) => (v.severity || 'block') !== 'warning');
  const warnings = [
    ...res.warnings,
    ...res.violations.filter((v) => (v.severity || 'warn') === 'warn'),
  ];

  if (warnings.length) {
    console.log(`Approved exceptions / warnings: ${warnings.length}`);
    for (const w of warnings) {
      console.log(`- ${w.type}: ${w.file}`);
      if (w.issue) console.log(`  ${w.issue}`);
      if (w.suggestion) console.log(`  ${w.suggestion}`);
    }
    console.log('');
  }

  if (blocking.length) {
    console.log(`Blocking violations: ${blocking.length}\n`);
    for (const v of blocking) {
      console.log(`- ${v.type}: ${v.file}`);
      if (v.cluster) console.log(`  Cluster: ${v.cluster.join(', ')}`);
      if (v.rule) console.log(`  Rule: ${v.rule}`);
      if (v.issue) console.log(`  Issue: ${v.issue}`);
      if (v.suggestion) console.log(`  Suggestion: ${v.suggestion}`);
    }
    const level = getGlobalEnforcementLevel?.('naming') || res.enforcementLevel || 'block';
    console.log(`\nEnforcement: ${level.toUpperCase()}`);
    process.exit(1);
  }

  console.log('No blocking naming violations.');
  process.exit(0);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
