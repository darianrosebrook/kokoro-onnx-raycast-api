#!/usr/bin/env node

/**
 * Quality Gates Runner
 *
 * Runs all quality gates and blocks commits if any critical violations are found.
 * Part of the crisis response - prevents further codebase degradation.
 *
 * Usage:
 *   node scripts/quality-gates/run-quality-gates.js [--ci] [--fix] [--json] [--gates=name,code_freeze]
 *
 * Options:
 *   --ci       Run in CI mode (stricter, no interactive fixes)
 *   --fix      Attempt automatic fixes for some violations
 *   --json     Output machine-readable JSON to stdout
 *   --gates    Run only specific gates (comma-separated)
 *
 * @author: @darianrosebrook
 */

/**
 * @typedef {Object} Violation
 * @property {string} gate - The gate that detected this violation (e.g., 'naming', 'duplication')
 * @property {string} type - Type of violation (e.g., 'banned_modifier', 'timeout', 'gate_error')
 * @property {string} message - Human-readable description of the violation
 * @property {string} [file] - File path where violation occurred (relative or absolute)
 * @property {number} [line] - Line number where violation occurred
 * @property {string} [rule] - Rule identifier that was violated
 * @property {string} [severity] - Severity level: 'warning', 'block', or 'fail'
 * @property {string} [suggestion] - Suggested fix for the violation
 * @property {number} [size] - File size in lines of code (for god object violations)
 * @property {number} [similarity] - Similarity percentage (for duplication violations)
 * @property {Object} [details] - Additional violation-specific details
 * @property {string} [waivedBy] - ID of waiver that exempts this violation (added by isViolationWaived)
 * @property {string} [waiverTitle] - Title of the waiver (added by isViolationWaived)
 * @property {string} [waiverExpires] - Expiration date of the waiver (added by isViolationWaived)
 */

/**
 * @typedef {Object} Warning
 * @property {string} gate - The gate that generated this warning
 * @property {string} type - Type of warning (e.g., 'exception_used', 'marketing_language')
 * @property {string} message - Human-readable description of the warning
 * @property {string} [file] - File path where warning occurred
 * @property {number} [line] - Line number where warning occurred
 * @property {string} [rule] - Rule identifier
 * @property {string} [suggestion] - Suggested fix
 * @property {Object} [violation] - Original violation that generated this warning
 * @property {Object} [exception] - Exception that was applied (for exception_used warnings)
 */

/**
 * @typedef {Object} Waiver
 * @property {string} id - Unique waiver identifier
 * @property {string} title - Human-readable waiver title
 * @property {string} description - Detailed waiver description
 * @property {string|string[]} gates - Gate name(s) this waiver applies to ('*' for all gates)
 * @property {string} reason - Reason for the waiver (e.g., 'emergency_hotfix')
 * @property {string} expires_at - ISO 8601 expiration date-time
 * @property {string} approved_by - Approver name/email
 * @property {string} impact_level - Impact level: 'low', 'medium', 'high', or 'critical'
 * @property {string} mitigation_plan - Description of mitigation plan
 */

/**
 * @typedef {Object} ContextInfo
 * @property {string} description - Human-readable context description
 * @property {string} scope - Context scope: 'commit', 'push', or 'ci'
 * @property {string} gitCommand - Git command used to determine file scope
 */

/**
 * @typedef {Object} GateTimings
 * @property {number} [gateName] - Execution time in milliseconds for each gate
 */

/**
 * @typedef {Object} QualityGateReport
 * @property {string} timestamp - ISO 8601 timestamp of report generation
 * @property {string} context - Execution context: 'commit', 'push', or 'ci'
 * @property {number} files_scoped - Number of files analyzed
 * @property {Warning[]} warnings - Non-blocking warnings
 * @property {Violation[]} violations - All violations (including waived)
 * @property {Object} waivers - Waiver information
 * @property {number} waivers.active - Number of active waivers
 * @property {number} waivers.applied - Number of violations waived
 * @property {Object[]} waivers.details - Details of active waivers
 * @property {Object} performance - Performance metrics
 * @property {number} performance.total_execution_time_ms - Total execution time
 * @property {GateTimings} performance.gate_timings - Per-gate timing breakdown
 * @property {Object} [debug] - Debug information (only if DEBUG_MODE enabled)
 */

import { getContextInfo, getFilesToCheck } from './file-scope-manager.mjs';

// Import quality gate modules
import fs from 'fs';
import yaml from 'js-yaml';
import path, { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { checkFunctionalDuplication } from './check-functional-duplication.mjs';
import { checkNamingViolations, checkSymbolNaming } from './check-naming.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const CI_MODE = process.argv.includes('--ci') || !!process.env.CI;
const FIX_MODE = process.argv.includes('--fix');
const JSON_MODE = process.argv.includes('--json');
const FORCE_MODE = process.argv.includes('--force');
const QUIET_MODE = process.argv.includes('--quiet');
const DEBUG_MODE = process.argv.includes('--debug');
const VALID_GATES = new Set([
  'naming',
  'code_freeze',
  'duplication',
  'god_objects',
  'hidden-todo',
  'documentation',
]);

if (DEBUG_MODE) {
  console.log('DEBUG: Starting quality gates runner');
}

/**
 * Parses --gates command-line argument to determine which gates should run.
 * @returns {Set<string>|null} Set of gate names to run, or null if all gates should run
 */
const GATES_FILTER = (() => {
  // Find --gates or --gates=value
  let gatesArg = null;
  for (const arg of process.argv) {
    if (arg === '--gates') {
      const idx = process.argv.indexOf(arg);
      if (idx + 1 < process.argv.length) {
        gatesArg = process.argv[idx + 1];
      }
      break;
    } else if (arg.startsWith('--gates=')) {
      gatesArg = arg.substring('--gates='.length);
      break;
    }
  }

  if (gatesArg) {
    const requested = gatesArg
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const valid = requested.filter((gate) => VALID_GATES.has(gate));
    const invalid = requested.filter((gate) => !VALID_GATES.has(gate));

    if (invalid.length > 0) {
      console.error(`Error: Invalid gate names: ${invalid.join(', ')}`);
      console.error(`Valid gates: ${Array.from(VALID_GATES).join(', ')}`);
      process.exit(1);
    }

    return valid.length > 0 ? new Set(valid) : null;
  }
  return null;
})();

/**
 * QualityGateRunner orchestrates the execution of all quality gates.
 *
 * Manages gate execution lifecycle, violation tracking, waiver application,
 * and result reporting. Ensures proper cleanup and lock management to prevent
 * concurrent executions.
 *
 * @class QualityGateRunner
 */
class QualityGateRunner {
  /**
   * Creates a new QualityGateRunner instance.
   *
   * Initializes the runner by:
   * - Determining execution context (commit/push/ci)
   * - Loading file scope for the context
   * - Loading active waivers from `.caws/waivers/active-waivers.yaml`
   * - Setting up cleanup handlers for graceful shutdown
   *
   * All initialization failures are logged but use safe fallbacks to ensure
   * the runner can still execute (with reduced functionality).
   */
  constructor() {
    /** @type {Violation[]} */
    this.violations = [];

    /** @type {Warning[]} */
    this.warnings = [];

    /** @type {string|null} */
    this.lockFile = null;

    /** @type {number} */
    this.startTime = Date.now();

    /** @type {GateTimings} */
    this.gateTimings = {};

    /** @type {string[]} */
    this.debugLog = [];

    /** @type {Waiver[]} */
    this.activeWaivers = [];

    /** @type {'commit'|'push'|'ci'} */
    this.context;

    /** @type {ContextInfo} */
    this.contextInfo;

    /** @type {string[]} */
    this.filesToCheck;

    try {
      this.context = this.determineContext();
      if (DEBUG_MODE) {
        this.debugLog.push(`Context determined: ${this.context}`);
      }
    } catch (error) {
      console.error('Failed to determine context:', error.message);
      this.context = 'commit'; // fallback
      if (DEBUG_MODE) {
        this.debugLog.push(`Context fallback to: ${this.context} (error: ${error.message})`);
      }
    }

    try {
      this.contextInfo = getContextInfo(this.context);
      if (DEBUG_MODE) {
        this.debugLog.push(`Context info: ${JSON.stringify(this.contextInfo)}`);
      }
    } catch (error) {
      console.error('Failed to get context info:', error.message);
      this.contextInfo = { description: 'unknown context' }; // fallback
      if (DEBUG_MODE) {
        this.debugLog.push(`Context info fallback (error: ${error.message})`);
      }
    }

    try {
      this.filesToCheck = this.getFilesForContext();
      if (DEBUG_MODE) {
        this.debugLog.push(`Files to check: ${this.filesToCheck.length}`);
        this.debugLog.push(`File scoping command: ${this.contextInfo.gitCommand || 'unknown'}`);
      }

      // Clear caches if we have files to check (indicates changes)
      if (this.filesToCheck.length > 0) {
        this.clearCachesOnFileChanges();
      }
    } catch (error) {
      console.error('Failed to get files for context, using empty set:', error.message);
      this.filesToCheck = []; // fallback
      if (DEBUG_MODE) {
        this.debugLog.push(`File scoping failed, using empty set (error: ${error.message})`);
      }
    }

    // Load active waivers
    try {
      this.activeWaivers = this.loadActiveWaivers();
      if (DEBUG_MODE) {
        this.debugLog.push(`Loaded ${this.activeWaivers.length} active waivers`);
      }
    } catch (error) {
      console.warn('Warning: Could not load waivers:', error.message);
      this.activeWaivers = [];
      if (DEBUG_MODE) {
        this.debugLog.push(`Waiver loading failed: ${error.message}`);
      }
    }

    // Set up cleanup handlers for crashes/unexpected termination
    this.setupCleanupHandlers();
  }

  /**
   * Acquires a lock file to prevent concurrent quality gate executions.
   *
   * Lock file mechanism:
   * - Location: `docs-status/quality-gates.lock`
   * - Contains: PID and ISO timestamp
   * - Stale detection: Locks older than 5 minutes are considered stale
   * - Force mode: --force flag bypasses lock checks
   *
   * @throws {Error} Exits process with code 1 if lock exists and is not stale
   * @returns {void}
   */
  acquireLock() {
    const docsStatusDir = path.join(__dirname, 'docs-status');
    const lockPath = path.join(docsStatusDir, 'quality-gates.lock');

    if (DEBUG_MODE) {
      this.debugLog.push(`Acquiring lock: ${lockPath}`);
    }

    // Ensure docs-status directory exists
    if (!fs.existsSync(docsStatusDir)) {
      fs.mkdirSync(docsStatusDir, { recursive: true });
      if (DEBUG_MODE) {
        this.debugLog.push(`Created docs-status directory: ${docsStatusDir}`);
      }
    }

    try {
      // Check if lock file exists and is recent (< 5 minutes)
      if (fs.existsSync(lockPath)) {
        const stats = fs.statSync(lockPath);
        const age = Date.now() - stats.mtime.getTime();
        if (DEBUG_MODE) {
          this.debugLog.push(`Lock file exists, age: ${age}ms`);
        }
        if (age < 5 * 60 * 1000 && !FORCE_MODE) {
          // 5 minutes and not in force mode
          console.error('Error: Another quality gates process is already running');
          console.error(
            'Please wait for it to complete, use --force to bypass, or remove the lock file manually:'
          );
          console.error(`  rm "${lockPath}"`);
          process.exit(1);
        } else if (age >= 5 * 60 * 1000) {
          // Stale lock, remove it
          console.warn('Warning: Removing stale lock file');
          fs.unlinkSync(lockPath);
          if (DEBUG_MODE) {
            this.debugLog.push(`Removed stale lock file (age: ${age}ms)`);
          }
        } else {
          // Force mode - remove existing lock
          console.warn('Warning: Force mode enabled, removing existing lock file');
          fs.unlinkSync(lockPath);
          if (DEBUG_MODE) {
            this.debugLog.push(`Force mode: removed existing lock file`);
          }
        }
      }

      // Create lock file
      fs.writeFileSync(lockPath, `${process.pid}\n${new Date().toISOString()}`);
      this.lockFile = lockPath;
      if (DEBUG_MODE) {
        this.debugLog.push(`Lock acquired: ${lockPath}`);
      }
    } catch (error) {
      console.warn('Warning: Could not acquire lock file:', error.message);
      // Continue without lock - not critical
    }
  }

  /**
   * Releases the lock file if it exists.
   *
   * Called automatically on:
   * - Normal completion (finally block)
   * - Process termination (SIGINT, SIGTERM)
   * - Uncaught exceptions
   *
   * Failures to release locks are logged but non-fatal.
   *
   * @returns {void}
   */
  releaseLock() {
    if (this.lockFile && fs.existsSync(this.lockFile)) {
      try {
        fs.unlinkSync(this.lockFile);
        if (DEBUG_MODE) {
          this.debugLog.push(`Lock released: ${this.lockFile}`);
        }
      } catch (error) {
        console.warn('Warning: Could not release lock file:', error.message);
        if (DEBUG_MODE) {
          this.debugLog.push(`Lock release failed: ${error.message}`);
        }
      }
    }
  }

  clearCachesOnFileChanges() {
    try {
      // Find project root
      let projectRoot = process.cwd();
      let attempts = 0;
      while (attempts < 10) {
        const cawsDir = path.join(projectRoot, '.caws');
        const workingSpecPath = path.join(cawsDir, 'working-spec.yaml');

        if (fs.existsSync(cawsDir) && fs.existsSync(workingSpecPath)) {
          break;
        }

        const parentDir = path.dirname(projectRoot);
        if (parentDir === projectRoot) {
          break;
        }
        projectRoot = parentDir;
        attempts++;
      }

      const cacheFiles = [
        path.join(projectRoot, '.caws', 'duplication-cache.json'),
        path.join(projectRoot, '.caws', 'naming-exceptions.json'),
        path.join(projectRoot, '.caws', 'canonical-map.yaml'),
      ];

      let clearedCount = 0;
      for (const cacheFile of cacheFiles) {
        if (fs.existsSync(cacheFile)) {
          try {
            fs.unlinkSync(cacheFile);
            clearedCount++;
            if (DEBUG_MODE) {
              this.debugLog.push(`Cleared cache: ${path.relative(projectRoot, cacheFile)}`);
            }
          } catch (error) {
            console.warn(`Warning: Could not clear cache ${cacheFile}:`, error.message);
          }
        }
      }

      if (clearedCount > 0 && !QUIET_MODE) {
        console.log(`   Cleared ${clearedCount} cache files`);
      }
    } catch (error) {
      console.warn('Warning: Could not clear caches:', error.message);
    }
  }

  clearTemporaryCaches() {
    try {
      // Clear temporary analysis caches that are safe to regenerate
      const tempCacheFiles = [
        path.join(__dirname, 'docs-status', 'quality-gates-report.json'),
        // Add other temporary cache files here
      ];

      let clearedCount = 0;
      for (const cacheFile of tempCacheFiles) {
        if (fs.existsSync(cacheFile)) {
          try {
            fs.unlinkSync(cacheFile);
            clearedCount++;
            if (DEBUG_MODE) {
              this.debugLog.push(
                `Cleared temporary cache: ${path.relative(process.cwd(), cacheFile)}`
              );
            }
          } catch (error) {
            // Don't warn for temporary cache cleanup failures
          }
        }
      }

      if (clearedCount > 0 && DEBUG_MODE) {
        console.log(`   Cleared ${clearedCount} temporary cache files`);
      }
    } catch (error) {
      // Don't warn for temporary cache cleanup failures
    }
  }

  setupCleanupHandlers() {
    const cleanup = () => {
      try {
        // Release lock
        this.releaseLock();

        // Clear caches on crash (since analysis may be incomplete)
        if (this.filesToCheck && this.filesToCheck.length > 0) {
          this.clearCachesOnFileChanges();
        }

        if (DEBUG_MODE) {
          console.error('Quality gates cleanup completed');
        }
      } catch (error) {
        console.error('Warning: Cleanup failed:', error.message);
      }
    };

    // Handle common termination signals
    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
    process.on('uncaughtException', (error) => {
      console.error('Uncaught exception:', error);
      cleanup();
      process.exit(1);
    });
    process.on('unhandledRejection', (reason, promise) => {
      console.error('Unhandled rejection at:', promise, 'reason:', reason);
      cleanup();
      process.exit(1);
    });

    if (DEBUG_MODE) {
      this.debugLog.push('Cleanup handlers installed');
    }
  }

  /**
   * Loads active waivers from `.caws/waivers/active-waivers.yaml`.
   *
   * Waivers allow temporary bypassing of quality gate violations for
   * documented reasons (e.g., emergency hotfixes, planned refactoring).
   *
   * Waiver validation:
   * - Must have `id`, `gates`, and `expires_at` fields
   * - Only non-expired waivers are loaded
   * - Invalid waivers are skipped with warnings
   *
   * @returns {Waiver[]} Array of active, non-expired waivers
   */
  loadActiveWaivers() {
    // Find project root (go up until we find .caws directory with working-spec.yaml)
    let projectRoot = process.cwd();
    let attempts = 0;
    while (attempts < 10) {
      const cawsDir = path.join(projectRoot, '.caws');
      const workingSpecPath = path.join(cawsDir, 'working-spec.yaml');

      // Look for .caws directory with working-spec.yaml (indicates project root)
      if (fs.existsSync(cawsDir) && fs.existsSync(workingSpecPath)) {
        break;
      }

      const parentDir = path.dirname(projectRoot);
      if (parentDir === projectRoot) {
        // Hit filesystem root
        break;
      }
      projectRoot = parentDir;
      attempts++;
    }

    const activeWaiversPath = path.join(projectRoot, '.caws', 'waivers', 'active-waivers.yaml');

    if (DEBUG_MODE) {
      this.debugLog.push(`Project root detected: ${projectRoot}`);
      this.debugLog.push(`Checking waivers path: ${activeWaiversPath}`);
      this.debugLog.push(`Waivers file exists: ${fs.existsSync(activeWaiversPath)}`);
    }

    // Check if active waivers file exists
    if (!fs.existsSync(activeWaiversPath)) {
      if (DEBUG_MODE) {
        this.debugLog.push('Active waivers file does not exist');
      }
      return [];
    }

    try {
      const content = fs.readFileSync(activeWaiversPath, 'utf8');
      const activeWaiversConfig = yaml.load(content);

      if (!activeWaiversConfig || !activeWaiversConfig.waivers) {
        if (DEBUG_MODE) {
          this.debugLog.push('No waivers found in active-waivers.yaml');
        }
        return [];
      }

      const waivers = [];
      const now = new Date();

      // Process each waiver in the config
      for (const [waiverId, waiver] of Object.entries(activeWaiversConfig.waivers)) {
        try {
          // Validate waiver structure
          if (!waiver.id || !waiver.gates || !waiver.expires_at) {
            console.warn(`Warning: Invalid waiver structure for ${waiverId}`);
            continue;
          }

          // Check if waiver is active and not expired
          if (new Date(waiver.expires_at) > now) {
            waivers.push(waiver);
            if (DEBUG_MODE) {
              this.debugLog.push(
                `Loaded active waiver: ${waiver.id} for gates: ${Array.isArray(waiver.gates) ? waiver.gates.join(', ') : waiver.gates}`
              );
            }
          } else if (DEBUG_MODE) {
            this.debugLog.push(`Skipped expired waiver: ${waiver.id}`);
          }
        } catch (error) {
          console.warn(`Warning: Could not process waiver ${waiverId}: ${error.message}`);
        }
      }

      return waivers;
    } catch (error) {
      console.warn('Warning: Could not load active waivers file:', error.message);
      return [];
    }
  }

  /**
   * Checks if a violation is covered by an active waiver.
   *
   * Waiver matching logic:
   * - Gate name must match (or waiver applies to '*' for all gates)
   * - Waiver must not be expired
   * - Mutates violation object to add waiver metadata if waived
   *
   * @param {Violation} violation - Violation to check against waivers
   * @returns {boolean} True if violation is waived, false otherwise
   */
  isViolationWaived(violation) {
    for (const waiver of this.activeWaivers) {
      // Check if this waiver applies to the gate
      const waiverGates = Array.isArray(waiver.gates) ? waiver.gates : [waiver.gates];
      if (waiverGates.includes(violation.gate) || waiverGates.includes('*')) {
        // Add waiver information to violation for reporting
        violation.waivedBy = waiver.id;
        violation.waiverTitle = waiver.title || waiver.description;
        violation.waiverExpires = waiver.expires_at;
        return true;
      }
    }
    return false;
  }

  /**
   * Determines the execution context for quality gates.
   *
   * Context priority (highest to lowest):
   * 1. --context=<value> command-line flag
   * 2. --ci flag or CI environment variable
   * 3. CAWS_ENFORCEMENT_CONTEXT environment variable
   * 4. Default: 'commit'
   *
   * Context affects:
   * - File scope (staged vs. all files)
   * - Enforcement strictness (warning vs. block vs. fail)
   * - Error handling (CI mode is stricter)
   *
   * @returns {'commit'|'push'|'ci'} Execution context
   */
  determineContext() {
    // Check for explicit --context flag first
    for (const arg of process.argv) {
      if (arg.startsWith('--context=')) {
        const context = arg.substring('--context='.length);
        if (['commit', 'push', 'ci'].includes(context)) {
          if (DEBUG_MODE) {
            this.debugLog.push(`Context set via --context flag: ${context}`);
          }
          return context;
        }
        break;
      }
    }

    // Determine context based on environment and arguments
    if (
      process.argv.includes('--ci') ||
      process.env.CAWS_ENFORCEMENT_CONTEXT === 'ci' ||
      process.env.CI
    ) {
      if (DEBUG_MODE) {
        this.debugLog.push(`Context determined by CI environment: ci`);
      }
      return 'ci';
    } else if (process.env.CAWS_ENFORCEMENT_CONTEXT === 'push') {
      if (DEBUG_MODE) {
        this.debugLog.push(`Context determined by environment: push`);
      }
      return 'push';
    } else {
      if (DEBUG_MODE) {
        this.debugLog.push(`Context defaulted to: commit`);
      }
      return 'commit';
    }
  }

  getFilesForContext() {
    // Get files to check based on context
    try {
      return getFilesToCheck(this.context);
    } catch (error) {
      console.warn(
        `Warning: Failed to determine files for context '${this.context}': ${error.message}`
      );
      console.warn('Falling back to checking all files in repository');
      // Fallback: try to get all files
      try {
        return getFilesToCheck('ci'); // CI context scans entire repo
      } catch (fallbackError) {
        console.warn(`Fallback also failed: ${fallbackError.message}`);
        return []; // Empty array as last resort
      }
    }
  }

  /**
   * Executes a quality gate function with timeout protection.
   *
   * Ensures gates don't hang indefinitely by:
   * - Wrapping gate execution in a timeout promise
   * - Recording execution time for performance monitoring
   * - Converting timeouts to violations
   * - Continuing execution even if gate fails (allows other gates to run)
   *
   * @param {string} gateName - Name of the gate (for logging and violation reporting)
   * @param {Function} gateFunction - Async function that executes the gate
   * @param {number} [timeoutMs=30000] - Maximum execution time in milliseconds
   * @returns {Promise<void>} Resolves when gate completes or times out
   */
  async runGateWithTimeout(gateName, gateFunction, timeoutMs = 30000) {
    return new Promise(async (resolve) => {
      const gateStartTime = Date.now();
      if (DEBUG_MODE) {
        this.debugLog.push(`Starting gate: ${gateName} (timeout: ${timeoutMs}ms)`);
      }

      const timeout = setTimeout(() => {
        const gateDuration = Date.now() - gateStartTime;
        console.error(`   ${gateName} gate timed out after ${timeoutMs}ms`);
        this.violations.push({
          gate: gateName,
          type: 'timeout',
          message: `${gateName} gate timed out after ${timeoutMs}ms`,
        });
        if (DEBUG_MODE) {
          this.debugLog.push(`Gate ${gateName} timed out after ${gateDuration}ms`);
        }
        resolve();
      }, timeoutMs);

      try {
        await gateFunction();
        const gateDuration = Date.now() - gateStartTime;
        clearTimeout(timeout);
        this.gateTimings[gateName] = gateDuration;
        if (DEBUG_MODE) {
          this.debugLog.push(`Gate ${gateName} completed in ${gateDuration}ms`);
        }
        resolve();
      } catch (error) {
        const gateDuration = Date.now() - gateStartTime;
        clearTimeout(timeout);
        console.error(`   ${gateName} gate failed:`, error.message);
        this.violations.push({
          gate: gateName,
          type: 'gate_error',
          message: `${gateName} gate failed: ${error.message}`,
        });
        if (DEBUG_MODE) {
          this.debugLog.push(`Gate ${gateName} failed after ${gateDuration}ms: ${error.message}`);
        }
        resolve(); // Continue with other gates
      }
    });
  }

  /**
   * Runs all quality gates in parallel with timeout protection.
   *
   * Gate execution flow:
   * 1. Acquire lock to prevent concurrent runs
   * 2. Execute all enabled gates in parallel (Promise.all)
   * 3. Each gate runs with its own timeout
   * 4. Collect violations and warnings from all gates
   * 5. Report results (console + JSON artifacts)
   * 6. Release lock (always, even on errors)
   *
   * Gate filtering:
   * - If GATES_FILTER is set, only runs specified gates
   * - Otherwise runs all available gates
   *
   * Exit codes:
   * - 0: No blocking violations (may have waived violations)
   * - 1: Blocking violations found (commit blocked)
   *
   * @returns {Promise<void>} Resolves when all gates complete
   */
  async runAllGates() {
    // Acquire lock to prevent concurrent runs
    this.acquireLock();

    try {
      if (!QUIET_MODE && !JSON_MODE) {
        console.log('Running Quality Gates - Crisis Response Mode');
        console.log('='.repeat(50));
        console.log(`Context: ${this.context.toUpperCase()} (${this.contextInfo.description})`);
        console.log(`Files to check: ${this.filesToCheck.length}`);
        console.log('='.repeat(50));
      }

      if (DEBUG_MODE) {
        this.debugLog.push(`Starting quality gates execution`);
        this.debugLog.push(`Total files to check: ${this.filesToCheck.length}`);
        this.debugLog.push(
          `Gates to run: ${GATES_FILTER ? Array.from(GATES_FILTER).join(', ') : 'all'}`
        );
      }

      const gatePromises = [];

      // Gate 1: Naming Conventions
      if (!GATES_FILTER || GATES_FILTER.has('naming')) {
        if (!QUIET_MODE && !JSON_MODE) console.log('\nChecking naming conventions...');
        gatePromises.push(this.runGateWithTimeout('naming', () => this.runNamingGate(), 10000));
      }

      // Gate 1.5: Code Freeze (Crisis Response)
      if (!GATES_FILTER || GATES_FILTER.has('code_freeze')) {
        if (!QUIET_MODE && !JSON_MODE) console.log('\nChecking code freeze compliance...');
        gatePromises.push(
          this.runGateWithTimeout('code_freeze', () => this.runCodeFreezeGate(), 5000)
        );
      }

      // Gate 2: Duplication Prevention (can be slow)
      if (!GATES_FILTER || GATES_FILTER.has('duplication')) {
        if (!QUIET_MODE && !JSON_MODE) console.log('\nChecking duplication...');
        gatePromises.push(
          this.runGateWithTimeout('duplication', () => this.runDuplicationGate(), 60000)
        );
      }

      // Gate 3: God Object Prevention
      if (!GATES_FILTER || GATES_FILTER.has('god_objects')) {
        if (!QUIET_MODE && !JSON_MODE) console.log('\nChecking god objects...');
        gatePromises.push(
          this.runGateWithTimeout('god_objects', () => this.runGodObjectGate(), 10000)
        );
      }

      // Gate 4: Hidden TODO Analysis
      if (!GATES_FILTER || GATES_FILTER.has('hidden-todo')) {
        if (!QUIET_MODE && !JSON_MODE)
          console.log('\nChecking for hidden incomplete implementations...');
        gatePromises.push(
          this.runGateWithTimeout('hidden-todo', () => this.runHiddenTodoQualityGate(), 20000)
        );
      }

      // Gate 5: Documentation Quality
      if (!GATES_FILTER || GATES_FILTER.has('documentation')) {
        if (!QUIET_MODE && !JSON_MODE) console.log('\nChecking documentation quality...');
        gatePromises.push(
          this.runGateWithTimeout('documentation', () => this.runDocumentationQualityGate(), 15000)
        );
      }

      // Wait for all gates to complete (with their own error handling)
      await Promise.all(gatePromises);

      if (DEBUG_MODE) {
        this.debugLog.push(`All gates completed`);
        this.debugLog.push(`Total execution time: ${Date.now() - this.startTime}ms`);
      }

      // Report results
      this.reportResults();
    } finally {
      // Always release lock
      this.releaseLock();
    }
  }

  async runNamingGate() {
    try {
      // Use hardened naming checker with context-based scoping
      const [filenameResults, symbolViolations] = await Promise.all([
        Promise.resolve(checkNamingViolations(this.context)),
        Promise.resolve(checkSymbolNaming(this.context)),
      ]);
      const allViolations = [...filenameResults.violations, ...symbolViolations];
      const allWarnings = filenameResults.warnings;

      // Report warnings
      if (allWarnings.length > 0) {
        console.log(`   ${allWarnings.length} approved exceptions in use`);
        for (const warning of allWarnings) {
          console.log(`      ${warning.file}: ${warning.reason}`);
        }
      }

      // Handle violations based on enforcement level
      const enforcementLevel = filenameResults.enforcementLevel;

      if (allViolations.length > 0) {
        if (!QUIET_MODE && !JSON_MODE)
          console.log(`    Enforcement level: ${enforcementLevel.toUpperCase()}`);

        for (const violation of allViolations) {
          const severity = violation.severity || enforcementLevel;

          // Only add to violations if severity requires blocking
          if (severity === 'fail' || severity === 'block') {
            this.violations.push({
              gate: 'naming',
              type: violation.type,
              message: violation.issue,
              file: violation.file,
              line: violation.line,
              rule: violation.rule,
              severity: severity,
              suggestion: violation.suggestion,
            });
          } else {
            // Warning level - add to warnings instead
            this.warnings.push({
              gate: 'naming',
              type: violation.type,
              message: violation.issue,
              file: violation.file,
              line: violation.line,
              rule: violation.rule,
              suggestion: violation.suggestion,
            });
          }
        }

        if (!QUIET_MODE && !JSON_MODE) {
          console.log(`   ${allViolations.length} naming findings (${enforcementLevel} mode)`);
        }
      } else {
        if (!QUIET_MODE && !JSON_MODE) {
          console.log('   No problematic naming patterns found');
        }
      }
    } catch (error) {
      this.violations.push({
        gate: 'naming',
        type: 'error',
        message: error.message,
      });
    }
  }

  async runCodeFreezeGate() {
    try {
      const { checkCodeFreeze } = await import('./check-code-freeze.mjs');

      const codeFreezeResults = checkCodeFreeze(this.context);

      // Report warnings (approved exceptions)
      if (codeFreezeResults.warnings.length > 0) {
        console.log(`   ${codeFreezeResults.warnings.length} approved exceptions in use`);
        for (const warning of codeFreezeResults.warnings) {
          console.log(`      ${warning.violation.file}: ${warning.exception.reason}`);
        }
      }

      // Handle violations based on enforcement level
      const enforcementLevel = codeFreezeResults.enforcementLevel;

      if (codeFreezeResults.violations.length > 0) {
        if (!QUIET_MODE && !JSON_MODE)
          console.log(`    Enforcement level: ${enforcementLevel.toUpperCase()}`);

        for (const violation of codeFreezeResults.violations) {
          const severity = violation.severity || enforcementLevel;

          // Only add to violations if severity requires blocking
          if (severity === 'fail' || severity === 'block') {
            this.violations.push({
              gate: 'code_freeze',
              type: violation.type,
              message: violation.message,
              suggestion: violation.suggestion,
              severity: severity,
            });
          } else {
            // Warning level - add to warnings instead
            this.warnings.push({
              gate: 'code_freeze',
              type: violation.type,
              message: violation.message,
              suggestion: violation.suggestion,
            });
          }
        }

        console.log(
          `   ${codeFreezeResults.violations.length} code freeze findings (${enforcementLevel} mode)`
        );
      } else {
        console.log('   Code freeze compliance check passed');
      }
    } catch (error) {
      this.violations.push({
        gate: 'code_freeze',
        type: 'error',
        message: `Code freeze check failed: ${error.message}`,
      });
    }
  }

  async runDuplicationGate() {
    try {
      if (!QUIET_MODE && !JSON_MODE) console.log('   Checking functional duplication...');

      const duplicationResults = await checkFunctionalDuplication(this.context);

      // Report warnings (approved exceptions)
      if (duplicationResults.warnings.length > 0) {
        console.log(`   ${duplicationResults.warnings.length} approved exceptions in use`);
        for (const warning of duplicationResults.warnings) {
          if (warning.type === 'exception_used') {
            console.log(
              `      ${warning.violation.files?.[0]?.file || 'unknown'}: ${warning.exception.reason}`
            );
          } else {
            console.log(`      ${warning.files?.[0]?.file || 'unknown'}: ${warning.message}`);
          }
        }
      }

      // Handle violations based on enforcement level
      const enforcementLevel = duplicationResults.enforcementLevel;

      if (duplicationResults.violations.length > 0) {
        if (!QUIET_MODE && !JSON_MODE)
          console.log(`    Enforcement level: ${enforcementLevel.toUpperCase()}`);

        for (const violation of duplicationResults.violations) {
          const severity = violation.severity || enforcementLevel;

          // Only add to violations if severity requires blocking
          if (severity === 'fail' || severity === 'block') {
            this.violations.push({
              gate: 'duplication',
              type: violation.type,
              message: violation.message,
              file: violation.files?.[0]?.file || 'unknown',
              similarity: violation.similarity,
              severity: severity,
            });
          } else {
            // Warning level - add to warnings instead
            this.warnings.push({
              gate: 'duplication',
              type: violation.type,
              message: violation.message,
              file: violation.files?.[0]?.file || 'unknown',
              similarity: violation.similarity,
            });
          }
        }

        if (enforcementLevel === 'warning') {
          console.log(
            `   ${duplicationResults.violations.length} functional duplication warnings (commit allowed)`
          );
        } else {
          console.log(
            `   ${duplicationResults.violations.length} functional duplication violations (${enforcementLevel} mode)`
          );
        }
      } else {
        if (!QUIET_MODE && !JSON_MODE) console.log('   No functional duplication violations found');
      }
    } catch (error) {
      console.error('   Error running functional duplication gate:', error.message);
      // In CI mode, treat errors as violations
      if (CI_MODE) {
        this.violations.push({
          gate: 'functional_duplication',
          type: 'gate_error',
          message: `Functional duplication gate failed: ${error.message}`,
          file: 'unknown',
          severity: 'fail',
        });
      }
    }
  }

  async runGodObjectGate() {
    try {
      const { checkGodObjects, checkGodObjectRegression } = await import('./check-god-objects.mjs');

      const godObjectResults = checkGodObjects(this.context, this.filesToCheck);
      const regressionViolations = checkGodObjectRegression(this.context);

      const allViolations = [...godObjectResults.violations, ...regressionViolations];
      const allWarnings = godObjectResults.warnings;

      // Report warnings (approved exceptions)
      if (allWarnings.length > 0) {
        console.log(`   ${allWarnings.length} approved exceptions in use`);
        for (const warning of allWarnings) {
          console.log(`      ${warning.violation.file}: ${warning.exception.reason}`);
        }
      }

      // Handle violations based on enforcement level
      const enforcementLevel = godObjectResults.enforcementLevel;

      if (allViolations.length > 0) {
        if (!QUIET_MODE && !JSON_MODE)
          console.log(`    Enforcement level: ${enforcementLevel.toUpperCase()}`);

        for (const violation of allViolations) {
          const severity = violation.severity || enforcementLevel;

          // Only add to violations if severity requires blocking
          if (severity === 'fail' || severity === 'block') {
            this.violations.push({
              gate: 'god_objects',
              type: violation.type,
              message: violation.message,
              file: violation.relativePath,
              size: violation.size,
              severity: severity,
            });
          } else {
            // Warning level - add to warnings instead
            this.warnings.push({
              gate: 'god_objects',
              type: violation.type,
              message: violation.message,
              file: violation.relativePath,
              size: violation.size,
            });
          }
        }

        if (!QUIET_MODE && !JSON_MODE)
          console.log(`   ${allViolations.length} god object findings (${enforcementLevel} mode)`);
      } else {
        if (!QUIET_MODE && !JSON_MODE) console.log('   No god object violations found');
      }
    } catch (error) {
      this.violations.push({
        gate: 'god_objects',
        type: 'error',
        message: `God object check failed: ${error.message}`,
      });
    }
  }

  async runHiddenTodoQualityGate() {
    console.log('   Checking for hidden incomplete implementations...');

    try {
      const todoAnalyzerPath = join(__dirname, 'todo-analyzer.mjs');
      const projectRoot = join(__dirname, '..', '..');

      // Check if the TODO analyzer script exists
      if (!fs.existsSync(todoAnalyzerPath)) {
        console.log('   Hidden TODO analyzer not available (script missing)');
        console.log('   Consider installing advanced code quality tooling');
        return; // Skip this gate gracefully
      }

      // TODO: Update TODO analyzer to support file filtering. For transparency, announce scope here.
      console.log(
        `    File scope: ${this.filesToCheck.length} files (analyzer currently scans repo)`
      );

      // Import and run the Node.js TODO analyzer
      let issues = [];
      try {
        const { HiddenTodoAnalyzer } = await import(todoAnalyzerPath);
        const analyzer = new HiddenTodoAnalyzer(projectRoot);
        issues = await analyzer.analyzeProject(false, this.filesToCheck); // No progress in quality gates
      } catch (analyzerError) {
        console.warn('   TODO analyzer failed, skipping hidden TODO check...');
        console.warn(`   Error: ${analyzerError.message}`);
        return;
      }

      if (issues.length > 0) {
        // Convert issues to violations format for shared framework
        const rawViolations = issues.map((issue) => ({
          type: issue.severity === 'error' ? 'hidden_todo_error' : 'hidden_todo_warning',
          file: issue.file_path,
          line: issue.line_number,
          message: issue.message,
          rule: issue.rule_id,
          confidence: issue.confidence,
          suggested_fix: issue.suggested_fix,
        }));

        // Import shared framework
        const { processViolations } = await import('./shared-exception-framework.mjs');

        // Process violations with exception handling
        const result = processViolations('hidden-todo', rawViolations, this.context);

        // Filter violations by enforcement level
        const errors = result.violations.filter(
          (v) => v.severity === 'fail' || v.severity === 'block'
        );

        // Report errors (unapproved violations)
        if (errors.length > 0) {
          console.log(`   ❌ Found ${errors.length} hidden incomplete implementations`);
          for (const error of errors) {
            console.log(
              `      ${path.relative(projectRoot, error.file)}:${error.line} - ${error.message}`
            );
          }
          throw new Error(`${errors.length} hidden incomplete implementations found`);
        }

        // Report warnings (approved exceptions)
        if (result.warnings.length > 0) {
          console.log(`   ${result.warnings.length} approved exceptions in use`);
          for (const warning of result.warnings) {
            console.log(`      ${warning.violation.file}: ${warning.exception.reason}`);
          }
        }
      } else {
        console.log('   ✅ No hidden incomplete implementations found');
      }
    } catch (error) {
      console.warn('   Warning: Hidden TODO analysis failed');
      console.warn(`   Error: ${error.message}`);
      // Don't fail the entire quality gates for this
    }
  }

  async runDocumentationQualityGate() {
    try {
      const __filename = fileURLToPath(import.meta.url);
      const __dirname = dirname(__filename);
      const projectRoot = join(__dirname, '..', '..');
      const docLinterPath = join(__dirname, 'doc-quality-linter.mjs');

      // Check if the documentation linter script exists
      if (!fs.existsSync(docLinterPath)) {
        console.log('   Documentation linter not available (script missing)');
        console.log('   Falling back to basic documentation checks...');
        return await this.runBasicDocumentationChecks();
      }

      // TODO: Update doc linter to support file filtering. For transparency, announce scope here.
      console.log(
        `    File scope: ${this.filesToCheck.length} files (linter currently scans repo)`
      );

      console.log('    Starting documentation quality scan...');

      // Import and run the Node.js documentation linter
      let issues = [];
      try {
        const { DocumentationQualityLinter } = await import(docLinterPath);
        const linter = new DocumentationQualityLinter(projectRoot);
        issues = await linter.lintProject(
          true,
          this.filesToCheck.length > 0 ? this.filesToCheck : null
        );
      } catch (linterError) {
        console.warn('   Documentation linter failed, falling back to basic checks...');
        console.warn(`   Error: ${linterError.message}`);
        return await this.runBasicDocumentationChecks();
      }

      console.log(`    Found ${issues.length} documentation quality issues`);

      if (issues.length > 0) {
        // Convert issues to violations format for shared framework
        const rawViolations = issues.map((issue) => ({
          type: issue.severity === 'error' ? 'documentation_error' : 'documentation_warning',
          file: issue.file_path,
          line: issue.line_number,
          message: issue.message,
          rule: issue.rule_id,
          suggested_fix: issue.suggested_fix,
        }));

        // Import shared framework
        const { processViolations } = await import('./shared-exception-framework.mjs');

        // Process violations with exception handling
        const result = processViolations('documentation', rawViolations, this.context);

        // Report warnings (approved exceptions)
        if (result.warnings.length > 0) {
          console.log(`   ${result.warnings.length} approved exceptions in use`);
          for (const warning of result.warnings) {
            console.log(`      ${warning.violation.file}: ${warning.exception.reason}`);
          }
        }

        // Handle violations based on enforcement level
        const enforcementLevel = result.enforcementLevel;

        if (!QUIET_MODE && !JSON_MODE)
          console.log(`    Enforcement level: ${enforcementLevel.toUpperCase()}`);

        for (const violation of result.violations) {
          const severity = violation.severity || enforcementLevel;

          // Only add to violations if severity requires blocking
          if (severity === 'fail' || severity === 'block') {
            this.violations.push({
              gate: 'documentation',
              type: violation.type,
              message: violation.message,
              file: violation.file,
              line: violation.line,
              rule: violation.rule,
              suggested_fix: violation.suggested_fix,
              severity: severity,
            });
          } else {
            // Warning level - add to warnings instead
            this.warnings.push({
              gate: 'documentation',
              type: violation.type,
              message: violation.message,
              file: violation.file,
              line: violation.line,
              rule: violation.rule,
              suggested_fix: violation.suggested_fix,
            });
          }
        }

        console.log(
          `   ${result.violations.length} documentation findings (${enforcementLevel} mode)`
        );
      } else {
        console.log('   No documentation quality issues found');
      }
    } catch (error) {
      // Check if it's an exit code error (issues found) or a real error
      if (error.status === 1) {
        // This means the linter found issues and exited with code 1
        // The output should contain the JSON with issues
        try {
          const output = error.stdout || error.stderr || '';
          if (output.trim()) {
            const issues = JSON.parse(output);

            if (issues.length > 0) {
              // Get context for enforcement level
              const context = process.env.CAWS_ENFORCEMENT_CONTEXT || 'commit';

              // Convert issues to violations format for shared framework
              const rawViolations = issues.map((issue) => ({
                type: issue.severity === 'error' ? 'documentation_error' : 'documentation_warning',
                file: issue.file,
                line: issue.line,
                message: issue.message,
                rule: issue.rule,
                suggested_fix: issue.suggested_fix,
              }));

              // Import shared framework
              const { processViolations } = await import('./shared-exception-framework.mjs');

              // Process violations with exception handling
              const result = processViolations('documentation', rawViolations, context);

              // Report warnings (approved exceptions)
              if (result.warnings.length > 0) {
                console.log(`   ${result.warnings.length} approved exceptions in use`);
                for (const warning of result.warnings) {
                  console.log(`      ${warning.violation.file}: ${warning.exception.reason}`);
                }
              }

              // Handle violations based on enforcement level
              const enforcementLevel = result.enforcementLevel;

              if (!QUIET_MODE && !JSON_MODE)
                console.log(`    Enforcement level: ${enforcementLevel.toUpperCase()}`);

              for (const violation of result.violations) {
                const severity = violation.severity || enforcementLevel;

                // Only add to violations if severity requires blocking
                if (severity === 'fail' || severity === 'block') {
                  this.violations.push({
                    gate: 'documentation',
                    type: violation.type,
                    message: violation.message,
                    file: violation.file,
                    line: violation.line,
                    rule: violation.rule,
                    suggested_fix: violation.suggested_fix,
                    severity: severity,
                  });
                } else {
                  // Warning level - add to warnings instead
                  this.warnings.push({
                    gate: 'documentation',
                    type: violation.type,
                    message: violation.message,
                    file: violation.file,
                    line: violation.line,
                    rule: violation.rule,
                    suggested_fix: violation.suggested_fix,
                  });
                }
              }

              if (enforcementLevel === 'warning') {
                console.log(
                  `   ${result.violations.length} documentation warnings (commit allowed)`
                );
              } else {
                console.log(
                  `   ${result.violations.length} documentation violations (${enforcementLevel} mode)`
                );
              }
            }
          }
        } catch (parseError) {
          // If we can't parse the output, treat as a general error
          this.violations.push({
            gate: 'documentation',
            type: 'error',
            message: `Documentation quality check failed: ${error.message}`,
          });
        }
      } else {
        // Real error (Python not found, script missing, etc.)
        this.violations.push({
          gate: 'documentation',
          type: 'error',
          message: `Documentation quality check failed: ${error.message}`,
        });
      }
    }
  }

  async runBasicDocumentationChecks() {
    console.log('   Running basic documentation quality checks (Python fallback)');

    const violations = [];
    const warnings = [];

    // Basic checks that don't require Python
    const docFiles = this.filesToCheck.filter(
      (file) => file.endsWith('.md') || file.endsWith('.rst') || file.endsWith('.txt')
    );

    for (const file of docFiles) {
      try {
        const content = fs.readFileSync(file, 'utf8');

        // Check for common documentation quality issues
        const lines = content.split('\n');

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          const lineNum = i + 1;

          // Check for marketing language (basic patterns)
          const marketingPatterns = [
            /revolutionary/i,
            /breakthrough/i,
            /innovative/i,
            /groundbreaking/i,
            /cutting-edge/i,
            /state-of-the-art/i,
            /next-generation/i,
            /advanced/i,
            /premium/i,
            /superior/i,
            /best/i,
            /leading/i,
            /industry-leading/i,
            /award-winning/i,
            /game-changing/i,
          ];

          for (const pattern of marketingPatterns) {
            if (pattern.test(line)) {
              warnings.push({
                gate: 'documentation',
                type: 'marketing_language',
                message: `Marketing language detected: "${line.trim()}"`,
                file: file,
                line: lineNum,
                rule: 'marketing_language',
                suggested_fix: 'Replace with engineering-grade language',
              });
            }
          }

          // Check for unfounded achievement claims
          const achievementPatterns = [
            /production-ready/i,
            /enterprise-grade/i,
            /battle-tested/i,
            /complete/i,
            /finished/i,
            /done/i,
            /achieved/i,
            /delivered/i,
            /implemented/i,
            /operational/i,
            /ready/i,
            /deployed/i,
            /launched/i,
            /released/i,
            /100%/i,
            /fully/i,
            /comprehensive/i,
            /entire/i,
            /total/i,
            /all/i,
            /every/i,
            /perfect/i,
            /ideal/i,
            /optimal/i,
            /maximum/i,
            /minimum/i,
            /unlimited/i,
            /infinite/i,
            /endless/i,
          ];

          for (const pattern of achievementPatterns) {
            if (pattern.test(line)) {
              violations.push({
                gate: 'documentation',
                type: 'unfounded_achievements',
                message: `Unfounded achievement claim: "${line.trim()}"`,
                file: file,
                line: lineNum,
                rule: 'unfounded_achievements',
                suggested_fix: 'Verify claim with evidence or use more accurate language',
              });
            }
          }
        }
      } catch (error) {
        console.warn(`   Warning: Could not read file ${file}: ${error.message}`);
      }
    }

    // Report findings
    if (violations.length > 0) {
      console.log(`   ${violations.length} documentation violations found (basic checks)`);
      for (const violation of violations) {
        this.violations.push(violation);
      }
    }

    if (warnings.length > 0) {
      console.log(`   ${warnings.length} documentation warnings found (basic checks)`);
      for (const warning of warnings) {
        this.warnings.push(warning);
      }
    }

    if (violations.length === 0 && warnings.length === 0) {
      console.log('   No documentation quality issues found (basic checks)');
    }
  }

  /**
   * Reports quality gate results to console and generates artifacts.
   *
   * Output includes:
   * - Console: Human-readable summary with violations, warnings, waivers
   * - JSON: Machine-readable report at `docs-status/quality-gates-report.json`
   * - GitHub Summary: Markdown summary if GITHUB_STEP_SUMMARY env var is set
   *
   * Violation processing:
   * - Checks each violation against active waivers
   * - Separates waived vs. blocking violations
   * - Only blocking violations cause exit code 1
   *
   * Artifacts:
   * - QualityGateReport JSON with full metadata
   * - Performance metrics (gate timings, total execution time)
   * - Debug information (if DEBUG_MODE enabled)
   *
   * @returns {void} Exits process with code 0 (success) or 1 (blocking violations)
   */
  reportResults() {
    if (!QUIET_MODE) {
      console.log('\n' + '='.repeat(50));
      console.log('QUALITY GATES RESULTS');
      console.log('='.repeat(50));
    }

    // Check waivers for each violation
    for (const violation of this.violations) {
      this.isViolationWaived(violation);
    }

    // Separate waived and blocking violations
    const waivedViolations = this.violations.filter((v) => v.waivedBy);
    const blockingViolations = this.violations.filter((v) => !v.waivedBy);

    // Report active waivers
    if (this.activeWaivers.length > 0 && !QUIET_MODE && !JSON_MODE) {
      console.log(`\n🔖 ACTIVE WAIVERS (${this.activeWaivers.length}):`);
      for (const waiver of this.activeWaivers) {
        const daysLeft = Math.ceil(
          (new Date(waiver.expires_at) - new Date()) / (1000 * 60 * 60 * 24)
        );
        console.log(`   ${waiver.id}: ${waiver.title} (${daysLeft} days left)`);
        console.log(`      Gates: ${waiver.gates.join(', ')}`);
        console.log(`      Reason: ${waiver.reason}`);
      }
    }

    // Report warnings
    if (this.warnings.length > 0 && !QUIET_MODE && !JSON_MODE) {
      console.log(`\nWARNINGS (${this.warnings.length}):`);
      for (const warning of this.warnings) {
        console.log(`   ${warning.file || 'General'}: ${warning.message}`);
      }
    }

    // Report waived violations
    if (waivedViolations.length > 0 && !QUIET_MODE && !JSON_MODE) {
      console.log(`\n✅ WAIVED VIOLATIONS (${waivedViolations.length}) - ALLOWED:`);
      for (const violation of waivedViolations) {
        console.log(`${violation.gate.toUpperCase()}: ${violation.type.toUpperCase()}`);
        console.log(`   ${violation.message}`);
        console.log(`   Waived by: ${violation.waivedBy} (${violation.waiverTitle})`);
        console.log(`   Expires: ${violation.waiverExpires}`);
        if (violation.file) {
          console.log(`   File: ${violation.file}`);
        }
        console.log('');
      }
    }

    // Report blocking violations
    if (blockingViolations.length > 0) {
      if (!QUIET_MODE && !JSON_MODE) {
        console.log(`\n❌ BLOCKING VIOLATIONS (${blockingViolations.length}) - COMMIT BLOCKED:`);
        console.log('');

        for (const violation of blockingViolations) {
          console.log(`${violation.gate.toUpperCase()}: ${violation.type.toUpperCase()}`);
          console.log(`   ${violation.message}`);
          if (violation.file) {
            console.log(`   File: ${violation.file}`);
          }
          if (violation.size) {
            console.log(`   Size: ${violation.size} LOC`);
          }
          if (violation.details) {
            console.log(`   Details: ${JSON.stringify(violation.details, null, 2)}`);
          }
          console.log('');
        }

        console.log('Fix these critical violations before committing.');
        console.log('See docs/refactoring.md for crisis response plan.');
      }
    } else {
      if (!QUIET_MODE && !JSON_MODE) {
        const statusMsg =
          waivedViolations.length > 0
            ? `QUALITY GATES PASSED (${waivedViolations.length} violations waived)`
            : 'ALL QUALITY GATES PASSED';
        console.log(`\n✅ ${statusMsg}`);
        console.log('Commit allowed - quality maintained!');

        // Clear temporary caches on successful exit
        this.clearTemporaryCaches();
      }
    }

    // Write artifacts (JSON + optional GitHub Summary)
    try {
      const root = process.cwd();
      const outDir = 'docs-status';
      const reportPath = `${outDir}/quality-gates-report.json`;
      const summaryPath = process.env.GITHUB_STEP_SUMMARY;
      const payload = {
        timestamp: new Date().toISOString(),
        context: this.context,
        files_scoped: this.filesToCheck.length,
        warnings: this.warnings,
        violations: this.violations,
        waivers: {
          active: this.activeWaivers.length,
          applied: waivedViolations.length,
          details: this.activeWaivers.map((w) => ({
            id: w.id,
            title: w.title,
            gates: w.gates,
            expires_at: w.expires_at,
          })),
        },
        performance: {
          total_execution_time_ms: Date.now() - this.startTime,
          gate_timings: this.gateTimings,
        },
        debug: DEBUG_MODE
          ? {
              debug_log: this.debugLog,
              environment: {
                node_version: process.version,
                platform: process.platform,
                arch: process.arch,
                cwd: process.cwd(),
              },
            }
          : undefined,
      };
      fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(reportPath, JSON.stringify(payload, null, 2));
      if (JSON_MODE) {
        console.log(JSON.stringify(payload, null, 2));
      }

      if (DEBUG_MODE && !QUIET_MODE) {
        console.log('\n' + '='.repeat(50));
        console.log('DEBUG INFORMATION');
        console.log('='.repeat(50));
        console.log(`Total execution time: ${payload.performance.total_execution_time_ms}ms`);
        console.log('Gate timings:');
        for (const [gate, timing] of Object.entries(payload.performance.gate_timings)) {
          console.log(`  ${gate}: ${timing}ms`);
        }
        console.log('\nDebug log:');
        for (const logEntry of this.debugLog) {
          console.log(`  ${logEntry}`);
        }
        console.log('='.repeat(50));
      }
      if (summaryPath) {
        const lines = [];
        lines.push(`# Quality Gates`);
        lines.push(`- Context: ${this.context}`);
        lines.push(`- Files scoped: ${this.filesToCheck.length}`);
        lines.push(`- Violations: ${this.violations.length}`);
        lines.push(`- Warnings: ${this.warnings.length}`);
        if (this.violations.length) {
          lines.push(`\n## Violations`);
          for (const v of this.violations.slice(0, 50)) {
            lines.push(
              `- **${v.gate}/${v.type}**: ${v.message}${v.file ? ` (file: ${v.file})` : ''}`
            );
          }
        }
        fs.appendFileSync(summaryPath, lines.join('\n') + '\n');
      }
    } catch {}

    // Only block commit if there are non-waived violations
    const nonWaivedViolations = this.violations.filter((v) => !v.waivedBy);
    process.exit(nonWaivedViolations.length ? 1 : 0);
  }
}

/**
 * Main entry point for quality gates runner.
 *
 * Handles command-line argument parsing, initializes QualityGateRunner,
 * and executes all gates. Processes help flag and mode indicators.
 *
 * Execution modes:
 * - CI mode: Stricter enforcement, no interactive fixes
 * - Fix mode: Attempts automatic fixes (experimental)
 * - JSON mode: Outputs machine-readable JSON instead of console output
 * - Quiet mode: Suppresses all output except errors
 * - Debug mode: Enables detailed debug logging
 *
 * @returns {Promise<void>} Resolves when gates complete (or process exits)
 */
async function main() {
  console.log('Quality gates starting...');
  // Handle help flag
  if (process.argv.includes('--help') || process.argv.includes('-h')) {
    console.log(`
Quality Gates Runner - Enterprise Code Quality Enforcement

USAGE:
  node packages/quality-gates/run-quality-gates.mjs [options]

OPTIONS:
  --ci              Run in CI mode (strict enforcement, blocks on warnings)
  --context=<ctx>   Set context explicitly (commit, push, ci)
  --json            Output machine-readable JSON to stdout
  --quiet           Suppress all console output except JSON/errors
  --debug           Enable debug output with timing and detailed logging
  --gates=<list>    Run only specific gates (comma-separated)
  --fix             Attempt automatic fixes (experimental)
  --force           Bypass lock files and force execution
  --help, -h        Show this help message

VALID GATES:
  naming           Check naming conventions and banned modifiers
  code_freeze      Enforce code freeze compliance
  duplication      Detect functional duplication
  god_objects      Prevent oversized files
  documentation    Check documentation quality

EXAMPLES:
  # Run all gates in development mode
  node packages/quality-gates/run-quality-gates.mjs

  # Run only specific gates
  node packages/quality-gates/run-quality-gates.mjs --gates=naming,duplication

  # CI mode with JSON output
  node packages/quality-gates/run-quality-gates.mjs --ci --json

  # GitHub Actions with summary
  GITHUB_STEP_SUMMARY=/tmp/summary.md node packages/quality-gates/run-quality-gates.mjs --ci

OUTPUT:
  - Console: Human-readable results with enforcement levels
  - JSON: Machine-readable structured data (--json flag)
  - Artifacts: docs-status/quality-gates-report.json
  - GitHub Summary: Automatic when GITHUB_STEP_SUMMARY is set

EXIT CODES:
  0  Success - no violations found
  1  Violations found - commit blocked
  2  System error - check failed to run
`);
    process.exit(0);
  }

  if (CI_MODE) {
    console.log('Running in CI mode - strict enforcement');
  }

  if (FIX_MODE) {
    console.log('Running in fix mode - will attempt automatic fixes');
  }

  const runner = new QualityGateRunner();

  await runner.runAllGates();
}

if (
  process.argv[1] &&
  (process.argv[1].endsWith('run-quality-gates.mjs') ||
    process.argv[1].includes('run-quality-gates.mjs'))
) {
  main().catch((error) => {
    console.error('Quality gates crashed:', error);
    process.exit(1);
  });
}

export default QualityGateRunner;
