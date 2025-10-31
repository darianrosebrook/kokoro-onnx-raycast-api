#!/usr/bin/env node

/**
 * Quality Gate: Code Freeze Enforcement
 *
 * Blocks commits that add new features during crisis response.
 * Allows bug fixes, refactors, and critical maintenance.
 *
 * - Configurable via .caws/code-freeze.yaml
 * - Deterministic scoping via file-scope manager
 * - Conventional-Commits aware ("feat:" blocks; "fix:"/ "refactor:" allowed)
 * - Accurate insertion counts via --numstat (total + per-file budgets)
 * - Exception-aware via shared-exception-framework v2
 * - Supports allow-listed new files (tests/docs/migrations) by glob pattern
 * - Accepts --context and --json for CI
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import yaml from 'js-yaml';
import micromatch from 'micromatch';
import path from 'path';
import { fileURLToPath } from 'url';

import { getFilesToCheck } from './file-scope-manager.mjs';
import {
  getEnforcementLevel,
  loadExceptionConfig,
  processViolations,
} from './shared-exception-framework.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = repoRoot();
const CFG_PATH = path.join(REPO_ROOT, '.caws', 'code-freeze.yaml');

function repoRoot() {
  try {
    return execFileSync('git', ['rev-parse', '--show-toplevel'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return process.cwd();
  }
}

/* ----------------------------- config ----------------------------- */

const DEFAULT_CFG = {
  blocked_commit_types: ['feat', 'perf'],
  allowed_commit_types: ['fix', 'refactor', 'chore', 'docs', 'test', 'revert'],
  // Fallback keyword heuristics when type is unknown or message is non-conventional
  new_feature_keywords: [
    'feature',
    'add',
    'new',
    'create',
    'implement',
    'introduce',
    'enhance',
    'extend',
    'expand',
    'upgrade',
    'improve',
    'build',
    'develop',
    'launch',
  ],
  allowed_keywords: [
    'fix',
    'bug',
    'refactor',
    'cleanup',
    'remove',
    'delete',
    'extract',
    'merge',
    'consolidate',
    'decompose',
    'quality gate',
    'crisis',
    'emergency',
    'audit',
    'test',
    'lint',
    'format',
    'doc',
    'readme',
    'comment',
  ],
  // New files policy
  allowed_new_file_patterns: [
    '**/*.md',
    '**/*.mdx',
    '**/*.rst',
    '**/__tests__/**',
    '**/*.spec.*',
    '**/*.test.*',
    '**/tests/**',
    '**/fixtures/**',
    '**/migrations/**',
    '**/.changeset/**',
  ],
  // Source extensions that are suspicious when added in freeze
  watch_extensions: [
    '.rs',
    '.ts',
    '.tsx',
    '.js',
    '.jsx',
    '.mjs',
    '.cjs',
    '.go',
    '.java',
    '.kt',
    '.swift',
    '.py',
    '.cpp',
    '.c',
    '.h',
  ],
  // Budgets
  max_total_insertions: 500, // total added lines across the change
  max_per_file_insertions: 300, // added lines per file
  // Enforcement context default
  default_context: 'commit',
};

function loadFreezeConfig() {
  if (!fs.existsSync(CFG_PATH)) return DEFAULT_CFG;
  try {
    const raw = fs.readFileSync(CFG_PATH, 'utf8');
    const cfg = yaml.load(raw) || {};
    return { ...DEFAULT_CFG, ...cfg };
  } catch {
    return DEFAULT_CFG;
  }
}

/* ----------------------------- git helpers ----------------------------- */

function git(args, opts = {}) {
  return execFileSync('git', args, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
    ...opts,
  }).trim();
}

function currentContext() {
  const argIdx = process.argv.indexOf('--context');
  if (argIdx >= 0 && argIdx + 1 < process.argv.length) return process.argv[argIdx + 1];
  return process.env.CAWS_ENFORCEMENT_CONTEXT || DEFAULT_CFG.default_context;
}

function inCI() {
  return !!process.env.CI;
}

/* ----------------------------- analysis primitives ----------------------------- */

function parseConventionalType(msg) {
  // E.g., "feat(parser)!: add lookahead", "fix: handle null", "docs(readme): ..."
  const m = msg.match(/^([a-zA-Z]+)(\([\w\-\s/]+\))?(!)?:\s/i);
  return m ? m[1].toLowerCase() : null;
}

function latestCommitMessageOrStagedFallback() {
  // In pre-commit, HEAD may not have the new commit yet; best effort:
  try {
    return git(['log', '-1', '--pretty=%B']);
  } catch {
    // Fallback: use staged diff summary as pseudo-message
    try {
      const names = git(['diff', '--cached', '--name-only']);
      return `staged changes: ${names.split('\n').slice(0, 20).join(', ')}`;
    } catch {
      return '';
    }
  }
}

function numstat() {
  // Returns array of {added, deleted, file}
  // lines like: "12\t0\tsrc/foo.rs"
  const out = git(['diff', '--cached', '--numstat'], { cwd: REPO_ROOT });
  if (!out) return [];
  return out
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      const [a, d, ...rest] = line.split('\t');
      return {
        added: parseInt(a || '0', 10),
        deleted: parseInt(d || '0', 10),
        file: rest.join('\t'),
      };
    });
}

function stagedNewFiles() {
  // Files that are A(dded) in the index (staged)
  const out = git(['diff', '--cached', '--name-status']);
  const rows = out
    .split('\n')
    .filter(Boolean)
    .map((l) => l.split(/\s+/));
  const added = rows.filter(([status]) => status === 'A').map(([, f]) => f);
  return added;
}

/* ----------------------------- checks ----------------------------- */

export async function checkCommitMessage(context = currentContext(), cfg = loadFreezeConfig()) {
  const message = latestCommitMessageOrStagedFallback().trim();
  const lower = message.toLowerCase();
  const ctype = parseConventionalType(message);

  // Conventional-commits check first
  if (ctype) {
    if (cfg.blocked_commit_types.includes(ctype)) {
      // Unless the message also includes a whitelisted keyword like "fix" for a revert/fixup
      const hasAllowedKw = cfg.allowed_commit_types.some((t) => lower.startsWith(`${t}:`));
      if (!hasAllowedKw) {
        return {
          blocked: true,
          reason: `Commit type "${ctype}" is blocked during code freeze`,
          suggestion: `Use an allowed type (${cfg.allowed_commit_types.join(', ')}) or file an exception.`,
          file: 'commit_message',
        };
      }
    }
  } else {
    // Keyword heuristic fallback
    const hasNewFeature = cfg.new_feature_keywords.some((kw) => lower.includes(kw));
    const hasAllowed = cfg.allowed_keywords.some((kw) => lower.includes(kw));
    if (hasNewFeature && !hasAllowed) {
      return {
        blocked: true,
        reason: `Commit message suggests new feature: "${message.replace(/\s+/g, ' ').slice(0, 120)}"`,
        suggestion:
          'During freeze, allow only bug fixes, refactors, tests, docs. Rephrase and split if necessary.',
        file: 'commit_message',
      };
    }
  }

  return { blocked: false };
}

export async function checkNewFiles(context = currentContext(), cfg = loadFreezeConfig()) {
  const added = stagedNewFiles();
  if (!added.length) return { blocked: false };

  // Respect allowlist (tests/docs/fixtures/migrations/etc.)
  const disallowed = added.filter((f) => {
    if (cfg.allowed_new_file_patterns.some((pat) => micromatch.isMatch(f, pat, { dot: true })))
      return false;
    // If it's a source file extension, treat as suspicious
    const ext = path.extname(f).toLowerCase();
    return cfg.watch_extensions.includes(ext);
  });

  if (disallowed.length) {
    return {
      blocked: true,
      reason: `New source files staged during code freeze: ${disallowed.join(', ')}`,
      suggestion:
        'Avoid introducing new modules during freeze. Use exceptions for critical hotfixes only.',
      file: disallowed[0],
    };
  }

  return { blocked: false };
}

export async function checkLargeAdditions(context = currentContext(), cfg = loadFreezeConfig()) {
  const rows = numstat();
  const totalAdd = rows.reduce((sum, r) => sum + (isNaN(r.added) ? 0 : r.added), 0);
  const tooBigFiles = rows
    .filter((r) => {
      const ext = path.extname(r.file).toLowerCase();
      return cfg.watch_extensions.includes(ext) && r.added > cfg.max_per_file_insertions;
    })
    .map((r) => `${r.file} (+${r.added})`);

  if (totalAdd > cfg.max_total_insertions) {
    return {
      blocked: true,
      reason: `Large addition detected: +${totalAdd} lines staged (budget ${cfg.max_total_insertions})`,
      suggestion: 'Split the change into smaller, reviewable patches during freeze.',
      file: 'diff_index',
    };
  }

  if (tooBigFiles.length) {
    return {
      blocked: true,
      reason: `Per-file addition over budget: ${tooBigFiles.join(', ')}`,
      suggestion: `Keep per-file additions ≤ ${cfg.max_per_file_insertions} during freeze.`,
      file: tooBigFiles[0].split(' ')[0],
    };
  }

  return { blocked: false };
}

/**
 * Aggregated synchronous gate for use by other scripts.
 */
export function checkCodeFreeze(context = currentContext()) {
  const cfg = loadFreezeConfig();
  const violations = [];

  // Global override (shared exceptions) – if code_freeze disabled, pass
  const xc = loadExceptionConfig();
  const freeze = xc.global_overrides?.code_freeze;
  if (freeze && freeze.enabled === false) {
    return {
      violations: [],
      warnings: [],
      enforcementLevel: getEnforcementLevel('code_freeze', context),
    };
  }

  // Commit message - synchronous check
  const message = latestCommitMessageOrStagedFallback().trim();
  const lower = message.toLowerCase();
  const ctype = parseConventionalType(message);

  if (ctype) {
    if (cfg.blocked_commit_types.includes(ctype)) {
      const hasAllowedKw = cfg.allowed_commit_types.some((t) => lower.startsWith(`${t}:`));
      if (!hasAllowedKw) {
        violations.push({
          type: 'new_feature_commit',
          file: 'commit_message',
          message: `Commit type "${ctype}" is blocked during code freeze`,
          suggestion: `Use an allowed type (${cfg.allowed_commit_types.join(', ')}) or file an exception.`,
        });
      }
    }
  } else {
    const hasNewFeature = cfg.new_feature_keywords.some((kw) => lower.includes(kw));
    const hasAllowed = cfg.allowed_keywords.some((kw) => lower.includes(kw));
    if (hasNewFeature && !hasAllowed) {
      violations.push({
        type: 'new_feature_commit',
        file: 'commit_message',
        message: `Commit message suggests new feature: "${message.replace(/\s+/g, ' ').slice(0, 120)}"`,
        suggestion:
          'During freeze, allow only bug fixes, refactors, tests, docs. Rephrase and split if necessary.',
      });
    }
  }

  // New files - synchronous check
  const added = stagedNewFiles();
  if (added.length) {
    const disallowed = added.filter((f) => {
      if (cfg.allowed_new_file_patterns.some((pat) => micromatch.isMatch(f, pat, { dot: true })))
        return false;
      const ext = path.extname(f).toLowerCase();
      return cfg.watch_extensions.includes(ext);
    });

    if (disallowed.length) {
      violations.push({
        type: 'new_file_during_freeze',
        file: disallowed[0],
        message: `New source files staged during code freeze: ${disallowed.join(', ')}`,
        suggestion:
          'Avoid introducing new modules during freeze. Use exceptions for critical hotfixes only.',
      });
    }
  }

  // Insertions budget - synchronous check
  const rows = numstat();
  const totalAdd = rows.reduce((sum, r) => sum + (isNaN(r.added) ? 0 : r.added), 0);
  const tooBigFiles = rows
    .filter((r) => {
      const ext = path.extname(r.file).toLowerCase();
      return cfg.watch_extensions.includes(ext) && r.added > cfg.max_per_file_insertions;
    })
    .map((r) => `${r.file} (+${r.added})`);

  if (totalAdd > cfg.max_total_insertions) {
    violations.push({
      type: 'large_addition_during_freeze',
      file: 'diff_index',
      message: `Large addition detected: +${totalAdd} lines staged (budget ${cfg.max_total_insertions})`,
      suggestion: 'Split the change into smaller, reviewable patches during freeze.',
    });
  }

  if (tooBigFiles.length) {
    violations.push({
      type: 'large_addition_during_freeze',
      file: tooBigFiles[0].split(' ')[0],
      message: `Per-file addition over budget: ${tooBigFiles.join(', ')}`,
      suggestion: `Keep per-file additions ≤ ${cfg.max_per_file_insertions} during freeze.`,
    });
  }

  // Scope for logging (optional, no filtering needed here—gate operates on git index)
  // But you can fetch for transparency:
  void getFilesToCheck(context); // ensures consistency with other gates

  const result = processViolations('code_freeze', violations, context);

  return {
    violations: result.violations,
    warnings: result.warnings,
    enforcementLevel: result.enforcementLevel,
  };
}

/* ----------------------------- CLI ----------------------------- */

function main() {
  const contextArgIdx = process.argv.indexOf('--context');
  const context =
    contextArgIdx >= 0 && contextArgIdx + 1 < process.argv.length
      ? process.argv[contextArgIdx + 1]
      : currentContext();

  const jsonOut = process.argv.includes('--json');

  // Use the synchronous checkCodeFreeze function
  const result = checkCodeFreeze(context);

  if (jsonOut) {
    const payload = {
      context,
      enforcement: result.enforcementLevel,
      violations: result.violations,
      warnings: result.warnings,
    };
    console.log(JSON.stringify(payload, null, 2));
    process.exit(result.violations.length ? 1 : 0);
  }

  if (result.violations.length) {
    console.log(`CODE FREEZE VIOLATIONS (${result.violations.length})`);
    for (const v of result.violations) {
      console.log(`- ${v.type}: ${v.message}`);
      if (v.suggestion) console.log(`  Suggestion: ${v.suggestion}`);
    }
    console.log(`Enforcement: ${result.enforcementLevel.toUpperCase()}`);
    process.exit(1);
  } else {
    if (result.warnings.length) {
      console.log(`Code freeze: warnings (${result.warnings.length})`);
      for (const w of result.warnings) {
        console.log(`- exception_used: ${w.violation?.message || w.violation?.issue || w.gate}`);
      }
    }
    console.log('Code freeze compliance check passed.');
    process.exit(0);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    main();
  } catch (e) {
    console.error('Code freeze check failed:', e.message);
    process.exit(2);
  }
}
