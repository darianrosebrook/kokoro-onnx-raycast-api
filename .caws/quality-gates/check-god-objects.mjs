#!/usr/bin/env node

/**
 * Quality Gate: God Object Detector (Rust-focused, Git-correct, regression-aware)
 *
 * @author: @darianrosebrook
 * @date: 2025-10-28
 * @version: 1.0.0
 * @license: MIT
 * @copyright: 2025 Darian Rosebrook
 * @description: Detects files that are too large (god objects) and blocks commits that would create or worsen them.
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import yaml from 'js-yaml';
import micromatch from 'micromatch';
import os from 'os';
import path from 'path';
import { getEnforcementLevel, processViolations } from './shared-exception-framework.mjs';

// Optional: reuse the hardened file scope manager for staged file discovery
import { getFilesToCheck } from './file-scope-manager.mjs';

/* ----------------------------- Git helpers ----------------------------- */

function normalizePath(p) {
  // Normalize paths for cross-platform compatibility
  return os.platform() === 'win32' ? p.replace(/\\/g, '/') : p;
}

function git(args, { cwd } = {}) {
  try {
    return execFileSync('git', args, {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch (error) {
    throw new Error(
      `Git command failed: ${args.join(' ')} - ${error.message}. Run from within a git repository.`
    );
  }
}
function gitBuf(args, { cwd } = {}) {
  try {
    return execFileSync('git', args, {
      cwd,
      stdio: ['ignore', 'pipe', 'ignore'],
    });
  } catch (error) {
    throw new Error(
      `Git command failed: ${args.join(' ')} - ${error.message}. Run from within a git repository.`
    );
  }
}
function splitNul(bufOrStr) {
  const s = Buffer.isBuffer(bufOrStr) ? bufOrStr.toString('utf8') : bufOrStr;
  return s.split('\0').filter(Boolean);
}
function repoRoot() {
  return git(['rev-parse', '--show-toplevel']);
}
function resolveBaseRef(root, fallback) {
  try {
    return git(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], {
      cwd: root,
    });
  } catch {
    return (
      process.env.GITHUB_BASE_REF ||
      process.env.PR_BASE_REF ||
      process.env.PR_BASE_SHA ||
      fallback ||
      safeOriginHead(root)
    );
  }
}
function safeOriginHead(root) {
  try {
    const ref = git(['symbolic-ref', 'refs/remotes/origin/HEAD'], {
      cwd: root,
    });
    return ref || 'origin/HEAD';
  } catch {
    return 'origin/HEAD';
  }
}

/* ----------------------------- Config load ----------------------------- */

const DEFAULT_THRESHOLDS = {
  severe: 3000, // immediate block
  critical: 2000, // block in CI or with stricter enforcement
  warning: 1750, // warn
  target: 1500, // long-term target
};

// remediation budgets: allow N SLOC delta on known god objects while refactoring
const DEFAULT_CONFIG = {
  ciBaseRef: 'origin/HEAD',
  thresholds: DEFAULT_THRESHOLDS,
  knownGodObjects: [
    // Project-agnostic patterns - will be populated by .qualitygatesrc.yaml
    // Examples of common god object patterns:
    // "**/src/main.rs",           // Main entry points
    // "**/src/lib.rs",            // Library roots
    // "**/src/app.rs",            // Application modules
    // "**/src/server.rs",         // Server implementations
    // "**/src/database.rs",       // Database modules
    // "**/src/api.rs",            // API modules
  ],
  knownGodObjectBudgets: {
    // Project-agnostic budgets - will be populated by .qualitygatesrc.yaml
    // Examples:
    // "**/src/main.rs": 0,        // No growth on main entry points
    // "**/src/server.rs": 25,     // Small headroom for server modules
    // "**/src/database.rs": 25,   // Small headroom for database modules
  },
  excludeGlobs: ['**/target/**'],
};

function loadQualityConfig(root) {
  const candidates = [
    path.join(root, '.qualitygatesrc.yaml'),
    path.join(root, '.qualitygatesrc.yml'),
    path.join(root, '.qualitygatesrc.json'),
  ];
  for (const p of candidates) {
    if (!fs.existsSync(p)) continue;
    const raw = fs.readFileSync(p, 'utf8');
    const user = p.endsWith('.json') ? JSON.parse(raw) : yaml.load(raw) || {};
    return {
      ...DEFAULT_CONFIG,
      ...user,
      thresholds: { ...DEFAULT_THRESHOLDS, ...(user?.thresholds || {}) },
    };
  }
  return { ...DEFAULT_CONFIG };
}

/* ----------------------------- SLOC counting ----------------------------- */
/** Rust-aware SLOC: ignores blank lines, // line comments, /* block comments *\/ (naïve but effective). */
function countRustSloc(text) {
  let sloc = 0;
  let inBlock = false;
  for (const raw of text.split(/\r?\n/)) {
    let line = raw;
    // strip inline // if not inside block
    if (!inBlock) {
      const idx = line.indexOf('//');
      if (idx >= 0) line = line.slice(0, idx);
    }
    // handle block comments
    let i = 0;
    let kept = '';
    while (i < line.length) {
      if (!inBlock && line[i] === '/' && line[i + 1] === '*') {
        inBlock = true;
        i += 2;
        continue;
      }
      if (inBlock && line[i] === '*' && line[i + 1] === '/') {
        inBlock = false;
        i += 2;
        continue;
      }
      if (!inBlock) kept += line[i];
      i++;
    }
    if (kept.trim().length > 0) sloc++;
  }
  return sloc;
}

/* ----------------------------- Staged vs Base sizes ----------------------------- */
/** Read the *staged* blob for path (from the index), repo-relative path. */
function readStagedFile(root, relPath) {
  try {
    // `:` is the index pseudo-tree
    return execFileSync('git', ['show', `:${relPath}`], {
      cwd: root,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
    });
  } catch {
    // If not staged (e.g., deletion), return null
    return null;
  }
}
/** Read the file content at base ref. */
function readBaseFile(root, baseRef, relPath) {
  try {
    return execFileSync('git', ['show', `${baseRef}:${relPath}`], {
      cwd: root,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
    });
  } catch {
    return null; // new file
  }
}

function rustSlocAtStages(root, baseRef, relPath) {
  const staged = readStagedFile(root, relPath);
  if (staged === null) return { staged: null, base: null, delta: 0 };
  const stagedSloc = countRustSloc(staged);

  const base = readBaseFile(root, baseRef, relPath);
  const baseSloc = base === null ? 0 : countRustSloc(base);

  return { staged: stagedSloc, base: baseSloc, delta: stagedSloc - baseSloc };
}

/* ----------------------------- Core rule ----------------------------- */

function classifySize(sloc, thresholds) {
  if (sloc >= thresholds.severe) return 'severe';
  if (sloc >= thresholds.critical) return 'critical';
  if (sloc >= thresholds.warning) return 'warning';
  return 'ok';
}

function budgetFor(relPath, budgets) {
  // longest (most specific) glob wins
  let best = null;
  for (const [glob, val] of Object.entries(budgets || {})) {
    if (micromatch.isMatch(relPath, glob, { dot: true })) {
      if (!best || glob.length > best.glob.length) best = { glob, val };
    }
  }
  return best ? best.val : 0;
}

function isKnownGodObject(relPath, known) {
  return known.some((g) => micromatch.isMatch(relPath, g, { dot: true }));
}

/* ----------------------------- Public API ----------------------------- */

export function getFileSizes(context = 'commit') {
  const root = repoRoot();
  const cfg = loadQualityConfig(root);
  const baseRef = resolveBaseRef(root, cfg.ciBaseRef);

  // discover staged Rust files via scope manager; keep only *.rs
  const absFiles = getFilesToCheck(context).filter((p) => p.endsWith('.rs'));
  const relFiles = absFiles.map((a) => path.relative(root, a));

  const sizes = {};
  for (const rel of relFiles) {
    const { staged } = rustSlocAtStages(root, baseRef, rel);
    if (typeof staged === 'number') sizes[path.join(root, rel)] = staged;
  }
  return sizes;
}

export function checkGodObjects(context = 'commit', filesToCheck = null) {
  const root = repoRoot();
  const cfg = loadQualityConfig(root);
  const baseRef = resolveBaseRef(root, cfg.ciBaseRef);
  const thresholds = cfg.thresholds;

  // select repo-relative Rust files
  let relFiles;
  if (Array.isArray(filesToCheck) && filesToCheck.length) {
    relFiles = filesToCheck
      .filter((p) => p.endsWith('.rs'))
      .map((p) => (path.isAbsolute(p) ? path.relative(root, p) : p));
  } else {
    const abs = getFilesToCheck(context).filter((p) => p.endsWith('.rs'));
    relFiles = abs.map((a) => path.relative(root, a));
  }

  const rawViolations = [];

  for (const rel of relFiles) {
    const { staged, base, delta } = rustSlocAtStages(root, baseRef, rel);
    if (staged === null) continue; // deleted/not staged

    const cls = classifySize(staged, thresholds);
    const known = isKnownGodObject(rel, cfg.knownGodObjects);
    const allowedDelta = known ? budgetFor(rel, cfg.knownGodObjectBudgets) : 0;

    // Always emit a warning when beyond warning threshold
    if (cls === 'warning' || cls === 'critical' || cls === 'severe') {
      rawViolations.push({
        type: `${cls}_god_object`,
        file: path.join(root, rel),
        relativePath: rel,
        size: staged,
        baseSize: base,
        delta,
        threshold: thresholds[cls],
        message:
          cls === 'warning'
            ? `WARNING: ${staged} SLOC approaches god-object territory (≥ ${thresholds.warning}).`
            : `${cls.toUpperCase()} god object: ${staged} SLOC exceeds ${
                thresholds[cls]
              } SLOC limit.`,
        // severity is set later by exception framework; we propose defaults below
      });
    }

    // Regression rule: block if your change pushes file across a boundary or exceeds budget
    const crossedToCritical = (base ?? 0) < thresholds.critical && staged >= thresholds.critical;
    const crossedToSevere = (base ?? 0) < thresholds.severe && staged >= thresholds.severe;

    const exceededBudget = known && delta > allowedDelta;

    if (crossedToSevere || crossedToCritical || exceededBudget) {
      rawViolations.push({
        type: 'new_or_worsened_god_object',
        file: path.join(root, rel),
        relativePath: rel,
        size: staged,
        baseSize: base,
        delta,
        threshold: crossedToSevere
          ? thresholds.severe
          : crossedToCritical
            ? thresholds.critical
            : allowedDelta,
        severity: 'block',
        message: crossedToSevere
          ? `Crossed SEVERE threshold: ${base ?? 0}→${staged} SLOC (limit ${thresholds.severe}).`
          : crossedToCritical
            ? `Crossed CRITICAL threshold: ${base ?? 0}→${staged} SLOC (limit ${
                thresholds.critical
              }).`
            : `Known god object exceeded remediation budget: +${delta} SLOC (budget ${allowedDelta}).`,
      });
    }
  }

  // Defer final severity to the exception framework; recommend defaults:
  // - severe/critical => block in commit & CI
  // - warning => warn in commit; block in CI if enforcement policy says so
  const result = processViolations('god_objects', rawViolations, context, {
    defaultSeverity: (v) => {
      if (v.type === 'new_or_worsened_god_object') return 'block';
      if (v.type === 'severe_god_object') return 'block';
      if (v.type === 'critical_god_object') return context === 'ci' ? 'block' : 'warn';
      if (v.type === 'warning_god_object') return 'warn';
      return 'warn';
    },
  });

  return {
    violations: result.violations,
    warnings: result.warnings,
    enforcementLevel: result.enforcementLevel ?? getEnforcementLevel?.('god_objects'),
  };
}

export function checkGodObjectRegression(context = 'commit') {
  // Kept for compatibility; regression is now folded into checkGodObjects
  const res = checkGodObjects(context);
  return res.violations.filter((v) => v.type === 'new_or_worsened_god_object');
}

/* ----------------------------- CLI ----------------------------- */

function main() {
  const context = process.argv[2] || 'commit';
  const root = repoRoot();
  const cfg = loadQualityConfig(root);
  const res = checkGodObjects(context);

  const blocking = res.violations.filter((v) => (v.severity || 'block') === 'block');
  const warnings = [...res.violations, ...res.warnings].filter(
    (v) => (v.severity || 'warn') === 'warn'
  );

  // Stats
  const baseRef = resolveBaseRef(root, cfg.ciBaseRef);
  const abs = getFilesToCheck(context).filter((p) => p.endsWith('.rs'));
  const rel = abs.map((a) => path.relative(root, a));
  let severe = 0,
    critical = 0,
    warning = 0;
  for (const r of rel) {
    const { staged } = rustSlocAtStages(root, baseRef, r);
    if (staged == null) continue;
    const cls = classifySize(staged, cfg.thresholds);
    if (cls === 'severe') severe++;
    else if (cls === 'critical') critical++;
    else if (cls === 'warning') warning++;
  }

  console.log('📊 God object (Rust SLOC) stats:');
  console.log(`   - ${severe} files ≥ ${cfg.thresholds.severe} (severe)`);
  console.log(`   - ${critical} files ≥ ${cfg.thresholds.critical} (critical)`);
  console.log(`   - ${warning} files ≥ ${cfg.thresholds.warning} (warning)`);

  if (warnings.length) {
    console.log('\n⚠️  WARNINGS:');
    for (const v of warnings) {
      console.log(`   ${v.relativePath}: ${v.message}`);
    }
  }

  if (blocking.length) {
    console.log(`\n🚨 BLOCKING VIOLATIONS (${blocking.length}):\n`);
    for (const v of blocking) {
      console.log(`❌ ${v.type.toUpperCase().replace(/_/g, ' ')}`);
      console.log(`   File: ${v.relativePath}`);
      if (typeof v.baseSize === 'number') console.log(`   Base: ${v.baseSize} SLOC`);
      console.log(`   Size: ${v.size} SLOC`);
      console.log(`   Delta: ${v.delta >= 0 ? '+' : ''}${v.delta}`);
      console.log(`   Limit/Budget: ${v.threshold}`);
      console.log(`   Issue: ${v.message}\n`);
    }
    console.log('🔧 Decompose or reduce these files before committing.');
    console.log('💡 See: docs/audits/v3-codebase-audit-2025-10/03-god-objects-analysis.md');
    process.exit(1);
  }

  console.log('\n✅ No blocking god object violations');
  if (!warnings.length) console.log('✅ No god object warnings');
  process.exit(0);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
