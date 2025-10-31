#!/usr/bin/env node
// scripts/duplication-gate.mjs
/**
 * Unified CAWS Duplication Gate: functional clones + name collisions + file duplicates
 *
 * @author: @darianrosebrook
 * @date: 2025-10-28
 * @version: 1.0.0
 * @license: MIT
 * @copyright: 2025 Darian Rosebrook
 * @description: Detects functional duplication in the codebase and blocks commits that would create or worsen it.
 */

import { execFileSync } from 'child_process';
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
    return execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
  } catch (error) {
    throw new Error(
      `Not a git repository or git command failed: ${error.message}. Run from within a git repository.`
    );
  }
}
function readStaged(root, rel) {
  try {
    return execFileSync('git', ['show', `:${rel}`], {
      cwd: root,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
  } catch {
    return null;
  }
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

/* ---------- Config ---------- */
const DEFAULT_CFG = {
  ciBaseRef: 'origin/HEAD',
  considerTestFiles: false,
  testPatterns: ['**/*_test.*', '**/*.test.*', '**/*.spec.*'],
  exclude: ['**/node_modules/**', '**/dist/**', '**/build/**', '**/target/**'],
  packageMarkers: [
    'Cargo.toml',
    'package.json',
    'go.mod',
    'pom.xml',
    'build.gradle',
    'settings.gradle.kts',
  ],
  // Functional clone detection
  shingleSize: 7,
  minTokensPerRegion: 60,
  thresholds: {
    jaccardWarn: 0.7,
    jaccardBlock: 0.82,
    clusterSizeWarn: 2,
    clusterSizeBlock: 3,
  },
  // Name/shape collisions
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
      // these can be set in .qualitygatesrc.yaml if you’ve measured your baseline
      duplicateStructs: 692,
      duplicateFunctions: 250,
      duplicateTraits: 100,
    },
  },
  // Exceptions
  exceptionsFile: '.caws/duplication-exceptions.yaml',
  // Language -> file globs
  languages: {
    rust: ['**/*.rs'],
    ts: ['**/*.{ts,tsx,mts,cts}'],
    js: ['**/*.{js,jsx,mjs,cjs}'],
    go: ['**/*.go'],
    java: ['**/*.java'],
    kotlin: ['**/*.kt'],
  },
};

function loadCfg(root) {
  const candidates = ['.qualitygatesrc.yaml', '.qualitygatesrc.yml', '.qualitygatesrc.json'].map(
    (p) => path.join(root, p)
  );
  let cfg = { ...DEFAULT_CFG };
  for (const p of candidates) {
    if (!fs.existsSync(p)) continue;
    const raw = fs.readFileSync(p, 'utf8');
    const user = p.endsWith('.json') ? JSON.parse(raw) : yaml.load(raw) || {};
    // merge under a top-level key if you prefer (functionalDuplication / duplicationGate), or flat—both supported
    const u = user.duplicationGate || user.functionalDuplication || user;
    cfg = {
      ...cfg,
      ...u,
      thresholds: { ...cfg.thresholds, ...(u?.thresholds || {}) },
      nameDuplication: { ...cfg.nameDuplication, ...(u?.nameDuplication || {}) },
      languages: { ...cfg.languages, ...(u?.languages || {}) },
    };
    break;
  }
  // exceptions
  let exceptions = { exceptions: [] };
  const excPath = path.join(root, cfg.exceptionsFile);
  if (fs.existsSync(excPath)) {
    try {
      exceptions = yaml.load(fs.readFileSync(excPath, 'utf8')) || { exceptions: [] };
    } catch {}
  }
  return { cfg, exceptions };
}

/* ---------- Package boundary ---------- */
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

/* ---------- Language specs (light) ---------- */
const LANG = {
  rust: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /b?["'](?:\\.|[^\\])*?["']/g,
    regionStart: /\b(?:pub\s+)?(?:fn|impl|trait|enum|struct)\b/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*pub\s+(?:struct|trait|fn)\s+([A-Za-z_]\w*)/m,
  },
  ts: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /(["'`])(?:\\.|(?!\1).)*\1/g,
    regionStart: /\b(export\s+)?(function|class|interface|type)\b/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*export\s+(?:function|class|interface|type)\s+([A-Za-z_]\w*)/m,
  },
  js: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /(["'`])(?:\\.|(?!\1).)*\1/g,
    regionStart: /\b(export\s+)?(function|class)\b/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*export\s+(?:function|class)\s+([A-Za-z_]\w*)/m,
  },
  go: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /"(?:\\.|[^"\\])*"/g,
    regionStart: /\b(func|type|struct|interface)\b/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*(?:type|func)\s+([A-Za-z_]\w*)/m,
  },
  java: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /"(?:\\.|[^"\\])*"/g,
    regionStart: /\b(public|private|protected)?\s*(class|interface|enum|void|[\w<>]+\s+\w+\s*\()/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*public\s+(?:class|interface|enum)\s+([A-Za-z_]\w*)/m,
  },
  kotlin: {
    commentLine: /\/\/.*$/gm,
    commentBlock: /\/\*[\s\S]*?\*\//g,
    string: /"(?:\\.|[^"\\])*"/g,
    regionStart: /\b(class|interface|object|fun)\b/,
    id: /\b[_A-Za-z]\w*\b/g,
    publicSymbolLines: /^\s*(?:public\s+)?(?:class|interface|object|fun)\s+([A-Za-z_]\w*)/m,
  },
};
function langOf(rel) {
  if (rel.endsWith('.rs')) return 'rust';
  if (/\.(ts|tsx|mts|cts)$/.test(rel)) return 'ts';
  if (/\.(js|jsx|mjs|cjs)$/.test(rel)) return 'js';
  if (rel.endsWith('.go')) return 'go';
  if (rel.endsWith('.java')) return 'java';
  if (rel.endsWith('.kt')) return 'kotlin';
  return null;
}

/* ---------- Token normalization + regions ---------- */
function normalizeTokens(src, spec) {
  let s = src.replace(spec.commentBlock, ' ').replace(spec.commentLine, ' ').replace(/\s+/g, ' ');
  s = s.replace(spec.string, ' STR ').replace(/\b\d[\d_]*(\.\d+)?\b/g, ' NUM ');
  s = s.replace(spec.id, (m) => {
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
    return kw.includes(m) ? m : 'VAR';
  });
  return s.trim().split(/\s+/).filter(Boolean);
}
function extractRegions(text, spec, minTokens, k) {
  const regions = [];
  const lines = text.split(/\r?\n/);
  let buf = [],
    depth = 0,
    startLine = 1;
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    for (const ch of L) {
      if (ch === '{') depth++;
      else if (ch === '}') depth = Math.max(0, depth - 1);
    }
    if (buf.length === 0) startLine = i + 1;
    buf.push(L);
    if (depth === 0 && buf.length) {
      const block = buf.join('\n');
      if (spec.regionStart.test(block)) {
        const tokens = normalizeTokens(block, spec);
        if (tokens.length >= minTokens) {
          const shingles = [];
          for (let j = 0; j <= tokens.length - k; j++)
            shingles.push(tokens.slice(j, j + k).join(' '));
          regions.push({ startLine, tokens, shingles });
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

/* ---------- Discovery (scoped, staged) ---------- */
function discoverFiles(context, cfg, root) {
  const abs = getFilesToCheck(context);
  const rel = abs.map((a) => path.relative(root, a));
  return rel
    .filter((r) => !(cfg.exclude && micromatch.isMatch(r, cfg.exclude, { dot: true })))
    .filter((r) => {
      if (cfg.considerTestFiles) return true;
      return !micromatch.isMatch(r, cfg.testPatterns, { dot: true });
    })
    .map((r) => ({ rel: r, lang: langOf(r) }))
    .filter(
      (x) =>
        x.lang &&
        (cfg.languages[x.lang]?.length
          ? micromatch.isMatch(x.rel, cfg.languages[x.lang], { dot: true })
          : true)
    );
}

/* ---------- Name/shape collisions ---------- */
function collectPublicSymbols(text, spec) {
  const out = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(spec.publicSymbolLines);
    if (m) out.push({ name: m[1], line: i + 1 });
  }
  return out;
}

/* ---------- Main check ---------- */
export function runDuplicationGate(context = 'commit') {
  const root = repoRoot();
  const { cfg, exceptions } = loadCfg(root);
  const baseRef = resolveBaseRef(root, cfg.ciBaseRef);

  const files = discoverFiles(context, cfg, root);

  // Build regions & symbol tables
  const fileData = [];
  const baseNameMapPerPkg = new Map(); // pkg|basename -> count
  for (const f of files) {
    const staged = readStaged(root, f.rel);
    if (!staged) continue;
    const spec = LANG[f.lang];
    const pkgRoot = findPackageRoot(path.join(root, f.rel), root, cfg.packageMarkers);
    const pkgKey = path.relative(root, pkgRoot);
    // file duplicates (within package)
    const bnKey = `${pkgKey}|${path.basename(f.rel)}`;
    baseNameMapPerPkg.set(bnKey, (baseNameMapPerPkg.get(bnKey) || 0) + 1);
    // regions and symbols
    const regions = extractRegions(staged, spec, cfg.minTokensPerRegion, cfg.shingleSize);
    const symbols = collectPublicSymbols(staged, spec);
    fileData.push({ ...f, pkgKey, regions, symbols });
  }

  /* ---- Functional clone pairs via shingles ---- */
  const shingleMap = new Map(); // shingle -> [fileIndex, regionIndex]
  fileData.forEach((fd, fi) =>
    fd.regions.forEach((r, ri) => {
      for (const sh of r.shingles) {
        const arr = shingleMap.get(sh);
        if (arr) arr.push([fi, ri]);
        else shingleMap.set(sh, [[fi, ri]]);
      }
    })
  );
  const pairMap = new Map();
  for (const [, hits] of shingleMap) {
    if (hits.length < 2) continue;
    for (let i = 0; i < hits.length; i++)
      for (let j = i + 1; j < hits.length; j++) {
        const a = hits[i],
          b = hits[j];
        const key = `${a[0]},${a[1]}|${b[0]},${b[1]}`;
        pairMap.set(key, (pairMap.get(key) || 0) + 1);
      }
  }
  const pairFindings = [];
  for (const [key] of pairMap) {
    const [a, b] = key.split('|');
    const [fi, ri] = a.split(',').map(Number);
    const [fj, rj] = b.split(',').map(Number);
    const A = fileData[fi],
      B = fileData[fj];
    if (!A || !B) continue;
    if (A.rel === B.rel && Math.abs(A.regions[ri].startLine - B.regions[rj].startLine) < 5)
      continue;
    const s1 = new Set(A.regions[ri].shingles),
      s2 = new Set(B.regions[rj].shingles);
    const sim = jaccard(s1, s2);
    if (sim >= cfg.thresholds.jaccardWarn) {
      pairFindings.push({
        sim,
        files: [
          { file: A.rel, pkg: A.pkgKey, line: A.regions[ri].startLine, lang: A.lang },
          { file: B.rel, pkg: B.pkgKey, line: B.regions[rj].startLine, lang: B.lang },
        ],
      });
    }
  }

  /* ---- Cluster by stem within package (context) ---- */
  function normStem(rel) {
    const base = path
      .basename(rel)
      .toLowerCase()
      .replace(/\.[^.]+$/, '');
    return base.replace(/[-_.]v?\d+$/i, '').replace(/[-_.](final|copy|new|next)$/i, '');
  }
  const clusters = new Map(); // pkg|stem -> Set<file>
  for (const p of pairFindings)
    for (const s of p.files) {
      const key = `${s.pkg}|${normStem(s.file)}`;
      if (!clusters.has(key)) clusters.set(key, new Set());
      clusters.get(key).add(s.file);
    }

  /* ---- Name/shape collisions (public symbols) ---- */
  const allow = new Set((cfg.nameDuplication?.allowNames ?? []).map((s) => s.toLowerCase()));
  const nameCounts = new Map(); // symbolName -> count across repo
  const nameSites = new Map(); // symbolName -> [{file,line}]
  for (const fd of fileData) {
    for (const sym of fd.symbols) {
      const name = sym.name;
      if (allow.has(name.toLowerCase())) continue;
      nameCounts.set(name, (nameCounts.get(name) || 0) + 1);
      const arr = nameSites.get(name) || [];
      arr.push({ file: fd.rel, line: sym.line });
      nameSites.set(name, arr);
    }
  }
  const duplicateSymbols = [];
  for (const [name, count] of nameCounts) {
    if (count > 1) duplicateSymbols.push({ name, count, sites: nameSites.get(name) || [] });
  }

  /* ---- File duplicates inside a package ---- */
  const dupBasenames = [];
  for (const [key, count] of baseNameMapPerPkg) {
    if (count > 1) {
      const [pkg, bn] = key.split('|');
      dupBasenames.push({ pkg, basename: bn, count });
    }
  }

  /* ---- Build violations & warnings ---- */
  const violations = [];
  const warnings = [];

  // Pair-level functional clones
  for (const p of pairFindings.sort((a, b) => b.sim - a.sim)) {
    const severity = p.sim >= cfg.thresholds.jaccardBlock ? 'block' : 'warn';
    const v = {
      type: 'functional_duplicate_pair',
      similarity: p.sim,
      files: p.files,
      severity,
      rule: `Rename-invariant clone via ${cfg.shingleSize}-shingles`,
      message: `Jaccard ${p.sim.toFixed(2)} between:\n  - ${p.files[0].file}:${p.files[0].line}\n  - ${p.files[1].file}:${p.files[1].line}`,
    };
    (severity === 'block' ? violations : warnings).push(v);
  }

  // Cluster context
  for (const [key, set] of clusters) {
    const sz = set.size;
    if (sz >= cfg.thresholds.clusterSizeWarn) {
      const severity = sz >= cfg.thresholds.clusterSizeBlock ? 'block' : 'warn';
      const [pkg, stem] = key.split('|');
      const v = {
        type: 'functional_duplicate_cluster',
        package: pkg,
        stem,
        size: sz,
        severity,
        rule: 'Multiple files implement same stem within package',
        message: `Cluster '${stem}' in ${pkg} has ${sz} members`,
      };
      (severity === 'block' ? violations : warnings).push(v);
    }
  }

  // Name/shape collisions (regression-aware against configured baselines)
  if (cfg.nameDuplication?.enable) {
    const baselines = cfg.nameDuplication.regressionBaselines || {};
    const dupStructs = duplicateSymbols.filter((x) => /^[A-Z]/.test(x.name)); // very rough: types/structs/classes
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

  // File duplicates by basename within same package (contextual)
  for (const d of dupBasenames) {
    warnings.push({
      type: 'basename_duplicate_within_package',
      severity: 'warn',
      message: `Multiple files named '${d.basename}' in package ${d.pkg} (count=${d.count})`,
    });
  }

  // Let your exception framework finalize severities/waivers
  const processed = processViolations('duplication_gate', [...violations, ...warnings], context, {
    defaultSeverity: (v) => v.severity || 'warn',
  });

  return {
    violations: processed.violations,
    warnings: processed.warnings,
    enforcementLevel: processed.enforcementLevel,
  };
}

/* ---------- CLI ---------- */
function main() {
  const ctx = process.argv[2] || 'commit';
  const res = runDuplicationGate(ctx);

  if (res.warnings.length) {
    console.log(`Warnings: ${res.warnings.length}`);
    for (const w of res.warnings.slice(0, 12)) console.log(`- ${w.type}: ${w.message}`);
    console.log('');
  }

  if (res.violations.length) {
    console.log(`Blocking findings: ${res.violations.length}`);
    for (const v of res.violations) console.log(`- ${v.type}: ${v.message}`);
    process.exit(1);
  }

  console.log('No blocking duplication issues.');
  process.exit(0);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
