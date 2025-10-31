#!/usr/bin/env node
// scripts/quality-gates/shared-exception-framework.mjs
/* CAWS Shared Exception Framework (v2)
   - Git-relative matching, micromatch globs
   - Context constraints (branch/author/CI/time)
   - Budgets & recurrence caps
   - Atomic saves, basic lockfile
   - AJV schema validation
*/

import Ajv from 'ajv';
import { execFileSync } from 'child_process';
import fs from 'fs';
import micromatch from 'micromatch';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = repoRootSafe() ?? path.join(__dirname, '..', '..');
const EXCEPTION_CONFIG_PATH = path.join(PROJECT_ROOT, '.caws', 'quality-exceptions.json');
const LOCK_PATH = path.join(PROJECT_ROOT, '.caws', '.quality-exceptions.lock');

function repoRootSafe() {
  try {
    return execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
  } catch {
    return null;
  }
}

/* ----------------------------- Schema & defaults ----------------------------- */

const EXCEPTION_SCHEMA = {
  $id: 'caws/quality-exceptions',
  type: 'object',
  additionalProperties: false,
  properties: {
    schema_version: { const: '2.0.0' },
    description: { type: 'string' },
    gates: {
      type: 'object',
      additionalProperties: {
        type: 'object',
        properties: {
          description: { type: 'string' },
          enforcement_levels: {
            type: 'object',
            properties: {
              commit: { enum: ['warning', 'block', 'fail'] },
              push: { enum: ['warning', 'block', 'fail'] },
              ci: { enum: ['warning', 'block', 'fail'] },
            },
            additionalProperties: false,
            required: ['commit', 'push', 'ci'],
          },
        },
        required: ['enforcement_levels'],
        additionalProperties: false,
      },
    },
    global_overrides: {
      type: 'object',
      additionalProperties: false,
      properties: {
        // e.g., "code_freeze": { enabled: true, gates: ["*"], level: "fail" }
        code_freeze: {
          type: 'object',
          additionalProperties: false,
          properties: {
            enabled: { type: 'boolean' },
            gates: { type: 'array', items: { type: 'string' } },
            level: { enum: ['warning', 'block', 'fail'] },
          },
        },
      },
    },
    exceptions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'string' },
          gate: { type: 'string' },
          reason: { type: 'string' },
          approved_by: { type: 'string' },
          approved_at: { type: 'string', format: 'date-time' },
          expires_at: { type: 'string', format: 'date-time' },
          review_required: { type: 'boolean' },
          context: { type: 'string' }, // "all"|"commit"|"push"|"ci"
          // Matching
          file_pattern: { type: 'string' },
          violation_type: { type: 'string' },
          message_regex: { type: 'string' },
          // Budgets (optional)
          size_threshold: { type: 'number' },
          delta_budget: { type: 'number' }, // e.g., allow +25 SLOC growth while refactoring
          max_hits: { type: 'number' }, // cap usage
          // Constraints
          branch: { type: 'string' }, // glob, e.g. "feature/**"
          author_email: { type: 'string' }, // exact or glob
          ci_only: { type: 'boolean' },
          effective_from: { type: 'string', format: 'date-time' },
          // Audit
          created_by: { type: 'string' },
          updated_at: { type: 'string', format: 'date-time' },
          hits: { type: 'number' },
        },
        required: ['id', 'gate', 'reason', 'approved_by', 'approved_at', 'expires_at'],
      },
    },
  },
  required: ['schema_version', 'gates', 'exceptions'],
};

const DEFAULT_CONFIG = {
  schema_version: '2.0.0',
  gates: {
    naming: {
      description: 'Naming convention violations',
      enforcement_levels: { commit: 'warning', push: 'block', ci: 'fail' },
    },
    god_objects: {
      description: 'Files exceeding size thresholds',
      enforcement_levels: { commit: 'warning', push: 'block', ci: 'fail' },
    },
    duplication: {
      description: 'Functional duplication violations',
      enforcement_levels: { commit: 'warning', push: 'block', ci: 'fail' },
    },
    documentation: {
      description: 'Documentation quality violations',
      enforcement_levels: { commit: 'warning', push: 'warning', ci: 'block' },
    },
    code_freeze: {
      description: 'Document freeze',
      enforcement_levels: { commit: 'block', push: 'fail', ci: 'fail' },
    },
  },
  global_overrides: {},
  exceptions: [],
};

const ajv = new Ajv({ allErrors: true, strict: false });

// Add date-time format validator to eliminate warnings
ajv.addFormat('date-time', {
  validate: (dateTimeString) => {
    // Simple ISO 8601 date-time validation
    const iso8601Regex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$/;
    return typeof dateTimeString === 'string' && iso8601Regex.test(dateTimeString);
  },
});
const validateConfig = ajv.compile(EXCEPTION_SCHEMA);

/* ----------------------------- File IO (atomic + lock) ----------------------------- */

function ensureDir(p) {
  const d = path.dirname(p);
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}

function acquireLock(timeoutMs = 2000) {
  ensureDir(LOCK_PATH);
  const start = Date.now();
  while (true) {
    try {
      fs.writeFileSync(LOCK_PATH, String(process.pid), { flag: 'wx' });
      return true;
    } catch {
      if (Date.now() - start > timeoutMs) return false;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 25);
    }
  }
}
function releaseLock() {
  try {
    fs.unlinkSync(LOCK_PATH);
  } catch {}
}

export function loadExceptionConfig() {
  try {
    if (fs.existsSync(EXCEPTION_CONFIG_PATH)) {
      const content = fs.readFileSync(EXCEPTION_CONFIG_PATH, 'utf8');
      const parsed = JSON.parse(content);
      // lightweight migration: add schema_version if missing
      if (!parsed.schema_version) parsed.schema_version = '2.0.0';
      if (!validateConfig(parsed)) {
        // Only log validation errors once per session to avoid spam
        if (!global._qualityExceptionsValidationLogged) {
          console.warn(
            `⚠️ Invalid quality-exceptions.json: ${ajv.errorsText(validateConfig.errors, { separator: '\n' })}`
          );
          global._qualityExceptionsValidationLogged = true;
        }
        // fall back but keep parsed; don't lose data
        return { ...DEFAULT_CONFIG, ...parsed };
      }
      return parsed;
    }
  } catch (e) {
    console.warn(`⚠️ Could not load quality exceptions: ${e.message}`);
  }
  return JSON.parse(JSON.stringify(DEFAULT_CONFIG));
}

export function saveExceptionConfig(config) {
  const payload = JSON.stringify(config, null, 2);
  ensureDir(EXCEPTION_CONFIG_PATH);
  if (!validateConfig(config)) {
    console.error(
      `❌ Refusing to save invalid config:\n${ajv.errorsText(validateConfig.errors, { separator: '\n' })}`
    );
    return false;
  }
  if (!acquireLock()) {
    console.error('❌ Could not acquire exceptions lock; try again.');
    return false;
  }
  try {
    const tmp = EXCEPTION_CONFIG_PATH + '.tmp';
    fs.writeFileSync(tmp, payload);
    fs.renameSync(tmp, EXCEPTION_CONFIG_PATH);
    return true;
  } catch (e) {
    console.error(`❌ Error saving config: ${e.message}`);
    return false;
  } finally {
    releaseLock();
  }
}

/* ----------------------------- Context & matching ----------------------------- */

function currentContext() {
  return process.env.CAWS_ENFORCEMENT_CONTEXT || 'commit';
}
function currentBranch() {
  try {
    return execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { encoding: 'utf8' }).trim();
  } catch {
    return '';
  }
}
function currentAuthorEmail() {
  try {
    return execFileSync('git', ['config', 'user.email'], { encoding: 'utf8' }).trim();
  } catch {
    return '';
  }
}
function inCI() {
  return !!process.env.CI;
}

function matchFilePattern(fileRel, pattern) {
  if (!pattern) return true;
  return micromatch.isMatch(fileRel, pattern, { dot: true });
}
function matchType(violationType, expect) {
  if (!expect) return true;
  return violationType === expect;
}
function matchMessageRegex(message, regexStr) {
  if (!regexStr) return true;
  try {
    const rx = new RegExp(regexStr, 'i');
    return rx.test(message || '');
  } catch {
    return false;
  }
}
function matchBranch(branch, pattern) {
  if (!pattern) return true;
  return micromatch.isMatch(branch, pattern);
}
function matchAuthor(email, pattern) {
  if (!pattern) return true;
  return micromatch.isMatch(email, pattern);
}
function withinTimeWindow(now, effective_from, expires_at) {
  if (effective_from && new Date(now) < new Date(effective_from)) return false;
  if (expires_at && new Date(now) > new Date(expires_at)) return false;
  return true;
}

/* Budgets: supports numeric fields on violation:
   - size (absolute), delta (relative), score (generic)
   Exception can carry:
   - size_threshold (max size)
   - delta_budget (max allowed growth)
   - max_hits (cap exception use count) */
function checkBudgets(violation, ex) {
  if (typeof ex.size_threshold === 'number' && typeof violation.size === 'number') {
    if (violation.size > ex.size_threshold) return false;
  }
  if (typeof ex.delta_budget === 'number' && typeof violation.delta === 'number') {
    if (violation.delta > ex.delta_budget) return false;
  }
  if (
    typeof ex.max_hits === 'number' &&
    typeof ex.hits === 'number' &&
    violation.hits > ex.max_hits
  ) {
    return false;
  }
  return true;
}

/* ----------------------------- Enforcement resolution ----------------------------- */

/**
 * Gets the enforcement level for a gate in the given context.
 *
 * Enforcement levels determine how violations are handled:
 * - 'warning': Violations are reported but don't block commits
 * - 'block': Violations block commits locally
 * - 'fail': Violations cause CI/CD to fail
 *
 * Priority resolution:
 * 1. Global overrides (e.g., code freeze)
 * 2. Gate-specific enforcement_levels[context]
 * 3. Default: 'fail' (strictest)
 *
 * @param {string} gateName - Name of the gate (e.g., 'naming', 'duplication')
 * @param {'commit'|'push'|'ci'} [context=currentContext()] - Execution context
 * @returns {'warning'|'block'|'fail'} Enforcement level for this gate/context combination
 */
export function getEnforcementLevel(gateName, context = currentContext()) {
  const config = loadExceptionConfig();
  const gate = config.gates?.[gateName];
  const fallback = 'fail';

  // Global overrides (e.g., code freeze)
  const freeze = config.global_overrides?.code_freeze;
  if (freeze?.enabled) {
    const applies = !freeze.gates || freeze.gates.includes('*') || freeze.gates.includes(gateName);
    if (applies) return freeze.level || 'fail';
  }

  if (!gate) return fallback;
  return gate.enforcement_levels?.[context] || fallback;
}

/* ----------------------------- Exception matching ----------------------------- */

export function isException(gateName, violation, context = currentContext()) {
  const config = loadExceptionConfig();
  const now = new Date();
  const branch = currentBranch();
  const author = currentAuthorEmail();
  const ci = inCI();
  const fileRel = toRepoRel(violation.file);

  for (const ex of config.exceptions) {
    if (ex.gate !== gateName) continue;

    // context constraint
    if (ex.context && ex.context !== 'all' && ex.context !== context) continue;
    if (ex.ci_only && !ci) continue;

    if (!withinTimeWindow(now, ex.effective_from, ex.expires_at)) {
      // expired or not yet effective
      if (new Date(now) > new Date(ex.expires_at)) {
        return { valid: false, reason: 'expired', exception: ex };
      }
      continue;
    }

    // matching predicates
    const matches =
      matchFilePattern(fileRel, ex.file_pattern) &&
      matchType(violation.type, ex.violation_type) &&
      matchMessageRegex(violation.message || violation.issue, ex.message_regex) &&
      matchBranch(branch, ex.branch) &&
      matchAuthor(author, ex.author_email) &&
      checkBudgets(violation, ex);

    if (!matches) continue;

    // Track hits in-memory; caller can persist by saveExceptionConfig if desired via addHit
    return { valid: true, exception: ex, context, repoRelativeFile: fileRel };
  }
  return { valid: false };
}

function toRepoRel(p) {
  if (!p) return '';
  const root = PROJECT_ROOT;
  const abs = path.isAbsolute(p) ? p : path.join(root, p);
  const rel = path.relative(root, abs);
  return rel.split(path.sep).join('/');
}

/* ----------------------------- Mutations ----------------------------- */

function nowIso() {
  return new Date().toISOString();
}

function nextId() {
  return 'ex_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10);
}

export function addException(gateName, exceptionData) {
  const cfg = loadExceptionConfig();
  const now = nowIso();
  const expiresAt = new Date(
    Date.now() + (exceptionData.expiresInDays ?? 180) * 24 * 60 * 60 * 1000
  ).toISOString();

  const ex = {
    id: nextId(),
    gate: gateName,
    reason: exceptionData.reason,
    approved_by: exceptionData.approvedBy,
    approved_at: now,
    expires_at: expiresAt,
    review_required: exceptionData.reviewRequired !== false,
    context: exceptionData.context ?? 'all',
    // matchers
    file_pattern: exceptionData.filePattern ?? '**/*',
    violation_type: exceptionData.violationType ?? undefined,
    message_regex: exceptionData.messageRegex ?? undefined,
    // budgets
    size_threshold: exceptionData.sizeThreshold ?? undefined,
    delta_budget: exceptionData.deltaBudget ?? undefined,
    max_hits: exceptionData.maxHits ?? undefined,
    // constraints
    branch: exceptionData.branch ?? undefined,
    author_email: exceptionData.authorEmail ?? undefined,
    ci_only: exceptionData.ciOnly ?? false,
    effective_from: exceptionData.effectiveFrom ?? now,
    // audit
    created_by: exceptionData.createdBy ?? process.env.GIT_AUTHOR_EMAIL ?? 'unknown',
    updated_at: now,
    hits: 0,
  };

  // dedupe by (gate + file_pattern + violation_type + context)
  const exists = cfg.exceptions.find(
    (e) =>
      e.gate === ex.gate &&
      e.file_pattern === ex.file_pattern &&
      (e.violation_type || '') === (ex.violation_type || '') &&
      (e.context || 'all') === (ex.context || 'all')
  );
  if (exists) {
    return {
      success: false,
      message: 'Exception already exists for this gate/pattern/context',
      existing: exists,
    };
  }

  cfg.exceptions.push(ex);
  return saveExceptionConfig(cfg)
    ? { success: true, exception: ex }
    : { success: false, message: 'Failed to save configuration' };
}

export function removeException(exceptionId) {
  const cfg = loadExceptionConfig();
  const before = cfg.exceptions.length;
  cfg.exceptions = cfg.exceptions.filter((e) => e.id !== exceptionId);
  if (cfg.exceptions.length === before)
    return { success: false, message: 'No matching exception found' };
  return saveExceptionConfig(cfg)
    ? { success: true, message: `Removed exception ${exceptionId}` }
    : { success: false, message: 'Failed to save configuration' };
}

export function renewException(exceptionId, days = 90) {
  const cfg = loadExceptionConfig();
  const ex = cfg.exceptions.find((e) => e.id === exceptionId);
  if (!ex) return { success: false, message: 'No matching exception found' };
  ex.expires_at = new Date(Date.now() + days * 86400000).toISOString();
  ex.updated_at = nowIso();
  return saveExceptionConfig(cfg)
    ? { success: true, exception: ex }
    : { success: false, message: 'Failed to save configuration' };
}

export function addHit(exceptionId) {
  const cfg = loadExceptionConfig();
  const ex = cfg.exceptions.find((e) => e.id === exceptionId);
  if (!ex) return { success: false, message: 'No matching exception found' };
  ex.hits = (ex.hits ?? 0) + 1;
  ex.updated_at = nowIso();
  return saveExceptionConfig(cfg)
    ? { success: true, hits: ex.hits }
    : { success: false, message: 'Failed to update hits' };
}

/* ----------------------------- Listing ----------------------------- */

export function listExceptions(gateName = null) {
  const cfg = loadExceptionConfig();
  const now = new Date();
  const list = gateName ? cfg.exceptions.filter((e) => e.gate === gateName) : cfg.exceptions;
  return list.map((ex) => {
    const exp = new Date(ex.expires_at);
    const status = exp <= now ? 'expired' : exp - now / 86400000 < 30 ? 'expiring' : 'active';
    return {
      ...ex,
      status,
      daysUntilExpiry: Math.max(0, Math.ceil((exp - now) / 86400000)),
    };
  });
}

/* ----------------------------- Violation processing ----------------------------- */

/**
 * @typedef {Object} RawViolation
 * @property {string} file - File path where violation occurred
 * @property {string} type - Violation type identifier
 * @property {string} [message] - Human-readable violation message
 * @property {string} [issue] - Alternative message field (for naming violations)
 * @property {number} [size] - File size in LOC (for god object violations)
 * @property {number} [delta] - Size change in LOC (for regression violations)
 * @property {string} [pattern] - Pattern that matched (for duplication)
 * @property {number} [line] - Line number where violation occurred
 * @property {string} [rule] - Rule identifier
 * @property {string} [suggestion] - Suggested fix
 */

/**
 * @typedef {Object} ProcessViolationsOptions
 * @property {Function} [defaultSeverity] - Function to determine default severity for a violation
 */

/**
 * @typedef {Object} ProcessViolationsResult
 * @property {Violation[]} violations - Processed violations with severity assigned
 * @property {Warning[]} warnings - Warnings for waived violations
 * @property {'warning'|'block'|'fail'} enforcementLevel - Effective enforcement level for this gate/context
 * @property {Object[]} appliedExceptions - Metadata about exceptions that were applied
 */

/**
 * Processes violations against active exceptions and enforcement levels.
 *
 * This is the core function that determines which violations should block commits
 * vs. which are allowed due to exceptions or enforcement level settings.
 *
 * Processing flow:
 * 1. Check each violation against active exceptions
 * 2. If exception matches, convert to warning (non-blocking)
 * 3. Assign severity based on enforcement level for gate/context
 * 4. Track applied exceptions for reporting
 *
 * Exception matching:
 * - File pattern (micromatch glob)
 * - Violation type
 * - Message regex
 * - Branch, author, CI-only constraints
 * - Budget thresholds (size, delta, max hits)
 * - Time windows (effective_from, expires_at)
 *
 * @param {string} gateName - Name of the gate (e.g., 'naming', 'duplication')
 * @param {RawViolation[]} violations - Array of raw violations to process
 * @param {'commit'|'push'|'ci'} [context=currentContext()] - Execution context
 * @param {ProcessViolationsOptions} [opts={}] - Processing options
 * @returns {ProcessViolationsResult} Processed violations with warnings and enforcement level
 */
export function processViolations(gateName, violations, context = currentContext(), opts = {}) {
  const enforcementLevel = getEnforcementLevel(gateName, context);
  const processed = [];
  const warnings = [];
  const appliedExceptions = [];

  for (const v of violations) {
    const check = isException(gateName, v, context);
    if (check.valid) {
      appliedExceptions.push({ gate: gateName, violation: v, exceptionId: check.exception.id });
      warnings.push({
        type: 'exception_used',
        gate: gateName,
        violation: v,
        exception: {
          id: check.exception.id,
          reason: check.exception.reason,
          expires_at: check.exception.expires_at,
          approved_by: check.exception.approved_by,
        },
        context,
      });
      // Optional: bump hits counter (best effort, non-blocking)
      addHit(check.exception.id);
      continue;
    }

    if (check.reason === 'expired') {
      processed.push({
        ...v,
        type: 'expired_exception',
        severity: opts.defaultSeverity?.(v) ?? enforcementLevel,
      });
      continue;
    }

    processed.push({
      ...v,
      severity: opts.defaultSeverity?.(v) ?? enforcementLevel,
    });
  }

  return { violations: processed, warnings, enforcementLevel, appliedExceptions };
}

/* ----------------------------- CLI ----------------------------- */

export function runExceptionCLI(args) {
  const cmd = args[0];
  switch (cmd) {
    case 'add': {
      if (args.length < 4) {
        console.log(
          "❌ Usage: add <gate> <reason> <approver> [filePattern='**/*'] [violationType] [days=180]"
        );
        return;
      }
      const gate = args[1],
        reason = args[2],
        approver = args[3];
      const filePattern = args[4] ?? '**/*';
      const vtype = args[5] ?? undefined;
      const days = parseInt(args[6] ?? '180', 10);
      const res = addException(gate, {
        reason,
        approvedBy: approver,
        filePattern,
        violationType: vtype,
        expiresInDays: days,
      });
      console.log(res.success ? `✅ Added ${res.exception.id}` : `❌ ${res.message}`);
      break;
    }
    case 'list': {
      const gate = args[1] ?? null;
      const list = listExceptions(gate);
      if (!list.length) {
        console.log('📋 No exceptions');
        return;
      }
      console.log(`📋 ${list.length} exception(s):`);
      for (const ex of list) {
        const icon = ex.status === 'expired' ? '🔴' : ex.status === 'expiring' ? '🟡' : '🟢';
        console.log(`${icon} [${ex.gate}] ${ex.reason}`);
        console.log(`   ID: ${ex.id}`);
        console.log(`   Pattern: ${ex.file_pattern ?? '(any)'}`);
        console.log(`   Type: ${ex.violation_type ?? '(any)'}  Context: ${ex.context ?? 'all'}`);
        console.log(`   Expires: ${ex.expires_at}  Hits: ${ex.hits ?? 0}`);
        console.log('');
      }
      break;
    }
    case 'remove': {
      if (args.length < 2) {
        console.log('❌ Usage: remove <exception-id>');
        return;
      }
      const res = removeException(args[1]);
      console.log(res.success ? `✅ ${res.message}` : `❌ ${res.message}`);
      break;
    }
    case 'renew': {
      if (args.length < 2) {
        console.log('❌ Usage: renew <exception-id> [days=90]');
        return;
      }
      const days = parseInt(args[2] ?? '90', 10);
      const res = renewException(args[1], days);
      console.log(res.success ? `✅ Renewed to ${res.exception.expires_at}` : `❌ ${res.message}`);
      break;
    }
    default:
      console.log(`
🔧 CAWS Quality Exception Manager (v2)

Usage:
  node scripts/quality-gates/shared-exception-framework.mjs <command> [options]

Commands:
  add <gate> <reason> <approver> [filePattern] [violationType] [days]   Add exception
  list [gate]                                                            List exceptions
  remove <exception-id>                                                  Remove exception
  renew <exception-id> [days]                                            Extend expiry

Notes:
  - Patterns use micromatch (glob) and are repo-relative.
  - Budgets & constraints can be edited directly in .caws/quality-exceptions.json.
`);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runExceptionCLI(process.argv.slice(2));
}
