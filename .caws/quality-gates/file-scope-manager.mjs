#!/usr/bin/env node
// scripts/file-scope-manager.mjs

/**
 * @typedef {Object} ContextInfo
 * @property {string} description - Human-readable context description
 * @property {string} scope - Context scope: 'commit', 'push', or 'ci'
 * @property {string} gitCommand - Git command used to determine file scope
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import yaml from 'js-yaml';
import micromatch from 'micromatch';
import path from 'path';

/** ----------------------- cross-platform helpers ----------------------- */
function normalizePath(p) {
  // Normalize paths for cross-platform compatibility
  return process.platform === 'win32' ? p.replace(/\\/g, '/') : p;
}

/** ----------------------- binary file detection ----------------------- */
function isBinaryFile(filePath, sampleSize = 1024) {
  try {
    // Read first sampleSize bytes to check for binary content
    const buffer = Buffer.alloc(sampleSize);
    const fd = fs.openSync(filePath, 'r');
    const bytesRead = fs.readSync(fd, buffer, 0, sampleSize, 0);
    fs.closeSync(fd);

    if (bytesRead === 0) return false; // Empty file

    // Check for null bytes (common in binary files)
    for (let i = 0; i < bytesRead; i++) {
      if (buffer[i] === 0) return true;
    }

    // Check for high proportion of non-printable characters
    let nonPrintable = 0;
    for (let i = 0; i < bytesRead; i++) {
      const byte = buffer[i];
      // Consider bytes < 32 or > 126 as non-printable (except common whitespace)
      if ((byte < 32 && byte !== 9 && byte !== 10 && byte !== 13) || byte > 126) {
        nonPrintable++;
      }
    }

    // If more than 30% non-printable characters, likely binary
    return nonPrintable / bytesRead > 0.3;
  } catch (error) {
    // If we can't read the file, assume it's not binary (fail open)
    return false;
  }
}

function isLikelyBinaryFile(filePath) {
  // Quick filename-based binary detection
  const binaryExtensions = [
    '.jpg',
    '.jpeg',
    '.png',
    '.gif',
    '.bmp',
    '.tiff',
    '.ico',
    '.svg', // images
    '.mp3',
    '.wav',
    '.flac',
    '.aac',
    '.ogg', // audio
    '.mp4',
    '.avi',
    '.mkv',
    '.mov',
    '.wmv', // video
    '.zip',
    '.tar',
    '.gz',
    '.bz2',
    '.7z',
    '.rar', // archives
    '.exe',
    '.dll',
    '.so',
    '.dylib', // executables
    '.pdf',
    '.doc',
    '.docx',
    '.xls',
    '.xlsx', // documents
    '.ttf',
    '.woff',
    '.woff2', // fonts
  ];

  const ext = path.extname(filePath).toLowerCase();
  if (binaryExtensions.includes(ext)) return true;

  // Check file size - very large files are likely binary
  try {
    const stats = fs.statSync(filePath);
    if (stats.size > 50 * 1024 * 1024) {
      // 50MB threshold
      return true;
    }
  } catch {
    // Ignore stat errors
  }

  return false;
}

function isGitLFSFile(filePath, content) {
  // Git LFS pointer files start with "version https://git-lfs.github.com/spec/v1"
  if (content && content.startsWith('version https://git-lfs.github.com/spec/v1')) {
    return true;
  }

  // Also check if the file is tracked by LFS via .gitattributes
  try {
    const gitattributesPath = path.join(path.dirname(filePath), '.gitattributes');
    if (fs.existsSync(gitattributesPath)) {
      const gitattributes = fs.readFileSync(gitattributesPath, 'utf8');
      const filename = path.basename(filePath);
      const lines = gitattributes.split('\n');

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed && !trimmed.startsWith('#')) {
          const [pattern, ...attrs] = trimmed.split(/\s+/);
          if (pattern && micromatch.isMatch(filename, pattern, { dot: true })) {
            if (
              attrs.includes('filter=lfs') ||
              attrs.includes('diff=lfs') ||
              attrs.includes('merge=lfs')
            ) {
              return true;
            }
          }
        }
      }
    }
  } catch {
    // Ignore errors reading .gitattributes
  }

  return false;
}

/** ----------------------- git helpers (NUL-safe) ----------------------- */
function git(args, { cwd, stdio } = {}) {
  try {
    return execFileSync('git', args, {
      cwd,
      encoding: 'utf8',
      stdio: stdio ?? ['ignore', 'pipe', 'ignore'],
    });
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
  // Git typically ends with a trailing NUL
  return s.split('\0').filter(Boolean);
}

function repoRoot() {
  try {
    return git(['rev-parse', '--show-toplevel']).trim();
  } catch {
    throw new Error('Not a git repository. Run inside a repo or ensure GIT_* envs are set.');
  }
}

/** ----------------------- config ----------------------- */
const DEFAULT_CONFIG = {
  presets: {
    rust: ['**/*.{rs,toml}', 'Cargo.toml', 'Cargo.lock'],
    web: ['**/*.{ts,tsx,js,jsx,mjs,cjs,cts,mts}', '**/*.{json,yml,yaml}'],
    docs: ['**/*.{md,mdx}'],
    styles: ['**/*.{css,scss,less}'],
    infra: [
      'Dockerfile*',
      'docker/**',
      '**/*.{sh,bash,zsh,fish}',
      'Makefile',
      '.editorconfig',
      '.gitattributes',
      '.gitignore',
      '.nvmrc',
      '.tool-versions',
      '**/*.{nix,tf,tfvars}',
      '**/*.{yml,yaml}',
      '**/*.{xml,plist}',
      '**/*.{proto,sql}',
    ],
  },
  usePresets: ['rust', 'web', 'docs', 'styles', 'infra'],
  includeGlobs: [],
  excludeGlobs: ['**/node_modules/**', '**/dist/**', '**/build/**', '**/target/**', '**/.git/**'],
  // Linguist filtering controls
  linguist: {
    excludeGenerated: true,
    excludeVendored: true,
    excludeDocumentation: false, // docs usually kept for link checks / spellcheck; tune per gate
  },
  // CI base ref fallback used in push/PR contexts if upstream not found and no env override is present
  ciBaseRef: 'origin/HEAD',
  // Optional: group by package for monorepos (not required by this module, but useful downstream)
  monorepo: {
    detectPackages: false,
    packageMarkers: ['package.json', 'Cargo.toml'],
  },
  // Optional per-gate exclusions (gate id -> array of globs). Consumed by your gate runner.
  gateExclusions: {},
};

function loadConfig(root) {
  const candidates = [
    path.join(root, '.qualitygatesrc.json'),
    path.join(root, '.qualitygatesrc.yaml'),
    path.join(root, '.qualitygatesrc.yml'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) {
      const raw = fs.readFileSync(p, 'utf8');
      if (p.endsWith('.json')) return { ...DEFAULT_CONFIG, ...JSON.parse(raw) };
      return { ...DEFAULT_CONFIG, ...(yaml.load(raw) || {}) };
    }
  }
  return { ...DEFAULT_CONFIG };
}

/** ----------------------- matchers ----------------------- */
function makeMatcher(cfg) {
  const includes = [
    ...(cfg.usePresets ?? []).flatMap((p) => cfg.presets?.[p] ?? []),
    ...(cfg.includeGlobs ?? []),
  ];
  const excludes = cfg.excludeGlobs ?? [];
  return (relPath) =>
    (includes.length === 0 || micromatch.isMatch(relPath, includes, { dot: true })) &&
    (excludes.length === 0 || !micromatch.isMatch(relPath, excludes, { dot: true }));
}

/** ----------------------- shebang batching -----------------------
 * We only bother shebang-scanning files that have NO extension and passed the glob matcher.
 * Limit read to first 128 bytes per file for speed.
 */
function shebangMapFor(pathsAbs) {
  const map = new Map();
  for (const abs of pathsAbs) {
    let has = false;
    try {
      const fd = fs.openSync(abs, 'r');
      const buf = Buffer.alloc(128);
      const bytes = fs.readSync(fd, buf, 0, buf.length, 0);
      fs.closeSync(fd);
      if (bytes > 1) {
        const head = buf.toString('utf8', 0, bytes);
        has = head.startsWith('#!') || head.startsWith('\uFEFF#!');
      }
    } catch {
      has = false;
    }
    map.set(abs, has);
  }
  return map;
}

/** ----------------------- linguist attribute filtering (batch) -----------------------
 * Uses `git check-attr -z --stdin linguist-generated linguist-vendored linguist-documentation`
 * Results are keyed by repo-relative path. Returns a Set of paths to EXCLUDE based on cfg.linguist flags.
 */
function linguistExcludeSet(root, relPaths, cfg) {
  const attrs = ['linguist-generated', 'linguist-vendored', 'linguist-documentation'];
  if (relPaths.length === 0) return new Set();

  // Prepare NUL-delimited stdin: path\0path\0...
  const input = Buffer.from(relPaths.join('\0') + '\0', 'utf8');
  // Output format (-z): "path\0attr\0value\0path\0attr\0value\0..."
  const out = execFileSync('git', ['check-attr', '-z', '--stdin', ...attrs], {
    cwd: root,
    input,
    stdio: ['pipe', 'pipe', 'ignore'],
  }).toString('utf8');

  const tokens = splitNul(out);
  const exclude = new Set();

  // Tokens come in triplets: [path, attr, value]
  for (let i = 0; i + 2 < tokens.length; i += 3) {
    const p = tokens[i];
    const attr = tokens[i + 1];
    const val = tokens[i + 2]; // "set" | "unset" | "unspecified" | explicit value
    const should =
      (attr === 'linguist-generated' && cfg.linguist?.excludeGenerated) ||
      (attr === 'linguist-vendored' && cfg.linguist?.excludeVendored) ||
      (attr === 'linguist-documentation' && cfg.linguist?.excludeDocumentation);

    if (should) {
      // Treat "set", "true", or non-"false" string as truthy per linguist conventions
      const truthy =
        val === 'set' || val === 'true' || (val && val !== 'false' && val !== 'unspecified');
      if (truthy) exclude.add(p);
    }
  }
  return exclude;
}

/** ----------------------- sources from git ----------------------- */
function listRepoFiles(root) {
  // tracked files; respects .gitignore, submodules if --recurse-submodules
  const out = gitBuf(['ls-files', '-z', '--recurse-submodules'], { cwd: root });
  return splitNul(out);
}
function listStagedFiles(root) {
  // Include Adds, Copies, Modifications, Renames, Type changes, Unmerged, Unknown, Submodule changes
  const out = gitBuf(['diff', '--cached', '--name-only', '-z', '--diff-filter=ACMRTUXB'], {
    cwd: root,
  });
  return splitNul(out);
}
function resolveBaseRef(root, fallback) {
  try {
    return git(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], {
      cwd: root,
    }).trim();
  } catch {
    // Prefer CI envs if present
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
    }).trim();
    return ref || 'origin/HEAD';
  } catch {
    return 'origin/HEAD';
  }
}
function listPushFiles(root, baseRef) {
  const base = resolveBaseRef(root, baseRef);
  const out = gitBuf(['diff', '--name-only', '-z', '--diff-filter=ACMRTUXB', `${base}...HEAD`], {
    cwd: root,
  });
  return splitNul(out);
}

/** ----------------------- normalization & selection ----------------------- */
function filterAndNormalize(relPaths, root, cfg) {
  const match = makeMatcher(cfg);
  // First pass: apply include/exclude globs and basic existence checks
  const keptRel = [];
  const extlessAbs = [];

  for (const rel of relPaths) {
    if (!rel) continue;
    if (!match(rel)) continue;

    const abs = path.join(root, rel);
    try {
      const st = fs.statSync(abs);
      if (!st.isFile()) continue;

      const ext = path.extname(rel);
      if (ext) {
        keptRel.push(rel);
      } else {
        extlessAbs.push(abs); // wait for shebang scan
      }
    } catch {
      // ignore unreadable paths
    }
  }

  // Shebang include for extensionless
  if (extlessAbs.length > 0) {
    const shebangs = shebangMapFor(extlessAbs);
    for (const abs of extlessAbs) {
      if (shebangs.get(abs)) {
        keptRel.push(path.relative(root, abs));
      } else {
        // also include well-known config files without extension
        const rel = path.relative(root, abs);
        if (/(^|\/)(Makefile|Dockerfile.*|\.editorconfig|\.env.*|\.git.*)$/i.test(rel)) {
          keptRel.push(rel);
        }
      }
    }
  }

  // Linguist attribute filtering (generated/vendored/documentation) — batch
  const excludeSet = linguistExcludeSet(root, keptRel, cfg);
  const linguistFiltered = keptRel.filter((p) => !excludeSet.has(p));

  // Binary file filtering — skip files that are likely binary or Git LFS pointers
  const finalRel = [];
  for (const rel of linguistFiltered) {
    const abs = path.join(root, rel);

    // Quick check first (extensions, size)
    if (isLikelyBinaryFile(abs)) {
      continue;
    }

    // Check if file is a Git LFS pointer
    try {
      const content = fs.readFileSync(abs, 'utf8');
      if (isGitLFSFile(abs, content)) {
        continue; // Skip Git LFS pointer files
      }
    } catch {
      // If we can't read the file, assume it's not LFS (fail open)
    }

    // Deep binary check if still uncertain
    try {
      if (!isBinaryFile(abs)) {
        finalRel.push(rel);
      }
    } catch {
      // If we can't check, include it (fail open for text files)
      finalRel.push(rel);
    }
  }

  return finalRel;
}

/** ----------------------- public API ----------------------- */

/**
 * Gets the list of files to check based on execution context.
 *
 * File scoping by context:
 * - 'commit': Staged files only (git diff --cached)
 * - 'push': Files changed vs. upstream base (git diff <base>...HEAD)
 * - 'ci': All tracked files in repository (git ls-files)
 *
 * File filtering:
 * - Applies include/exclude globs from `.qualitygatesrc.json`
 * - Filters binary files (by extension, size, content analysis)
 * - Filters Git LFS pointer files
 * - Respects linguist attributes (generated, vendored, documentation)
 * - Includes extensionless files with shebangs
 *
 * @param {'commit'|'push'|'ci'} [context='commit'] - Execution context
 * @returns {string[]} Array of absolute file paths to check
 * @throws {Error} If not in a git repository or git commands fail
 */
export function getFilesToCheck(context = 'commit') {
  const root = repoRoot();
  const cfg = loadConfig(root);

  let rel;
  if (context === 'commit') rel = listStagedFiles(root);
  else if (context === 'push') rel = listPushFiles(root, cfg.ciBaseRef);
  else if (context === 'ci') rel = listRepoFiles(root);
  else rel = listStagedFiles(root);

  const selectedRel = filterAndNormalize(rel, root, cfg);
  // Absolute paths for downstream tools that need them
  return selectedRel.map((r) => path.join(root, r));
}

export function getFilesByPattern(context = 'commit', patterns = ['**/*']) {
  const root = repoRoot();
  const abs = getFilesToCheck(context);
  const rel = abs.map((a) => path.relative(root, a));
  const matchedRel = micromatch(rel, patterns, { dot: true });
  return matchedRel.map((r) => path.join(root, r));
}

/**
 * Gets human-readable information about an execution context.
 *
 * Provides metadata about what files are being checked and how,
 * useful for logging and user feedback.
 *
 * @param {'commit'|'push'|'ci'} context - Execution context
 * @returns {ContextInfo} Context metadata with description and git command
 */
export function getContextInfo(context) {
  if (context === 'commit')
    return {
      description: 'staged files only',
      scope: 'commit',
      gitCommand: 'git diff --cached --name-only -z --diff-filter=ACMRTUXB',
    };
  if (context === 'push')
    return {
      description: 'files changed vs base (upstream/CI)',
      scope: 'push',
      gitCommand: 'git diff --name-only -z --diff-filter=ACMRTUXB <base>...HEAD',
    };
  if (context === 'ci')
    return {
      description: 'all tracked files',
      scope: 'ci',
      gitCommand: 'git ls-files -z --recurse-submodules',
    };
  return {
    description: 'unknown context',
    scope: 'unknown',
    gitCommand: 'fallback',
  };
}

/** ----------------------- CLI (manual test) ----------------------- */
if (import.meta.url === `file://${process.argv[1]}`) {
  const ctx = process.argv[2] || 'commit';
  const root = repoRoot();
  const info = getContextInfo(ctx);
  console.log(`Scope: ${info.description}`);
  console.log(`Command: ${info.gitCommand}`);
  const files = getFilesToCheck(ctx);
  console.log(`Files (${files.length}):`);
  for (const f of files) console.log(path.relative(root, f));
}
