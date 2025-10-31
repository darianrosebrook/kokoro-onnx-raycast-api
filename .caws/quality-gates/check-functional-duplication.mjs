#!/usr/bin/env node
// scripts/functional-duplication-checker.mjs

/**
 * Quality Gate: Functional Duplication Checker (multi-language, rename-invariant, git-correct)
 *
 * Detects near-duplicate implementations by:
 *  1) discovering function-like regions per language,
 *  2) normalizing tokens (identifiers→VAR, literals→LIT, etc.),
 *  3) building k-shingles and comparing with Jaccard similarity,
 *  4) reporting clone pairs/clusters over thresholds, regression-aware.
 *
 * Dependencies: micromatch, js-yaml
 *
 * @author: @darianrosebrook
 * @date: 2025-10-28
 * @version: 1.0.0
 * @license: MIT
 * @copyright: 2025 Darian Rosebrook
 * @description: Detects functional duplication in the codebase and blocks commits that would create or worsen it.
 */

import { execFileSync } from 'child_process';
import crypto from 'crypto';
import fs from 'fs';
import yaml from 'js-yaml';
import micromatch from 'micromatch';
import os from 'os';
import path from 'path';
import { getFilesToCheck } from './file-scope-manager.mjs';
import { processViolations } from './shared-exception-framework.mjs';

/* ------------------- small helpers ------------------- */
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
    throw new Error('Not a git repository. Run from within a git repo.');
  }
}
function readStaged(root, rel, maxSize = 1024 * 1024, streamingThreshold = 5 * 1024 * 1024) {
  try {
    const content = execFileSync('git', ['show', `:${rel}`], {
      cwd: root,
      stdio: ['ignore', 'pipe', 'ignore'],
      encoding: 'utf8',
    });

    // For very large files, use streaming approach
    if (content.length > streamingThreshold) {
      console.warn(
        `📄 File ${rel} is very large (${content.length} bytes), using streaming analysis`
      );
      return processLargeFileContent(content, rel);
    }

    if (content.length > maxSize) {
      console.warn(
        `⚠️  File ${rel} is large (${content.length} bytes), analyzing first ${maxSize} bytes only`
      );
      return content.substring(0, maxSize);
    }
    return content;
  } catch (error) {
    // File might be deleted or not staged
    return null;
  }
}

function processLargeFileContent(content, rel) {
  // For very large files, extract meaningful regions rather than truncating
  const lines = content.split('\n');
  const regions = [];

  // Sample different parts of the file to get a representative view
  const sampleSize = Math.min(10000, Math.floor(lines.length / 10)); // Sample ~10% but max 10k lines

  // Sample from beginning, middle, and end
  const beginning = lines.slice(0, sampleSize);
  const middle = lines.slice(
    Math.floor(lines.length / 2),
    Math.floor(lines.length / 2) + sampleSize
  );
  const end = lines.slice(-sampleSize);

  const sampledLines = [...beginning, ...middle, ...end];
  const sampledContent = sampledLines.join('\n');

  console.warn(
    `📊 File ${rel}: sampled ${sampledLines.length} lines from ${lines.length} total lines for analysis`
  );

  return sampledContent;
}

/* ------------------- caching system ------------------- */
function getCacheKey(rel, content) {
  const hash = crypto.createHash('md5').update(content).digest('hex');
  return `${rel}:${hash}`;
}

function loadAnalysisCache(root) {
  const cacheFile = path.join(root, '.caws', 'duplication-cache.json');
  try {
    if (fs.existsSync(cacheFile)) {
      const data = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
      // Clean expired cache entries (older than 24 hours)
      const now = Date.now();
      const validEntries = {};
      for (const [key, entry] of Object.entries(data)) {
        if (entry.timestamp && now - entry.timestamp < 24 * 60 * 60 * 1000) {
          validEntries[key] = entry;
        }
      }
      return validEntries;
    }
  } catch (error) {
    console.warn('⚠️  Could not load analysis cache:', error.message);
  }
  return {};
}

function saveAnalysisCache(root, cache) {
  const cacheDir = path.join(root, '.caws');
  const cacheFile = path.join(cacheDir, 'duplication-cache.json');
  try {
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }
    fs.writeFileSync(cacheFile, JSON.stringify(cache, null, 2));
  } catch (error) {
    console.warn('⚠️  Could not save analysis cache:', error.message);
  }
}

function getCachedAnalysis(cache, cacheKey) {
  const entry = cache[cacheKey];
  if (entry && entry.regions) {
    return entry.regions;
  }
  return null;
}

function setCachedAnalysis(cache, cacheKey, regions) {
  cache[cacheKey] = {
    regions,
    timestamp: Date.now(),
  };
}
function resolveBaseRef(root, fallback) {
  try {
    return execFileSync('git', ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], {
      cwd: root,
      encoding: 'utf8',
    }).trim();
  } catch {
    return (
      process.env.GITHUB_BASE_REF ||
      process.env.PR_BASE_REF ||
      process.env.PR_BASE_SHA ||
      fallback ||
      'origin/HEAD'
    );
  }
}

/* ------------------- configuration ------------------- */

const DEFAULT_CFG = {
  // languages we’ll consider and their file globs
  languages: {
    rust: ['**/*.rs'],
    ts: ['**/*.{ts,tsx,mts,cts}'],
    js: ['**/*.{js,jsx,mjs,cjs}'],
    go: ['**/*.go'],
    java: ['**/*.java'],
    kotlin: ['**/*.kt'],
  },
  // generic excludes (linguist-generated/vendored handled upstream in file-scope manager)
  exclude: ['**/target/**', '**/node_modules/**', '**/dist/**', '**/build/**'],
  // token shingle parameters
  shingleSize: 7, // k
  minTokensPerRegion: 60, // skip tiny helpers
  // similarity thresholds
  thresholds: {
    // pair-level
    jaccardWarn: 0.7,
    jaccardBlock: 0.82,
    // cluster-level (same normalized stem across files/packages)
    clusterSizeWarn: 2,
    clusterSizeBlock: 3,
  },
  // regression control
  ciBaseRef: 'origin/HEAD',
  // test files policy (lower or ignore)
  considerTestFiles: false,
  testPatterns: ['**/*_test.*', '**/*.test.*', '**/*.spec.*'],
  // exceptions
  exceptionsFile: '.caws/duplication-exceptions.yaml',
  // crate/package boundary markers
  packageMarkers: [
    'Cargo.toml',
    'package.json',
    'go.mod',
    'pom.xml',
    'build.gradle',
    'settings.gradle.kts',
  ],
  // per-cluster remediation budgets (normalized stem -> allowed growth in duplicate pairs)
  clusterBudgets: {
    // "http.client.retry": 1
  },
  // Name/shape collisions (public symbols)
  nameDuplication: {
    enable: true,
    // language-aware public symbol matchers (cheap regexes)
    allowNames: [
      // idioms and trait/impl boilerplate
      'new',
      'default',
      'clone',
      'from',
      'into',
      'try_from',
      'as_str',
      'len',
      'is_empty',
      'fmt',
      'debug',
      'serialize',
      'deserialize',
      'hash',
      'eq',
      'partial_eq',
      'ord',
      'partial_ord',
      'config',
      'with_config',
      'update',
      'validate',
      'build',
      'from_string',
      'get',
      'set',
      'reset',
      'stats',
      'get_stats',
      'summary',
      'get_summary',
    ],
    // thresholds are *regression* targets (only block if you increase totals)
    regressionBaselines: {
      // these can be set in .qualitygatesrc.yaml if you've measured your baseline
      duplicateStructs: 692,
      duplicateFunctions: 250,
      duplicateTraits: 100,
    },
  },
};

function loadCfg(root) {
  const candidates = [
    path.join(root, '.qualitygatesrc.yaml'),
    path.join(root, '.qualitygatesrc.yml'),
    path.join(root, '.qualitygatesrc.json'),
  ];
  let base = { ...DEFAULT_CFG };
  for (const p of candidates) {
    if (!fs.existsSync(p)) continue;
    const raw = fs.readFileSync(p, 'utf8');
    const user = p.endsWith('.json') ? JSON.parse(raw) : yaml.load(raw) || {};
    // shallow merge (fine for our fields)
    base = { ...base, ...user.functionalDuplication, ciBaseRef: user.ciBaseRef || base.ciBaseRef };
    break;
  }
  // exceptions
  let exceptions = { exceptions: [] };
  const excPath = path.join(root, base.exceptionsFile);
  if (fs.existsSync(excPath)) {
    try {
      exceptions = yaml.load(fs.readFileSync(excPath, 'utf8')) || { exceptions: [] };
    } catch {
      /* noop */
    }
  }
  return { cfg: base, exceptions, excPath };
}

/* ------------------- package / crate boundary ------------------- */
function findPackageRoot(abs, root, markers) {
  let cur = path.dirname(abs);
  while (cur.startsWith(root)) {
    if (markers.some((m) => fs.existsSync(path.join(cur, m)))) return cur;
    const parent = path.dirname(cur);
    if (parent === cur) break;
    cur = parent;
  }
  return path.dirname(abs);
}

/* ------------------- language region discovery ------------------- */
/**
 * We do light function-like region discovery per language via regex. This is intentionally simple
 * because the heavy lifting is done by rename-invariant token normalization + shingling.
 */
const LANG = {
  rust: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /b?["'](?:\\.|[^\\])*?["']/g,
    signature: /^\s*pub\s+fn\s+\w+\s*\([^)]*\)\s*(?:->\s*[^({]+)?\s*\{/m,
    regionStart: /\b(?:pub\s+)?(?:fn|impl|trait|enum|struct)\b/,
    regionEnd: /\}/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*pub\s+(?:struct|trait|fn)\s+([A-Za-z_]\w*)/m,
  },
  ts: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /(["'`])(?:\\.|(?!\1).)*\1/g,
    regionStart: /\b(export\s+)?(function|class|interface|type)\b/,
    regionEnd: /\}/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*export\s+(?:function|class|interface|type)\s+([A-Za-z_]\w*)/m,
  },
  js: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /(["'`])(?:\\.|(?!\1).)*\1/g,
    regionStart: /\b(export\s+)?(function|class)\b/,
    regionEnd: /\}/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*export\s+(?:function|class)\s+([A-Za-z_]\w*)/m,
  },
  go: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /"(?:\\.|[^"\\])*"/g,
    regionStart: /\b(func|type|struct|interface)\b/,
    regionEnd: /\}/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*(?:type|func)\s+([A-Za-z_]\w*)/m,
  },
  java: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /"(?:\\.|[^"\\])*"/g,
    regionStart: /\b(public|private|protected)?\s*(class|interface|enum|void|[\w<>]+\s+\w+\s*\()/,
    regionEnd: /\}/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*public\s+(?:class|interface|enum)\s+([A-Za-z_]\w*)/m,
  },
  kotlin: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /"(?:\\.|[^"\\])*"/g,
    regionStart: /\b(class|interface|object|fun)\b/,
    regionEnd: /\}/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*(?:public\s+)?(?:class|interface|object|fun)\s+([A-Za-z_]\w*)/m,
  },
};

function langOf(rel) {
  const basename = path.basename(rel);

  // Handle files with multiple extensions (e.g., file.rs.bak, file.ts.old)
  if (basename.includes('.')) {
    const parts = basename.split('.');
    const ext = parts[parts.length - 1];

    switch (ext) {
      case 'rs':
        return 'rust';
      case 'ts':
      case 'tsx':
      case 'mts':
      case 'cts':
        return 'ts';
      case 'js':
      case 'jsx':
      case 'mjs':
      case 'cjs':
        return 'js';
      case 'go':
        return 'go';
      case 'java':
        return 'java';
      case 'kt':
        return 'kotlin';
      default:
        return null;
    }
  }
  return null;
}

/* ------------------- token normalization ------------------- */
/**
 * Normalize to remove identifiers/literals variability:
 *  - identifiers → VAR
 *  - numbers → NUM
 *  - strings → STR
 *  - keep operators/keywords
 */
function normalizeTokens(src, langSpec) {
  let s = src
    .replace(langSpec.commentBlock, ' ')
    .replace(langSpec.commentLine, ' ')
    .replace(/\s+/g, ' ');
  // strip strings and numbers
  s = s.replace(langSpec.string, ' STR ');
  s = s.replace(/\b\d[\d_]*(\.\d+)?\b/g, ' NUM ');
  // map identifiers last
  s = s.replace(langSpec.id, (m) => {
    // keep obvious keywords/operators by whitelisting common tokens
    const kw = [
      'if',
      'else',
      'for',
      'while',
      'match',
      'return',
      'break',
      'continue',
      'impl',
      'trait',
      'enum',
      'struct',
      'class',
      'interface',
      'type',
      'extends',
      'implements',
      'fn',
      'pub',
      'mod',
      'use',
      'const',
      'let',
      'var',
      'async',
      'await',
      'try',
      'catch',
      'finally',
      'switch',
      'case',
      'default',
      'package',
      'import',
      'export',
      'public',
      'private',
      'protected',
      'object',
      'fun',
    ];
    if (kw.includes(m)) return m;
    return 'VAR';
  });
  // split into tokens
  return s.trim().split(/\s+/).filter(Boolean);
}

/* ------------------- regions, shingles, and similarity ------------------- */

function extractRegions(text, langSpec, minTokens, shingleSize) {
  // cheap: split by top-level braces into blocks; then filter blocks that start with regionStart nearby
  // this is heuristic but works well with normalization
  const regions = [];
  const lines = text.split(/\r?\n/);
  let buf = [];
  let depth = 0;
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    // naive brace tracking
    for (const ch of L) {
      if (ch === '{') depth++;
      if (ch === '}') depth = Math.max(0, depth - 1);
    }
    buf.push(L);
    if (depth === 0 && buf.length) {
      const block = buf.join('\n');
      if (langSpec.regionStart.test(block)) {
        const tokens = normalizeTokens(block, langSpec);
        if (tokens.length >= minTokens) {
          // build shingles
          const shingles = [];
          for (let j = 0; j <= tokens.length - shingleSize; j++) {
            shingles.push(tokens.slice(j, j + shingleSize).join(' '));
          }
          regions.push({ startLine: i - buf.length + 2, tokens, shingles });
        }
      }
      buf = [];
    }
  }
  return regions;
}

function jaccard(aSet, bSet) {
  let inter = 0;
  if (aSet.size > bSet.size) {
    for (const x of bSet) if (aSet.has(x)) inter++;
  } else {
    for (const x of aSet) if (bSet.has(x)) inter++;
  }
  const union = aSet.size + bSet.size - inter;
  return union === 0 ? 0 : inter / union;
}

/* ------------------- public symbol collection ------------------- */
function collectPublicSymbols(text, langSpec) {
  const out = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(langSpec.publicSymbolLines);
    if (m) out.push({ name: m[1], line: i + 1 });
  }
  return out;
}

/* ------------------- name duplication detection ------------------- */
function collectNameCollisions(fileRegions, cfg) {
  const allow = new Set((cfg.nameDuplication?.allowNames ?? []).map((s) => s.toLowerCase()));
  const nameCounts = new Map(); // symbolName -> count across repo
  const nameSites = new Map(); // symbolName -> [{file,line}]

  for (const fr of fileRegions) {
    for (const sym of fr.symbols) {
      const name = sym.name;
      if (allow.has(name.toLowerCase())) continue;
      nameCounts.set(name, (nameCounts.get(name) || 0) + 1);
      const arr = nameSites.get(name) || [];
      arr.push({ file: fr.rel, line: sym.line });
      nameSites.set(name, arr);
    }
  }

  const duplicateSymbols = [];
  for (const [name, count] of nameCounts) {
    if (count > 1) duplicateSymbols.push({ name, count, sites: nameSites.get(name) || [] });
  }

  return duplicateSymbols;
}

/* ------------------- file basename duplicates ------------------- */
function collectFileBasenameDuplicates(fileRegions, cfg, root) {
  const baseNameMapPerPkg = new Map(); // pkg|basename -> count

  for (const fr of fileRegions) {
    const pkgRoot = findPackageRoot(path.join(root, fr.rel), root, cfg.packageMarkers);
    const pkgKey = path.relative(root, pkgRoot);
    const bnKey = `${pkgKey}|${path.basename(fr.rel)}`;
    baseNameMapPerPkg.set(bnKey, (baseNameMapPerPkg.get(bnKey) || 0) + 1);
  }

  const dupBasenames = [];
  for (const [key, count] of baseNameMapPerPkg) {
    if (count > 1) {
      const [pkg, bn] = key.split('|');
      dupBasenames.push({ pkg, basename: bn, count });
    }
  }

  return dupBasenames;
}

/* ------------------- exceptions ------------------- */
function loadExceptions(exceptions, rel) {
  // exceptions: { exceptions: [{pattern, reason, expires_at}] }
  const now = new Date();
  for (const ex of exceptions.exceptions || []) {
    if (!ex.pattern) continue;
    if (micromatch.isMatch(rel, ex.pattern, { dot: true })) {
      if (ex.expires_at && new Date(ex.expires_at) < now)
        return { valid: false, expired: true, entry: ex };
      return { valid: true, entry: ex };
    }
  }
  return { valid: false };
}

/* ------------------- main check ------------------- */

export async function checkFunctionalDuplication(context = 'commit') {
  const root = repoRoot();
  const { cfg, exceptions } = loadCfg(root);
  const baseRef = resolveBaseRef(root, cfg.ciBaseRef);

  // discover files from hardened scope manager (already filters linguist attrs)
  const absFiles = getFilesToCheck(context);
  const relFiles = absFiles.map((a) => path.relative(root, a));

  // filter by supported language and excludes
  const langFiles = [];
  for (const rel of relFiles) {
    if (cfg.exclude && micromatch.isMatch(rel, cfg.exclude, { dot: true })) continue;
    const lang = langOf(rel);
    if (!lang) continue;
    const patterns = cfg.languages[lang] ?? [];
    if (patterns.length && !micromatch.isMatch(rel, patterns, { dot: true })) continue;
    if (!cfg.considerTestFiles && micromatch.isMatch(rel, cfg.testPatterns, { dot: true }))
      continue;
    langFiles.push({ rel, lang });
  }

  // index regions (parallel processing with caching for performance)
  const maxConcurrency = Math.min(8, langFiles.length); // Limit concurrency to avoid overwhelming
  const fileRegions = [];
  const cache = loadAnalysisCache(root);
  let cacheHits = 0;
  let cacheMisses = 0;

  if (langFiles.length > 10) {
    console.warn(
      `🔄 Processing ${langFiles.length} files with parallel analysis (max ${maxConcurrency} concurrent)`
    );
  }

  // Process files in chunks to control concurrency
  for (let i = 0; i < langFiles.length; i += maxConcurrency) {
    const chunk = langFiles.slice(i, i + maxConcurrency);
    const chunkPromises = chunk.map(async (f) => {
      try {
        const staged = readStaged(root, f.rel);
        if (!staged) return null; // deleted or not staged

        const spec = LANG[f.lang];
        if (!spec) return null;

        // Check cache first
        const cacheKey = getCacheKey(f.rel, staged);
        let regs = getCachedAnalysis(cache, cacheKey);

        if (regs) {
          cacheHits++;
        } else {
          // Cache miss - analyze the file
          regs = extractRegions(staged, spec, cfg.minTokensPerRegion, cfg.shingleSize);
          setCachedAnalysis(cache, cacheKey, regs);
          cacheMisses++;
        }

        // Collect public symbols for name collision detection
        const symbols = collectPublicSymbols(staged, spec);

        const pkgRoot = findPackageRoot(path.join(root, f.rel), root, cfg.packageMarkers);
        return { ...f, pkgRoot, regions: regs, symbols };
      } catch (error) {
        console.warn(`⚠️  Error processing ${f.rel}: ${error.message}`);
        return null;
      }
    });

    const chunkResults = await Promise.all(chunkPromises);
    fileRegions.push(...chunkResults.filter((result) => result !== null));
  }

  // Save cache if we had cache misses
  if (cacheMisses > 0) {
    saveAnalysisCache(root, cache);
  }

  if (cacheHits > 0 || cacheMisses > 0) {
    console.warn(`Cache: ${cacheHits} hits, ${cacheMisses} misses`);
  }

  // build inverted index of shingles -> [fileIndex, regionIndex]
  const shingleMap = new Map();
  fileRegions.forEach((fr, fi) => {
    fr.regions.forEach((r, ri) => {
      for (const sh of r.shingles) {
        const arr = shingleMap.get(sh);
        if (arr) arr.push([fi, ri]);
        else shingleMap.set(sh, [[fi, ri]]);
      }
    });
  });

  // candidate pairs via shared shingles
  const pairMap = new Map(); // "fi,ri|fj,rj" -> countShared
  for (const [, hits] of shingleMap) {
    if (hits.length < 2) continue;
    for (let i = 0; i < hits.length; i++) {
      for (let j = i + 1; j < hits.length; j++) {
        const a = hits[i],
          b = hits[j];
        const key = `${a[0]},${a[1]}|${b[0]},${b[1]}`;
        pairMap.set(key, (pairMap.get(key) || 0) + 1);
      }
    }
  }

  // evaluate pairs with Jaccard
  const pairFindings = [];
  for (const [key, shared] of pairMap) {
    const [a, b] = key.split('|');
    const [fi, ri] = a.split(',').map(Number);
    const [fj, rj] = b.split(',').map(Number);
    const R1 = fileRegions[fi].regions[ri];
    const R2 = fileRegions[fj].regions[rj];
    const set1 = new Set(R1.shingles);
    const set2 = new Set(R2.shingles);
    const sim = jaccard(set1, set2);

    if (sim >= cfg.thresholds.jaccardWarn) {
      const F1 = fileRegions[fi];
      const F2 = fileRegions[fj];
      // ignore comparisons inside the same file region
      if (F1.rel === F2.rel && Math.abs(R1.startLine - R2.startLine) < 5) continue;

      // exceptions
      const ex1 = loadExceptions(exceptions, F1.rel);
      const ex2 = loadExceptions(exceptions, F2.rel);
      if (ex1.valid || ex2.valid) continue;

      pairFindings.push({
        sim,
        files: [
          { file: F1.rel, pkg: path.relative(root, F1.pkgRoot), line: R1.startLine, lang: F1.lang },
          { file: F2.rel, pkg: path.relative(root, F2.pkgRoot), line: R2.startLine, lang: F2.lang },
        ],
      });
    }
  }

  // cluster by normalized stem within package roots (helps with canonical consolidation)
  function normStem(rel) {
    const base = path
      .basename(rel)
      .toLowerCase()
      .replace(/\.[^.]+$/, '');
    return base.replace(/[-_.]v?\d+$/i, '').replace(/[-_.](final|copy|new|next)$/i, '');
  }
  const clusters = new Map(); // pkg|stem -> Set<file>
  for (const p of pairFindings) {
    for (const side of p.files) {
      const key = `${side.pkg}|${normStem(side.file)}`;
      if (!clusters.has(key)) clusters.set(key, new Set());
      clusters.get(key).add(side.file);
    }
  }

  // Additional detection: name collisions and file duplicates
  const duplicateSymbols = collectNameCollisions(fileRegions, cfg);
  const dupBasenames = collectFileBasenameDuplicates(fileRegions, cfg, root);

  // prepare violations
  const violations = [];
  const warnings = [];

  // pair-level functional duplicates
  for (const p of pairFindings.sort((a, b) => b.sim - a.sim)) {
    const severity = p.sim >= cfg.thresholds.jaccardBlock ? 'block' : 'warn';
    const msg =
      `High functional similarity (Jaccard ${p.sim.toFixed(2)}) between:\n` +
      `  - ${p.files[0].file}:${p.files[0].line}\n` +
      `  - ${p.files[1].file}:${p.files[1].line}`;
    const v = {
      type: 'functional_duplicate_pair',
      similarity: p.sim,
      files: p.files,
      severity,
      rule: `Rename-invariant similarity via ${cfg.shingleSize}-shingles`,
      message: msg,
    };
    (severity === 'block' ? violations : warnings).push(v);
  }

  // cluster-level functional duplicates
  for (const [key, set] of clusters) {
    const sz = set.size;
    if (sz >= cfg.thresholds.clusterSizeWarn) {
      const severity = sz >= cfg.thresholds.clusterSizeBlock ? 'block' : 'warn';
      const [pkg, stem] = key.split('|');
      const budget = DEFAULT_CFG.clusterBudgets?.[stem] ?? 0;
      const v = {
        type: 'functional_duplicate_cluster',
        package: pkg,
        stem,
        size: sz,
        severity,
        rule: `Multiple files implementing the same stem within package`,
        message: `Cluster '${stem}' in ${pkg} has ${sz} members.`,
        budgetAllowed: budget,
      };
      (severity === 'block' ? violations : warnings).push(v);
    }
  }

  // name collision regression (public symbols)
  if (cfg.nameDuplication?.enable) {
    const baselines = cfg.nameDuplication.regressionBaselines || {};
    const dupStructs = duplicateSymbols.filter((x) => /^[A-Z]/.test(x.name)); // rough: types/structs/classes
    const dupFns = duplicateSymbols.filter((x) => /^[a-z_]/.test(x.name)); // rough: functions/methods
    const dupTraits = duplicateSymbols.filter((x) => /Trait$|Interface$/.test(x.name)); // rough: traits/interfaces

    const counts = {
      structs: dupStructs.length,
      functions: dupFns.length,
      traits: dupTraits.length,
    };

    if (baselines.duplicateStructs && counts.structs > baselines.duplicateStructs) {
      violations.push({
        type: 'struct_duplication_regression',
        severity: 'block',
        rule: 'Public type name duplicated above baseline',
        message: `Duplicate public type names: ${counts.structs} > baseline ${baselines.duplicateStructs}`,
      });
    } else if (
      baselines.duplicateStructs &&
      counts.structs > Math.floor(baselines.duplicateStructs * 0.9)
    ) {
      warnings.push({
        type: 'struct_duplication_near_baseline',
        severity: 'warn',
        message: `Public type name duplicates near baseline: ${counts.structs}/${baselines.duplicateStructs}`,
      });
    }

    if (baselines.duplicateFunctions && counts.functions > baselines.duplicateFunctions) {
      violations.push({
        type: 'function_duplication_regression',
        severity: 'block',
        rule: 'Public function name duplicated above baseline (allowlist filtered)',
        message: `Duplicate public function names: ${counts.functions} > baseline ${baselines.duplicateFunctions}`,
      });
    }

    if (baselines.duplicateTraits && counts.traits > baselines.duplicateTraits) {
      violations.push({
        type: 'trait_duplication_regression',
        severity: 'block',
        rule: 'Public trait/interface name duplicated above baseline',
        message: `Duplicate trait/interface names: ${counts.traits} > baseline ${baselines.duplicateTraits}`,
      });
    }
  }

  // file duplicates by basename within same package (contextual)
  for (const d of dupBasenames) {
    warnings.push({
      type: 'basename_duplicate_within_package',
      severity: 'warn',
      message: `Multiple files named '${d.basename}' in package ${d.pkg} (count=${d.count})`,
    });
  }

  // defer to exception framework for final severity resolution
  const processed = processViolations('duplication', [...violations, ...warnings], context);

  return {
    violations: processed.violations,
    warnings: processed.warnings,
    enforcementLevel: processed.enforcementLevel,
  };
}

/* ------------------- CLI ------------------- */
async function main() {
  const ctx = process.argv[2] || 'commit';
  const res = await checkFunctionalDuplication(ctx);

  if (res.violations.length) {
    console.log(`Blocking duplication findings: ${res.violations.length}`);
    for (const v of res.violations) {
      switch (v.type) {
        case 'functional_duplicate_pair':
          console.log(`- Pair (${v.similarity.toFixed(2)}):`);
          console.log(`  ${v.files[0].file}:${v.files[0].line}`);
          console.log(`  ${v.files[1].file}:${v.files[1].line}`);
          break;
        case 'functional_duplicate_cluster':
          console.log(`- Cluster '${v.stem}' in ${v.package} size=${v.size}`);
          break;
        case 'struct_duplication_regression':
        case 'function_duplication_regression':
        case 'trait_duplication_regression':
          console.log(`- ${v.type}: ${v.message}`);
          break;
        default:
          console.log(`- ${v.type}: ${v.message}`);
      }
    }
    process.exit(1);
  }

  if (res.warnings.length) {
    console.log(`Warnings: ${res.warnings.length}`);
    for (const v of res.warnings.slice(0, 15)) {
      switch (v.type) {
        case 'functional_duplicate_pair':
          console.log(
            `- Pair warn (${v.similarity.toFixed(2)}): ${v.files[0].file} <> ${v.files[1].file}`
          );
          break;
        case 'functional_duplicate_cluster':
          console.log(`- Cluster warn '${v.stem}' in ${v.package} size=${v.size}`);
          break;
        case 'basename_duplicate_within_package':
          console.log(`- ${v.message}`);
          break;
        case 'struct_duplication_near_baseline':
          console.log(`- ${v.message}`);
          break;
        default:
          console.log(`- ${v.type}: ${v.message}`);
      }
    }
  } else {
    console.log('No duplication issues.');
  }
  process.exit(0);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error('❌ Functional duplication check failed:', error);
    process.exit(1);
  });
}
