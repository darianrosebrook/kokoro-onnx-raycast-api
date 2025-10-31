#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Hidden TODO Pattern Analyzer (Node.js)
 *
 * Automatically detects and reports hidden incomplete implementations including:
 * - Hidden TODO comments with sophisticated pattern matching
 * - Placeholder implementations and stub code
 * - Temporary solutions and workarounds
 * - Hardcoded values and constants
 * - Future improvement markers
 */

/**
 * Quality Issue class for reporting findings
 */
class QualityIssue {
  constructor(
    file_path,
    line_number,
    severity,
    rule_id,
    message,
    confidence = 1.0,
    suggested_fix = ''
  ) {
    this.file_path = file_path;
    this.line_number = line_number;
    this.severity = severity;
    this.rule_id = rule_id;
    this.message = message;
    this.confidence = confidence;
    this.suggested_fix = suggested_fix;
  }
}

/**
 * Hidden TODO Analyzer class
 */
class HiddenTodoAnalyzer {
  constructor(projectRoot = '.') {
    this.projectRoot = path.resolve(projectRoot);

    // Define sophisticated hidden TODO patterns
    this.hiddenTodoPatterns = [
      // Incomplete implementation patterns
      /\\bnot\\s+yet\\s+implemented\\b/i,
      /\\bmissing\\s+implementation\\b/i,
      /\\bincomplete\\s+implementation\\b/i,
      /\\bpartial\\s+implementation\\b/i,
      /\\bunimplemented\\b/i,
      /\\bnot\\s+done\\b/i,
      /\\bpending\\s+implementation\\b/i,
      /\\bto\\s+be\\s+implemented\\b/i,
      /\\bwill\\s+be\\s+implemented\\b/i,
      /\\bcoming\\s+soon\\b/i,
      /\\bwork\\s+in\\s+progress\\b/i,
      /\\bwip\\b/i,

      // Placeholder code patterns
      /\\bplaceholder\\s+code\\b/i,
      /\\bplaceholder\\s+implementation\\b/i,
      /\\bstub\\s+implementation\\b/i,
      /\\bdummy\\s+implementation\\b/i,
      /\\bfake\\s+implementation\\b/i,
      /\\bsimplified\\s+.*?\\s+implementation\\b/i,
      /\\bfor\\s+now\\b.*?just|simply|only\\b/i,
      /\\btemporary\\s+implementation\\b/i,
      /\\bmock\\s+implementation\\b/i,
      /\\bsample\\s+implementation\\b/i,

      // Temporary solution patterns
      /\\btemporary\\s+solution\\b/i,
      /\\btemporary\\s+fix\\b/i,
      /\\bquick\\s+fix\\b/i,
      /\\bworkaround\\b/i,
      /\\bhack\\b.*?fix|solution\\b/i,
      /\\bband-aid\\s+solution\\b/i,
      /\\bkludge\\b/i,
      /\\bcrude\\s+solution\\b/i,
      /\\brough\\s+implementation\\b/i,

      // Hardcoded value patterns
      /\\bhardcoded\\s+value\\b/i,
      /\\bmagic\\s+number\\b/i,
      /\\bmagic\\s+string\\b/i,
      /\\bconstant\\s+value\\b.*?replace|change|make\\s+configurable\\b/i,
      /\\bfixed\\s+value\\b/i,
      /\\bstatic\\s+value\\b/i,
      /\\bhardcoded\\s+constant\\b/i,

      // Future improvement patterns
      /\\bin\\s+production\\b.*?implement|add|fix\\b/i,
      /\\bin\\s+a\\s+real\\s+implementation\\b/i,
      /\\beventually\\b.*?implement|add|fix\\b/i,
      /\\bshould\\s+be\\b.*?implemented|added|fixed\\b/i,
      /\\bwould\\s+be\\b.*?implemented|added|fixed\\b/i,
      /\\bmight\\s+be\\b.*?implemented|added|fixed\\b/i,
      /\\bcould\\s+be\\b.*?implemented|added|fixed\\b/i,
      /\\blater\\b.*?implement|add|fix\\b/i,
      /\\bsomeday\\b.*?implement|add|fix\\b/i,
    ];

    // Language-specific code stub detection
    this.codeStubPatterns = {
      javascript: {
        functionStub: /function\s+\w+\(.*\)\s*\{/g,
        throwNotImpl:
          /throw\s+new\s+Error\(\s*[''`](TODO|Not\s+Implemented|Not\s+Yet\s+Implemented)[''`]/i,
        returnTodo: /return\s+(null|undefined);\s*\/\/\s*(TODO|PLACEHOLDER)/i,
        consoleLogStub: /console\.log.*;\s*\/\/\s*(TODO|PLACEHOLDER|STUB)/i,
        emptyFunction: /function\s+\w+\(.*\)\s*\{\s*\}\s*$/g,
        returnMock: /return\s+\{.*?\};\s*\/\/\s*(MOCK|FAKE|DUMMY)/i,
      },
      typescript: {
        functionStub: /(async\s+)?function\s+\w+\(.*\)\s*\{/g,
        throwNotImpl:
          /throw\s+new\s+Error\(\s*[''`](TODO|Not\s+Implemented|Not\s+Yet\s+Implemented)[''`]/i,
        returnTodo: /return\s+(null|undefined);\s*\/\/\s*(TODO|PLACEHOLDER)/i,
        consoleLogStub: /console\.log.*;\s*\/\/\s*(TODO|PLACEHOLDER|STUB)/i,
        emptyFunction: /(async\s+)?function\s+\w+\(.*\)\s*\{\s*\}\s*$/g,
        returnMock: /return\s+\{.*?\};\s*\/\/\s*(MOCK|FAKE|DUMMY)/i,
      },
      python: {
        functionStub: /^\s*def\s+\w+\(.*\):/gm,
        passStmt: /^\s*pass\s*$/gm,
        ellipsisStmt: /^\s*\.\.\.\s*$/gm,
        raiseNotImpl: /^\s*raise\s+NotImplementedError/gm,
        returnNone: /^\s*return\s+None\s*#\s*(TODO|PLACEHOLDER)/gm,
        printStub: /^\s*print\(.*\)\s*#\s*(TODO|PLACEHOLDER|STUB)/gm,
        emptyFunction: /^\s*def\s+\w+\(.*\):\s*pass\s*$/gm,
      },
      rust: {
        functionStub: /^\s*(async\s+)?fn\s+\w+\(.*\)\s*->\s*\w+\s*\{/gm,
        todoMacro: /^\s*todo!\(\)/gm,
        unimplementedMacro: /^\s*unimplemented!\(\)/gm,
        panicStub: /^\s*panic!\('TODO'\)/gm,
        returnDefault: /^\s*Default::default\(\);?\s*\/\/\s*(TODO|PLACEHOLDER)/gm,
      },
      go: {
        functionStub: /^\s*func\s+\w+\(.*\)\s*\w*\s*\{/gm,
        panicStub: /^\s*panic\('TODO'\)/gm,
        returnNil: /^\s*return\s+nil;?\s*\/\/\s*(TODO|PLACEHOLDER)/gm,
      },
      java: {
        functionStub: /^\s*(public|private|protected)?\s*\w+\s+\w+\(.*\)\s*\{\s*\}/gm,
        throwTodo: /^\s*throw\s+new\s+\w*Exception\('TODO/i,
        returnNull: /^\s*return\s+null;?\s*\/\/\s*(TODO|PLACEHOLDER)/gm,
      },
    };

    // Excluded directories and files
    this.excludedDirs = [
      'node_modules',
      '.git',
      'target',
      'dist',
      'build',
      '__pycache__',
      '.venv',
      '.stryker-tmp',
      'site-packages',
      '.dist-info',
      '.whl',
      'venv',
      'env',
      'virtualenv',
      'conda',
      'anaconda',
      '.build',
      'checkouts',
      'Tests',
      'examples',
      'models',
      'vocabs',
      'merges',
    ];

    // Excluded file patterns
    this.excludedFilePatterns = [
      '.venv',
      'site-packages',
      '.dist-info',
      '.whl',
      '.build',
      'checkouts',
      'Tests',
      'examples',
      'models',
      'vocabs',
      'merges',
      'LICENSE.txt',
      'bert-vocab.txt',
      'bench-all-gg.txt',
      'CMakeLists.txt',
    ];
  }

  /**
   * Analyze the entire project for hidden TODOs
   */
  async analyzeProject(showProgress = true, scopedFiles = null, engineeringSuggestions = false) {
    const allIssues = [];
    const filesToAnalyze = scopedFiles || this.findFilesToAnalyze();

    if (showProgress && filesToAnalyze.length > 0) {
      console.error(`Scanning ${filesToAnalyze.length} files for hidden TODOs...`);
    }

    // Process files in parallel batches for better performance
    const batchSize = 8; // Process 8 files concurrently
    let processedCount = 0;

    for (let batchStart = 0; batchStart < filesToAnalyze.length; batchStart += batchSize) {
      const batchEnd = Math.min(batchStart + batchSize, filesToAnalyze.length);
      const batch = filesToAnalyze.slice(batchStart, batchEnd);

      // Process batch in parallel
      const batchPromises = batch.map((filePath) =>
        this.analyzeFile(filePath, engineeringSuggestions)
      );
      const batchResults = await Promise.allSettled(batchPromises);

      // Collect results
      for (const result of batchResults) {
        if (result.status === 'fulfilled') {
          allIssues.push(...result.value);
        } else {
          console.error(`Error analyzing file: ${result.reason}`);
        }
      }

      processedCount += batch.length;

      if (showProgress) {
        const percent = (processedCount / filesToAnalyze.length) * 100;
        console.error(
          `Progress: ${processedCount}/${
            filesToAnalyze.length
          } files (${percent.toFixed(1)}%) - ${allIssues.length} issues found`
        );
      }
    }

    if (showProgress) {
      console.error(
        `Analysis complete: ${allIssues.length} total issues in ${filesToAnalyze.length} files`
      );
    }

    return allIssues;
  }

  /**
   * Analyze only git staged files for hidden TODOs
   */
  async analyzeStagedFiles(showProgress = true, engineeringSuggestions = false) {
    try {
      const { spawn } = await import('child_process');
      const gitDiff = spawn('git', ['diff', '--cached', '--name-only'], {
        cwd: this.projectRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      const files = [];
      let stdout = '';

      gitDiff.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      await new Promise((resolve, reject) => {
        gitDiff.on('close', (code) => {
          if (code === 0) {
            files.push(...stdout.trim().split('\n').filter(Boolean));
            resolve();
          } else {
            reject(new Error(`git diff failed with code ${code}`));
          }
        });
        gitDiff.on('error', reject);
      });

      // Filter to only include files that exist and are analyzable
      const analyzableFiles = files.filter((file) => {
        const fullPath = path.join(this.projectRoot, file);
        return fs.existsSync(fullPath) && this.shouldAnalyzeFile(file);
      });

      return await this.analyzeProject(showProgress, analyzableFiles, engineeringSuggestions);
    } catch (error) {
      console.error(`Error analyzing staged files: ${error.message}`);
      return [];
    }
  }

  /**
   * Check if a file should be analyzed based on its extension
   */
  shouldAnalyzeFile(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    return [
      '.js',
      '.jsx',
      '.ts',
      '.tsx',
      '.py',
      '.rs',
      '.go',
      '.java',
      '.cpp',
      '.c',
      '.h',
      '.hpp',
    ].includes(ext);
  }

  /**
   * Analyze TODO comment for engineering-grade format suggestions
   */
  analyzeEngineeringSuggestions(comment, filePath) {
    const normalized = comment.trim();
    if (!normalized) {
      return { needsEngineeringFormat: false };
    }

    // Only analyze explicit TODOs
    if (!/\b(TODO|FIXME|HACK)\b/i.test(normalized)) {
      return { needsEngineeringFormat: false };
    }

    const suggestions = {
      needsEngineeringFormat: false,
      suggestions: '',
      templateSuggestion: '',
      missingElements: [],
      suggestedTier: 'Medium',
      priority: 'Medium',
    };

    // Check if already has engineering-grade structure
    const hasStructure = this.checkEngineeringGradeStructure(normalized);

    if (!hasStructure) {
      suggestions.needsEngineeringFormat = true;

      // Check what's missing
      const missing = this.identifyMissingElements(normalized);
      suggestions.missingElements = missing;

      // Generate suggestions
      suggestions.suggestions = this.generateSuggestionsText(missing);
      suggestions.templateSuggestion = this.generateTemplateSuggestion(normalized, missing);
    }

    return suggestions;
  }

  /**
   * Check if comment already has engineering-grade structure
   */
  checkEngineeringGradeStructure(comment) {
    const patterns = {
      completionChecklist: [
        /\bCOMPLETION CHECKLIST\b/i,
        /\bchecklist\b.*?:/i,
        /\[ \].*\b(implement|add|fix|complete)\b/i,
      ],
      acceptanceCriteria: [
        /\bACCEPTANCE CRITERIA\b/i,
        /\bacceptance\b.*?:/i,
        /\bwhen\b.*?\bthen\b/i,
      ],
      dependencies: [
        /\bDEPENDENCIES\b/i,
        /\bdepends on\b/i,
        /\brequires\b.*?(system|feature|module)/i,
      ],
      governance: [/\bGOVERNANCE\b/i, /\bCAWS Tier\b/i, /\bPRIORITY\b/i, /\bBLOCKING\b/i],
    };

    for (const [category, categoryPatterns] of Object.entries(patterns)) {
      for (const pattern of categoryPatterns) {
        if (pattern.test(comment)) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * Identify missing engineering-grade elements
   */
  identifyMissingElements(comment) {
    const missing = [];

    if (
      !/\bCOMPLETION CHECKLIST\b/i.test(comment) &&
      !/\bchecklist\b.*?:/i.test(comment) &&
      !/\[ \].*\b(implement|add|fix|complete)\b/i.test(comment)
    ) {
      missing.push('completion_checklist');
    }

    if (
      !/\bACCEPTANCE CRITERIA\b/i.test(comment) &&
      !/\bacceptance\b.*?:/i.test(comment) &&
      !/\bwhen\b.*?\bthen\b/i.test(comment)
    ) {
      missing.push('acceptance_criteria');
    }

    if (
      !/\bDEPENDENCIES\b/i.test(comment) &&
      !/\bdepends on\b/i.test(comment) &&
      !/\brequires\b.*?(system|feature|module)/i.test(comment)
    ) {
      missing.push('dependencies');
    }

    if (
      !/\bGOVERNANCE\b/i.test(comment) &&
      !/\bCAWS Tier\b/i.test(comment) &&
      !/\bPRIORITY\b/i.test(comment)
    ) {
      missing.push('governance');
    }

    return missing;
  }

  /**
   * Generate human-readable suggestions text
   */
  generateSuggestionsText(missingElements) {
    const suggestions = [];

    if (missingElements.includes('completion_checklist')) {
      suggestions.push('• Add COMPLETION CHECKLIST with specific, measurable tasks');
    }

    if (missingElements.includes('acceptance_criteria')) {
      suggestions.push('• Add ACCEPTANCE CRITERIA defining done state (Given/When/Then)');
    }

    if (missingElements.includes('dependencies')) {
      suggestions.push('• Add DEPENDENCIES section listing required systems/features');
    }

    if (missingElements.includes('governance')) {
      suggestions.push('• Add GOVERNANCE section with CAWS Tier, priority, blocking status');
    }

    return suggestions.join('\n');
  }

  /**
   * Generate a template suggestion for the TODO
   */
  generateTemplateSuggestion(originalComment, missingElements) {
    const lines = originalComment.split('\n');
    const firstLine = lines[0].trim();

    let template = `// ${firstLine}\n`;
    template += '//       <One-sentence context & why this exists>\n';
    template += '//\n';

    if (missingElements.includes('completion_checklist')) {
      template += '// COMPLETION CHECKLIST:\n';
      template += '// [ ] Primary functionality implemented\n';
      template += '// [ ] API/data structures defined & stable\n';
      template += '// [ ] Error handling + validation aligned with error taxonomy\n';
      template += '// [ ] Tests: Unit ≥80% branch coverage (≥50% mutation if enabled)\n';
      template += '// [ ] Integration tests for external systems/contracts\n';
      template += '// [ ] Documentation: public API + system behavior\n';
      template += '// [ ] Performance/profiled against SLA (CPU/mem/latency throughput)\n';
      template += '// [ ] Security posture reviewed (inputs, authz, sandboxing)\n';
      template += '// [ ] Observability: logs (debug), metrics (SLO-aligned), tracing\n';
      template += '// [ ] Configurability and feature flags defined if relevant\n';
      template += '// [ ] Failure-mode cards documented (degradation paths)\n';
      template += '//\n';
    }

    if (missingElements.includes('acceptance_criteria')) {
      template += '// ACCEPTANCE CRITERIA:\n';
      template += '// - <User-facing measurable behavior>\n';
      template += '// - <Invariant or schema contract requirements>\n';
      template += '// - <Performance/statistical bounds>\n';
      template += '// - <Interoperation requirements or protocol contract>\n';
      template += '//\n';
    }

    if (missingElements.includes('dependencies')) {
      template += '// DEPENDENCIES:\n';
      template += '// - <System or feature this relies on> (Required/Optional)\n';
      template += '// - <Interop/contract references>\n';
      template += '// - File path(s)/module links to dependent code\n';
      template += '//\n';
    }

    if (missingElements.includes('governance')) {
      template += '// ESTIMATED EFFORT: <Number + confidence range>\n';
      template += '// PRIORITY: Medium\n';
      template += '// BLOCKING: {Yes/No} – If Yes: explicitly list what it blocks\n';
      template += '//\n';
      template += '// GOVERNANCE:\n';
      template += '// - CAWS Tier: 3 (impacts rigor, provenance, review policy)\n';
      template += '// - Change Budget: <LOC or file count> (if relevant)\n';
      template += '// - Reviewer Requirements: <Roles or domain expertise>\n';
    }

    return template;
  }

  /**
   * Find all files that should be analyzed
   */
  findFilesToAnalyze() {
    const filesToAnalyze = [];

    function walkDirectory(dir) {
      try {
        const items = fs.readdirSync(dir);

        for (const item of items) {
          const fullPath = path.join(dir, item);
          const stat = fs.statSync(fullPath);

          if (stat.isDirectory()) {
            // Skip excluded directories
            if (!this.excludedDirs.some((excluded) => fullPath.includes(excluded))) {
              walkDirectory.call(this, fullPath);
            }
          } else if (stat.isFile()) {
            // Skip excluded files
            if (!this.excludedFilePatterns.some((pattern) => fullPath.includes(pattern))) {
              // Include source code files
              const ext = path.extname(fullPath).toLowerCase();
              if (
                [
                  '.js',
                  '.jsx',
                  '.ts',
                  '.tsx',
                  '.py',
                  '.rs',
                  '.go',
                  '.java',
                  '.cpp',
                  '.c',
                  '.h',
                  '.hpp',
                ].includes(ext)
              ) {
                filesToAnalyze.push(fullPath);
              }
            }
          }
        }
      } catch (error) {
        // Skip directories we can't read
      }
    }

    walkDirectory.call(this, this.projectRoot);
    return filesToAnalyze;
  }

  /**
   * Analyze a single file for hidden TODOs
   */
  async analyzeFile(filePath, engineeringSuggestions = false) {
    const issues = [];

    try {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.split('\\n');
      const fileExt = path.extname(filePath).toLowerCase();
      const language = this.detectLanguage(fileExt);

      for (let lineNum = 0; lineNum < lines.length; lineNum++) {
        const line = lines[lineNum];
        const originalLineNum = lineNum + 1;

        // Check for hidden TODO patterns in comments
        if (this.isCommentLine(line, language)) {
          const confidence = this.calculateConfidence(line, language);

          if (confidence >= 0.6) {
            let foundMatch = false;

            // Check hidden TODO patterns first
            for (const pattern of this.hiddenTodoPatterns) {
              if (pattern.test(line)) {
                let message = `Hidden incomplete implementation detected: '${line.trim()}'`;
                let suggestedFix = 'Replace with complete implementation or remove TODO marker';

                // Add engineering suggestions if requested
                if (engineeringSuggestions) {
                  const engineeringData = this.analyzeEngineeringSuggestions(line, filePath);
                  if (engineeringData.needsEngineeringFormat) {
                    message += `\n\n💡 Engineering-grade format suggestions:\n${engineeringData.suggestions}`;
                    suggestedFix = engineeringData.templateSuggestion || suggestedFix;
                  }
                }

                issues.push(
                  new QualityIssue(
                    filePath,
                    originalLineNum,
                    'error',
                    'HIDDEN_TODO',
                    message,
                    confidence,
                    suggestedFix
                  )
                );
                foundMatch = true;
                break; // Only report one issue per line
              }
            }

            // If no hidden pattern matched but confidence is high and it's an explicit TODO,
            // flag it as an explicit TODO that should be addressed
            if (!foundMatch && /\bTODO\b/i.test(line) && confidence >= 0.7) {
              let message = `Explicit TODO detected in production code: '${line.trim()}'`;
              let suggestedFix = 'Implement the TODO or remove it from production code';

              // Add engineering suggestions if requested
              if (engineeringSuggestions) {
                const engineeringData = this.analyzeEngineeringSuggestions(line, filePath);
                if (engineeringData.needsEngineeringFormat) {
                  message += `\n\n💡 Engineering-grade format suggestions:\n${engineeringData.suggestions}`;
                  suggestedFix = engineeringData.templateSuggestion || suggestedFix;
                }
              }

              issues.push(
                new QualityIssue(
                  filePath,
                  originalLineNum,
                  'warning', // Explicit TODOs are warnings, not errors
                  'EXPLICIT_TODO',
                  message,
                  confidence,
                  suggestedFix
                )
              );
            }
          }
        }

        // Check for code stub patterns
        if (language && this.codeStubPatterns[language]) {
          const stubPatterns = this.codeStubPatterns[language];

          for (const [patternName, pattern] of Object.entries(stubPatterns)) {
            const matches = line.match(pattern);
            if (matches) {
              issues.push(
                new QualityIssue(
                  filePath,
                  originalLineNum,
                  'error',
                  'CODE_STUB',
                  `Code stub pattern detected (${patternName}): '${line.trim()}'`,
                  0.8,
                  'Implement complete functionality or remove stub code'
                )
              );
            }
          }
        }
      }
    } catch (error) {
      issues.push(
        new QualityIssue(
          filePath,
          0,
          'error',
          'FILE_READ_ERROR',
          `Could not analyze file: ${error.message}`,
          1.0,
          'Check file permissions and encoding'
        )
      );
    }

    return issues;
  }

  /**
   * Detect programming language from file extension
   */
  detectLanguage(ext) {
    const languageMap = {
      '.js': 'javascript',
      '.jsx': 'javascript',
      '.ts': 'typescript',
      '.tsx': 'typescript',
      '.py': 'python',
      '.rs': 'rust',
      '.go': 'go',
      '.java': 'java',
      '.cpp': 'cpp',
      '.c': 'c',
      '.h': 'c',
      '.hpp': 'cpp',
    };

    return languageMap[ext];
  }

  /**
   * Check if a line is a comment
   */
  isCommentLine(line, language) {
    const trimmed = line.trim();

    switch (language) {
      case 'javascript':
      case 'typescript':
        return (
          trimmed.startsWith('//') ||
          trimmed.startsWith('/*') ||
          trimmed.includes('/*') ||
          trimmed.includes('*/')
        );
      case 'python':
        return trimmed.startsWith('#');
      case 'rust':
        return (
          trimmed.startsWith('//') ||
          trimmed.startsWith('/*') ||
          trimmed.includes('/*') ||
          trimmed.includes('*/')
        );
      case 'go':
        return trimmed.startsWith('//');
      case 'java':
        return (
          trimmed.startsWith('//') ||
          trimmed.startsWith('/*') ||
          trimmed.includes('/*') ||
          trimmed.includes('*/')
        );
      case 'cpp':
      case 'c':
        return (
          trimmed.startsWith('//') ||
          trimmed.startsWith('/*') ||
          trimmed.includes('/*') ||
          trimmed.includes('*/')
        );
      default:
        return (
          trimmed.startsWith('//') ||
          trimmed.startsWith('#') ||
          trimmed.startsWith('/*') ||
          trimmed.includes('/*') ||
          trimmed.includes('*/')
        );
    }
  }

  /**
   * Calculate confidence score for a potential hidden TODO
   */
  calculateConfidence(line, language) {
    let score = 0.0;

    // Check for TODO indicators (increase score)
    if (/\bTODO\b/i.test(line)) {
      score += 0.3;
    }

    // Check for implementation context (increase score)
    if (/\b(implement|implementation|fix|add|create|build)\b/i.test(line)) {
      score += 0.2;
    }

    // Check for business logic context (increase score)
    if (
      /\b(feature|function|method|class|component|service|api|auth|authentication|user|login|security)\b/i.test(
        line
      )
    ) {
      score += 0.3;
    }

    // Check for documentation indicators (decrease score)
    if (/\b(example|sample|demo|test|spec|readme|doc)\b/i.test(line)) {
      score -= 0.5;
    }

    // Check if it's in a generated file (decrease score)
    if (/\bgenerated\b|\bauto-generated\b|\bdo not edit\b/i.test(line)) {
      score -= 0.4;
    }

    // Check for legitimate technical terms (decrease score)
    const legitimateTerms = [
      /\bperformance\s+monitoring\b/i,
      /\bperformance\s+optimization\b/i,
      /\bfallback\s+mechanism\b/i,
      /\bbasic\s+authentication\b/i,
      /\bmock\s+object\b/i,
      /\bcurrent\s+implementation.*?(uses|provides|supports)\b/i,
      /\bexample\s+implementation\b/i,
      /\bsample\s+code\b/i,
      /\bdemo\s+implementation\b/i,
      /\btest\s+implementation\b/i,
    ];

    for (const term of legitimateTerms) {
      if (term.test(line)) {
        score -= 0.6;
        break;
      }
    }

    return Math.max(-1.0, Math.min(1.0, score));
  }

  /**
   * Generate a report from the analysis results
   */
  generateReport(issues, outputFormat = 'text') {
    if (outputFormat === 'json') {
      return JSON.stringify(
        issues.map((issue) => ({
          file: issue.file_path,
          line: issue.line_number,
          severity: issue.severity,
          rule: issue.rule_id,
          message: issue.message,
          confidence: issue.confidence,
          suggested_fix: issue.suggested_fix,
        })),
        null,
        2
      );
    }

    const report = [];

    // Group by severity
    const errors = issues.filter((i) => i.severity === 'error');
    const warnings = issues.filter((i) => i.severity === 'warning');

    report.push(`Hidden TODO Analysis Report`);
    report.push(`==========================`);
    report.push(``);
    report.push(`Total files analyzed: ${new Set(issues.map((i) => i.file_path)).size}`);
    report.push(`Total issues found: ${issues.length}`);
    report.push(`Errors: ${errors.length}`);
    report.push(`Warnings: ${warnings.length}`);
    report.push(``);

    if (errors.length > 0) {
      report.push(`❌ ERRORS (${errors.length}):`);
      for (const issue of errors.slice(0, 10)) {
        // Show first 10
        const confidencePercent = (issue.confidence * 100).toFixed(1);
        report.push(
          `  ${path.relative(this.projectRoot, issue.file_path)}:${
            issue.line_number
          } (${confidencePercent}% confidence)`
        );
        report.push(`    ${issue.message}`);
        if (issue.suggested_fix) {
          report.push(`    💡 ${issue.suggested_fix}`);
        }
        report.push(``);
      }

      if (errors.length > 10) {
        report.push(`  ... and ${errors.length - 10} more errors`);
      }
    }

    if (warnings.length > 0) {
      report.push(`⚠️  WARNINGS (${warnings.length}):`);
      for (const issue of warnings.slice(0, 10)) {
        // Show first 10
        const confidencePercent = (issue.confidence * 100).toFixed(1);
        report.push(
          `  ${path.relative(this.projectRoot, issue.file_path)}:${
            issue.line_number
          } (${confidencePercent}% confidence)`
        );
        report.push(`    ${issue.message}`);
        if (issue.suggested_fix) {
          report.push(`    💡 ${issue.suggested_fix}`);
        }
        report.push(``);
      }

      if (warnings.length > 10) {
        report.push(`  ... and ${warnings.length - 10} more warnings`);
      }
    }

    return report.join('\\n');
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);
  let pathArg = '.';
  let outputFormat = 'text';
  let minConfidence = 0.6;
  let showProgress = true;
  let exitCode = false;
  let scopedFiles = null;
  let engineeringSuggestions = false;
  let stagedOnly = false;

  // Parse arguments
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case '--path':
        pathArg = args[++i];
        break;
      case '--format':
        outputFormat = args[++i];
        break;
      case '--min-confidence':
        minConfidence = parseFloat(args[++i]);
        break;
      case '--no-progress':
        showProgress = false;
        break;
      case '--exit-code':
        exitCode = true;
        break;
      case '--scoped-files':
        // Read scoped files from stdin or file
        const scopedArg = args[++i];
        if (scopedArg === '-') {
          // Read from stdin (async approach for reliability)
          const stdinData = [];
          process.stdin.on('data', (chunk) => stdinData.push(chunk));
          await new Promise((resolve) => {
            process.stdin.on('end', () => {
              scopedFiles = Buffer.concat(stdinData).toString().trim().split('\n').filter(Boolean);
              resolve();
            });
          });
        } else if (
          fs.existsSync(scopedArg) &&
          (scopedArg.endsWith('.txt') || scopedArg.endsWith('.list') || scopedArg.includes('files'))
        ) {
          // Read from file (only if it looks like a file list)
          scopedFiles = fs.readFileSync(scopedArg, 'utf8').trim().split('\n').filter(Boolean);
        } else {
          // Treat as a single file path from command line
          scopedFiles = [scopedArg];
        }
        break;
      case '--engineering-suggestions':
        engineeringSuggestions = true;
        break;
      case '--staged-only':
        stagedOnly = true;
        break;
      case '--help':
      case '-h':
        console.log(`
Hidden TODO Pattern Analyzer (Node.js v2.0)

Automatically detects and reports hidden incomplete implementations including:
- Hidden TODO comments with sophisticated pattern matching
- Placeholder implementations and stub code
- Temporary solutions and workarounds
- Hardcoded values and constants
- Future improvement markers

USAGE:
  node todo-analyzer.mjs [options] [path]

OPTIONS:
  --path <path>              Root directory to analyze (default: '.')
  --format <format>          Output format: text, json, md (default: text)
  --min-confidence <float>   Minimum confidence score 0.0-1.0 (default: 0.6)
  --no-progress              Disable progress reporting
  --exit-code                Exit with code 1 if issues found
  --scoped-files <file>      Analyze only specified files (one per line)
  --scoped-files -           Read file list from stdin
  --engineering-suggestions  Include engineering-grade TODO format suggestions
  --staged-only              Analyze only git staged files
  --help, -h                 Show this help message

EXAMPLES:
  node todo-analyzer.mjs                     # Analyze current directory
  node todo-analyzer.mjs --path src         # Analyze src directory
  node todo-analyzer.mjs --min-confidence 0.8 # Higher confidence threshold
  echo 'file1.rs\\nfile2.rs' | node todo-analyzer.mjs --scoped-files -
`);
        process.exit(0);
        break;
      default:
        if (arg.startsWith('--')) {
          console.error(`Unknown option: ${arg}`);
          process.exit(1);
        } else {
          pathArg = arg;
        }
    }
  }

  const analyzer = new HiddenTodoAnalyzer(pathArg);

  try {
    let issues;
    if (stagedOnly) {
      issues = await analyzer.analyzeStagedFiles(showProgress, engineeringSuggestions);
    } else {
      issues = await analyzer.analyzeProject(showProgress, scopedFiles, engineeringSuggestions);
    }

    // Filter by confidence
    const filteredIssues = issues.filter((issue) => issue.confidence >= minConfidence);

    const report = analyzer.generateReport(filteredIssues, outputFormat);
    console.log(report);

    if (exitCode && filteredIssues.length > 0) {
      // Exit with error code if there are issues
      const errors = filteredIssues.filter((i) => i.severity === 'error');
      if (errors.length > 0) {
        process.exit(1);
      }
    }
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

// Run CLI if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { HiddenTodoAnalyzer, QualityIssue };
