#!/usr/bin/env node
// scripts/refactor-progress-checker.mjs

/**
 * Refactoring Progress Monitor (hardened)
 *
 * - Loads targets and optional baselines from .caws/*
 * - Uses gate helpers you already have (god objects, duplication, quality gates)
 * - Produces structured JSON, JSONL timeseries, and optional GHA summary
 * - Deterministic context; default is 'ci'
 */

import { execFileSync, spawn } from 'child_process';
import fs from 'fs';
import yaml from 'js-yaml';
import path from 'path';
import { fileURLToPath } from 'url';

// -------------------- git + paths --------------------
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function repoRoot() {
  try {
    return execFileSync('git', ['rev-parse', '--show-toplevel'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch (e) {
    throw new Error('Not a git repository. Run inside a repo.');
  }
}
const ROOT = repoRoot();

// -------------------- config --------------------
const TARGETS_PATH = path.join(ROOT, '.caws', 'refactor-targets.yaml');
const BASELINES_PATH = path.join(ROOT, '.caws', 'refactor-baselines.yaml');
const REPORT_DIR = path.join(ROOT, 'docs-status');
const REPORT_PATH = path.join(REPORT_DIR, 'refactoring-progress-report.json');
const HISTORY_PATH = path.join(REPORT_DIR, 'refactoring-progress-history.jsonl');

const DEFAULT_TARGETS = {
  week: 'week-1',
  goals: {
    god_objects: { severe: 0, critical: 0, warning: 5 }, // warning = SLOC ≥ warning threshold
    duplicate_structs: 329,
    duplicate_filenames: 7,
    quality_gates: 'passing',
  },
};

const DEFAULT_BASELINES = {
  // Optional comparison anchors
  refs: {
    baseline: 'origin/main',
  },
  initial: {
    god_objects: { severe: 11, critical: null, warning: null },
    duplicate_structs: 658,
    duplicate_filenames: 69,
  },
};

function loadYamlSafe(p, fallback) {
  if (!fs.existsSync(p)) return fallback;
  const raw = fs.readFileSync(p, 'utf8');
  const data = yaml.load(raw);
  return { ...fallback, ...(data || {}) };
}

function ensureDir(p) {
  const d = path.dirname(p);
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}

// -------------------- context --------------------
function arg(key, def) {
  const i = process.argv.indexOf(`--${key}`);
  if (i >= 0 && i + 1 < process.argv.length) return process.argv[i + 1];
  return def;
}
const CONTEXT = arg('context', process.env.CAWS_ENFORCEMENT_CONTEXT || 'ci');

// -------------------- helpers --------------------
async function runQualityGatesCI() {
  return new Promise((resolve) => {
    const child = spawn('node', ['scripts/quality-gates/run-quality-gates.js', '--ci'], {
      stdio: 'pipe',
      cwd: ROOT,
    });
    let out = '',
      err = '';
    child.stdout.on('data', (d) => (out += d.toString()));
    child.stderr.on('data', (d) => (err += d.toString()));
    child.on('close', (code) =>
      resolve({
        status: code === 0 ? 'passing' : 'failing',
        exit_code: code,
        output: out,
        errors: err,
      })
    );
  });
}

function sortTopN(obj, n) {
  return Object.entries(obj)
    .sort(([, a], [, b]) => b - a)
    .slice(0, n)
    .map(([file, size]) => ({ file: path.relative(ROOT, file), size }));
}

function ratioProgress(current, target) {
  // Higher is better when current <= target
  if (current <= target) return 100;
  if (target === 0) return 0;
  return Math.max(0, Math.min(100, Math.round((target / current) * 100)));
}

function nowIso() {
  return new Date().toISOString();
}

// -------------------- collectors --------------------
async function collectGodObjects() {
  // Uses your hardened god-object detector
  const { getFileSizes } = await import(
    path.join(ROOT, 'packages', 'quality-gates', 'check-god-objects.mjs')
  );

  // Define thresholds based on the config
  const GOD_OBJECT_THRESHOLDS = { severe: 1000, critical: 1500, warning: 500 };

  const sizes = getFileSizes(CONTEXT); // returns SLOC by file
  const counts = {
    severe: Object.values(sizes).filter((s) => s >= GOD_OBJECT_THRESHOLDS.severe).length,
    critical: Object.values(sizes).filter((s) => s >= GOD_OBJECT_THRESHOLDS.critical).length,
    warning: Object.values(sizes).filter((s) => s >= GOD_OBJECT_THRESHOLDS.warning).length,
  };
  return { counts, largest: sortTopN(sizes, 8), thresholds: GOD_OBJECT_THRESHOLDS };
}

async function collectDuplication() {
  // Uses the unified functional duplication checker with all detection types
  const { checkFunctionalDuplication } = await import(
    path.join(ROOT, 'packages', 'quality-gates', 'check-functional-duplication.mjs')
  );

  const result = await checkFunctionalDuplication(CONTEXT);

  // Count different types of duplication violations
  const filenameDuplicates = result.violations.filter(
    (v) => v.type === 'functional_duplicate_cluster'
  ).length;
  const structDuplicates =
    result.violations.filter((v) => v.type === 'struct_duplication_regression').length +
    result.warnings.filter((v) => v.type === 'struct_duplication_near_baseline').length;

  // For detailed data, we'd need to extract from the violations
  // For now, return counts that can be used for progress tracking
  return {
    filename_count: filenameDuplicates,
    struct_count: structDuplicates,
    violations: result.violations,
    warnings: result.warnings,
  };
}

async function collectQuality() {
  return runQualityGatesCI();
}

// -------------------- core monitor --------------------
async function collectAll() {
  const targets = loadYamlSafe(TARGETS_PATH, DEFAULT_TARGETS);
  const baselines = loadYamlSafe(BASELINES_PATH, DEFAULT_BASELINES);

  const [god, dup, qual] = await Promise.all([
    collectGodObjects(),
    collectDuplication(),
    collectQuality(),
  ]);

  // Status vs targets
  const goal = targets.goals;
  const godStatus = {
    severe: {
      count: god.counts.severe,
      target: goal.god_objects.severe,
      ok: god.counts.severe <= goal.god_objects.severe,
    },
    critical: {
      count: god.counts.critical,
      target: goal.god_objects.critical,
      ok: god.counts.critical <= goal.god_objects.critical,
    },
    warning: {
      count: god.counts.warning,
      target: goal.god_objects.warning,
      ok: god.counts.warning <= goal.god_objects.warning,
    },
  };
  const dupStatus = {
    filenames: {
      count: dup.filename_count,
      target: goal.duplicate_filenames,
      ok: dup.filename_count <= goal.duplicate_filenames,
    },
    structs: {
      count: dup.struct_count,
      target: goal.duplicate_structs,
      ok: dup.struct_count <= goal.duplicate_structs,
    },
  };
  const qualStatus = {
    status: qual.status,
    ok: goal.quality_gates === 'passing' ? qual.status === 'passing' : true,
  };

  // Progress scores (bounded 0..100)
  const progress = {
    god_objects:
      godStatus.severe.ok && godStatus.critical.ok
        ? 100
        : Math.max(
            0,
            Math.min(
              100,
              Math.round(
                (ratioProgress(god.counts.severe, goal.god_objects.severe) +
                  ratioProgress(god.counts.critical, goal.god_objects.critical)) /
                  2
              )
            )
          ),
    duplication: Math.round(
      (ratioProgress(dup.filename_count, goal.duplicate_filenames) +
        ratioProgress(dup.struct_count, goal.duplicate_structs)) /
        2
    ),
    quality_gates: qualStatus.ok ? 100 : 0,
  };
  const overall = Math.round(
    (progress.god_objects + progress.duplication + progress.quality_gates) / 3
  );

  const report = {
    timestamp: nowIso(),
    context: CONTEXT,
    git: {
      branch: execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], {
        encoding: 'utf8',
      }).trim(),
      commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
      baseline: baselines.refs?.baseline || null,
    },
    targets,
    metrics: {
      god_objects: {
        counts: god.counts,
        thresholds: god.thresholds,
        largest_files: god.largest,
      },
      duplication: {
        filename_count: dup.filename_count,
        struct_count: dup.struct_count,
      },
      quality_gates: {
        status: qual.status,
        exit_code: qual.exit_code,
      },
    },
    progress: {
      overall_percentage: overall,
      breakdown: progress,
    },
    status: overall >= 80 ? 'good' : overall >= 50 ? 'needs_work' : 'critical',
    notes: {
      // Comparison to initial baselines if available
      initial: {
        god_objects: baselines.initial?.god_objects || null,
        duplicate_structs: baselines.initial?.duplicate_structs ?? null,
        duplicate_filenames: baselines.initial?.duplicate_filenames ?? null,
      },
    },
  };

  return report;
}

// -------------------- I/O & summary --------------------
function writeJsonAtomic(p, obj) {
  ensureDir(p);
  const tmp = p + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2));
  fs.renameSync(tmp, p);
}

function appendJsonl(p, obj) {
  ensureDir(p);
  const line = JSON.stringify(obj);
  fs.appendFileSync(p, line + '\n');
}

function writeGhaSummary(report) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) return;
  const lines = [];
  lines.push(`# Refactoring Progress`);
  lines.push(`- Timestamp: ${report.timestamp}`);
  lines.push(`- Branch: ${report.git.branch}`);
  lines.push(`- Commit: ${report.git.commit}`);
  lines.push(`- Context: ${report.context}`);
  lines.push(`- Overall: ${report.progress.overall_percentage}% (${report.status})`);
  lines.push(``);
  lines.push(`## God Objects`);
  lines.push(
    `- Severe ≥ ${report.metrics.god_objects.thresholds.severe}: ${report.metrics.god_objects.counts.severe}`
  );
  lines.push(
    `- Critical ≥ ${report.metrics.god_objects.thresholds.critical}: ${report.metrics.god_objects.counts.critical}`
  );
  lines.push(
    `- Warning ≥ ${report.metrics.god_objects.thresholds.warning}: ${report.metrics.god_objects.counts.warning}`
  );
  if (report.metrics.god_objects.largest_files?.length) {
    lines.push(`- Largest files:`);
    for (const f of report.metrics.god_objects.largest_files) {
      lines.push(`  - ${f.file}: ${f.size} SLOC`);
    }
  }
  lines.push(``);
  lines.push(`## Duplication`);
  lines.push(`- Duplicate filenames: ${report.metrics.duplication.filename_count}`);
  lines.push(`- Duplicate structs: ${report.metrics.duplication.struct_count}`);
  lines.push(``);
  lines.push(`## Quality Gates`);
  lines.push(`- Status: ${report.metrics.quality_gates.status}`);
  fs.appendFileSync(summaryPath, lines.join('\n') + '\n');
}

// -------------------- CLI --------------------
async function main() {
  try {
    const report = await collectAll();

    // Write artifacts
    writeJsonAtomic(REPORT_PATH, report);
    appendJsonl(HISTORY_PATH, {
      t: report.timestamp,
      branch: report.git.branch,
      commit: report.git.commit,
      overall: report.progress.overall_percentage,
      god_severe: report.metrics.god_objects.counts.severe,
      god_critical: report.metrics.god_objects.counts.critical,
      dup_files: report.metrics.duplication.filename_count,
      dup_structs: report.metrics.duplication.struct_count,
      quality: report.metrics.quality_gates.status,
    });
    writeGhaSummary(report);

    // Console summary (no emojis, one-liners)
    console.log('AGENT AGENCY V3 - CRISIS RESPONSE MONITOR');
    console.log('='.repeat(60));
    console.log(`Timestamp: ${report.timestamp}`);
    console.log(
      `Branch: ${report.git.branch}  Commit: ${report.git.commit}  Context: ${report.context}`
    );
    console.log(
      `Overall Progress: ${report.progress.overall_percentage}%  Status: ${report.status}`
    );
    console.log('');
    console.log('God Objects:');
    console.log(
      `  Severe (≥${report.metrics.god_objects.thresholds.severe}): ${report.metrics.god_objects.counts.severe}`
    );
    console.log(
      `  Critical (≥${report.metrics.god_objects.thresholds.critical}): ${report.metrics.god_objects.counts.critical}`
    );
    console.log(
      `  Warning (≥${report.metrics.god_objects.thresholds.warning}): ${report.metrics.god_objects.counts.warning}`
    );
    if (report.metrics.god_objects.largest_files?.length) {
      console.log('  Largest files:');
      for (const f of report.metrics.god_objects.largest_files) {
        console.log(`    - ${f.file} : ${f.size} SLOC`);
      }
    }
    console.log('');
    console.log('Duplication:');
    console.log(`  Duplicate filenames: ${report.metrics.duplication.filename_count}`);
    console.log(`  Duplicate structs:   ${report.metrics.duplication.struct_count}`);
    console.log('');
    console.log('Quality Gates:');
    console.log(`  Status: ${report.metrics.quality_gates.status}`);
    console.log('');

    // Exit policy: this is a monitor, not a gate. Exit 0 unless --strict
    const strict = process.argv.includes('--strict');
    if (strict) {
      const t = loadYamlSafe(TARGETS_PATH, DEFAULT_TARGETS).goals;
      const fails =
        report.metrics.god_objects.counts.severe > t.god_objects.severe ||
        report.metrics.god_objects.counts.critical > t.god_objects.critical ||
        report.metrics.duplication.filename_count > t.duplicate_filenames ||
        report.metrics.duplication.struct_count > t.duplicate_structs ||
        (t.quality_gates === 'passing' && report.metrics.quality_gates.status !== 'passing');
      process.exit(fails ? 1 : 0);
    } else {
      process.exit(0);
    }
  } catch (e) {
    console.error('Refactoring monitor failed:', e.message);
    process.exit(2);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export default main;
