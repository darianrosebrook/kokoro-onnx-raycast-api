#!/usr/bin/env python3
"""
Hidden TODO Pattern Analyzer

@description: Hidden TODO analyzer with better accuracy, context awareness,
and reduced false positives. Uses semantic analysis and context clues to
distinguish between hidden TODOs and legitimate documentation.

@parameters:
- root_dir: The root directory to analyze.
- min_confidence: The minimum confidence score to consider a TODO.
- output_json: The path to save the JSON report.
- output_md: The path to save the Markdown report.
- verbose: Whether to print verbose output.
- enable_code_stub_scan: Whether to enable code stub detection heuristics.

For an example on clear TODOs, see the following code:
```rust
    // TODO: Implement ANE initialization with the following requirements:
    // 1. ANE initialization: Initialize Apple Neural Engine framework and resources
    //    - Set up ANE device and computation resources
    //    - Initialize ANE neural network computation capabilities
    //    - Handle ANE initialization error handling and recovery
    // 2. ANE resource setup: Set up ANE resources and memory
    //    - Allocate ANE memory and computation buffers
    //    - Set up ANE resource management and optimization
    //    - Implement ANE resource validation and verification
    // 3. ANE configuration: Configure ANE settings and parameters
    //    - Set up ANE computation parameters and settings
    //    - Configure ANE performance and optimization settings
    //    - Handle ANE configuration validation and verification
    // 4. ANE monitoring: Set up ANE monitoring and management
    //    - Initialize ANE performance monitoring
    //    - Set up ANE resource monitoring and management
    //    - Implement ANE monitoring and reporting
```

@author: @darianrosebrook
@date: 2025-10-17
@version: 2.0.0
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Any, Dict, List, Set, Tuple, Optional


class HiddenTodoAnalyzer:
    def __init__(self, root_dir: str, *, enable_code_stub_scan: bool = True):
        self.root_dir = Path(root_dir)
        self.enable_code_stub_scan = enable_code_stub_scan

        # Language-specific comment patterns
        self.language_patterns = {
            'rust': {
                'extensions': ['.rs'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'javascript': {
                'extensions': ['.js', '.mjs', '.cjs'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'typescript': {
                'extensions': ['.ts', '.tsx', '.mts', '.cts'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'python': {
                'extensions': ['.py', '.pyi'],
                'single_line': r'^\s*#',
                'multi_line_start': r'^\s*"""',
                'multi_line_end': r'"""',
            },
            'go': {
                'extensions': ['.go'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'java': {
                'extensions': ['.java'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'csharp': {
                'extensions': ['.cs'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'cpp': {
                'extensions': ['.cpp', '.cc', '.cxx', '.c++', '.hpp', '.h', '.hxx'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'c': {
                'extensions': ['.c'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'php': {
                'extensions': ['.php'],
                'single_line': r'^\s*//',
                'multi_line_start': r'^\s*/\*',
                'multi_line_end': r'\*/',
            },
            'ruby': {
                'extensions': ['.rb'],
                'single_line': r'^\s*#',
                'multi_line_start': r'^\s*=begin',
                'multi_line_end': r'=end',
            },
            'shell': {
                'extensions': ['.sh', '.bash', '.zsh', '.fish'],
                'single_line': r'^\s*#',
                'multi_line_start': None,
                'multi_line_end': None,
            },
            'yaml': {
                'extensions': ['.yaml', '.yml'],
                'single_line': r'^\s*#',
                'multi_line_start': None,
                'multi_line_end': None,
            },
            'json': {
                'extensions': ['.json'],
                'single_line': None,
                'multi_line_start': None,
                'multi_line_end': None,
            },
            'markdown': {
                'extensions': ['.md', '.markdown'],
                'single_line': r'^\s*<!--',
                'multi_line_start': r'^\s*<!--',
                'multi_line_end': r'-->',
            },
        }

        # Comprehensive list of file patterns to ignore
        self.ignored_file_patterns = [
            # Test files
            r'\btest\b',
            r'\btests\b',
            r'_test\.',
            r'_tests\.',
            r'\.test\.',
            r'\.spec\.',
            r'\.specs\.',

            # Build artifacts and generated files
            r'\btarget\b',
            r'\bbuild\b',
            r'\bout\b',
            r'\bdist\b',
            r'\bbin\b',
            r'\.next\b',
            r'generated\.',
            r'bindgen\.',
            r'private\.',
            r'mime_types_generated\.',
            r'named_entities\.',
            r'ascii_case_insensitive_html_attributes\.',

            # Package management
            r'\bnode_modules\b',
            r'package-lock\.json$',
            r'package\.json$',
            r'yarn\.lock$',
            r'pnpm-lock\.yaml$',
            r'\bvenv\b',
            r'\bpip\b',
            r'requirements\.txt$',
            r'Pipfile$',
            r'Pipfile\.lock$',
            r'poetry\.lock$',
            r'Cargo\.lock$',
            r'Cargo\.toml$',

            # Version control and IDE
            r'\.git\b',
            r'\.github\b',
            r'\.vscode\b',
            r'\.idea\b',
            r'\.DS_Store$',
            r'\.DS_Store\?$',
            r'\._',
            r'\.Spotlight-V100$',

            # Documentation and examples
            r'\bdocs\b',
            r'\bexamples\b',
            r'\bdoc\b',
            r'\bexample\b',

            # Temporary and cache files
            r'\bcache\b',
            r'\btmp\b',
            r'\btemp\b',
            r'\.tmp$',
            r'\.temp$',
            r'\.cache$',
            
            # Coverage and analysis reports
            r'\bhtmlcov\b',
            r'\bcoverage\b',
            r'\.coverage$',
            r'coverage\.xml$',
            r'lcov\.info$',

            # OS-specific files
            r'Thumbs\.db$',
            r'desktop\.ini$',
            r'\.fseventsd$',
            r'\.Trashes$',

            # Language-specific build artifacts
            r'\.rlib$',
            r'\.rmeta$',
            r'\.d$',
            r'\.pdb$',
            r'\.o$',
            r'\.obj$',
            r'\.exe$',
            r'\.dll$',
            r'\.so$',
            r'\.dylib$',
            r'\.pyc$',
            r'\.pyo$',
            r'__pycache__',
            r'\.class$',
            r'\.jar$',
            r'\.war$',
            r'\.ear$',

            # Web assets
            r'\.min\.js$',
            r'\.min\.css$',
            r'\.bundle\.js$',
            r'\.chunk\.js$',
            r'\.map$',

            # Configuration files (often generated)
            r'\.env\.local$',
            r'\.env\.production$',
            r'\.env\.development$',
            r'config\.local\.',
            r'config\.prod\.',
            r'config\.dev\.',
            
            # Logs and reports
            r'\blogs\b',
            r'\.log$',
            r'\breports\b',
            r'\bartifacts\b',
            r'\btemp\b',
            
            # IDE and editor files
            r'\.swp$',
            r'\.swo$',
            r'~$',
            r'\.bak$',
            r'\.backup$',
        ]

        # Explicit TODO patterns (highest priority) - more restrictive
        self.explicit_todo_patterns = {
            'explicit_todos': [
                r'\bTODO\b.*?:',
                r'\bFIXME\b.*?:',
                r'\bHACK\b.*?:',
                r'\bXXX\b.*?:',
                r'\bTEMP\b.*?:.*?(implement|fix|replace|complete|add)',
                r'\bTEMPORARY\b.*?:.*?(implement|fix|replace|complete|add)',
            ]
        }

        # High-confidence hidden TODO patterns (more specific and contextual)
        self.high_confidence_patterns = {
            'incomplete_implementation': [
                r'\bnot\s+yet\s+implemented\b',
                r'\bmissing\s+implementation\b',
                r'\bincomplete\s+implementation\b',
                r'\bpartial\s+implementation\b',
                r'\bunimplemented\b',
                r'\bnot\s+done\b',
                r'\bpending\s+implementation\b',
                r'\bto\s+be\s+implemented\b',
                r'\bwill\s+be\s+implemented\b',
            ],
            
            'placeholder_code': [
                r'\bplaceholder\s+code\b',
                r'\bplaceholder\s+implementation\b',
                r'\bplaceholder\s+function\b',
                r'\bplaceholder\s+value\b',
                r'\bstub\s+implementation\b',
                r'\bstub\s+function\b',
                r'\bdummy\s+implementation\b',
                r'\bfake\s+implementation\b',
                r'\bexample\s+implementation\b',
                r'\bdemo\s+implementation\b',
                r'\bsample\s+implementation\b',
                r'\btemplate\s+implementation\b',
            ],
            
            'temporary_solutions': [
                r'\btemporary\s+solution\b',
                r'\btemporary\s+fix\b',
                r'\btemporary\s+workaround\b',
                r'\bquick\s+fix\b',
                r'\bquick\s+hack\b',
                r'\bworkaround\b',
                r'\bhack\b.*?(fix|solution)',
                r'\bpatch\b.*?(fix|solution)',
                r'\bbypass\b.*?(fix|solution)',
            ],
            
            'hardcoded_values': [
                r'\bhardcoded\s+value\b',
                r'\bhard-coded\s+value\b',
                r'\bmagic\s+number\b',
                r'\bmagic\s+string\b',
                r'\bconstant\s+value\b.*?(replace|change|make\s+configurable)',
                r'\bdefault\s+value\b.*?(replace|change|make\s+configurable)',
            ],
            
            'future_improvements': [
                r'\bin\s+production\b.*?(implement|add|fix)',
                r'\bin\s+a\s+real\s+implementation\b',
                r'\beventually\b.*?(implement|add|fix)',
                r'\blater\b.*?(implement|add|fix)',
                r'\bshould\s+be\b.*?(implemented|added|fixed)',
                r'\bwould\s+be\b.*?(implemented|added|fixed)',
                r'\bcould\s+be\b.*?(implemented|added|fixed)',
                r'\bwill\s+be\b.*?(implemented|added|fixed)',
            ],
        }

        # Medium-confidence patterns (context-dependent)
        self.medium_confidence_patterns = {
            'basic_implementations': [
                r'\bbasic\s+implementation\b.*?(improve|enhance|replace)',
                r'\bsimple\s+implementation\b.*?(improve|enhance|replace)',
                r'\bminimal\s+implementation\b.*?(improve|enhance|replace)',
                r'\bnaive\s+implementation\b.*?(improve|enhance|replace)',
                r'\brough\s+implementation\b.*?(improve|enhance|replace)',
                r'\bcrude\s+implementation\b.*?(improve|enhance|replace)',
            ],
        }

        # Patterns to exclude (legitimate technical terms and documentation)
        self.exclusion_patterns = [
            # Performance and optimization terms
            r'\bperformance\s+monitoring\b',
            r'\bperformance\s+optimization\b',
            r'\bperformance\s+analysis\b',
            r'\bperformance\s+benchmark\b',
            r'\boptimize\s+for\s+performance\b',
            r'\boptimization\s+strategy\b',
            r'\befficient\s+implementation\b',
            
            # Simulation and testing terms
            r'\bsimulation\s+environment\b',
            r'\bsimulate\s+network\s+conditions\b',
            r'\bsimulate\s+.*?(behavior|response|data)\b',
            r'\bsimulation\s+.*?(mode|environment)\b',
            
            # Fallback and error handling
            r'\bfallback\s+mechanism\b',
            r'\bfallback\s+strategy\b',
            r'\bfallback\s+to\b.*?(method|function|implementation)',
            
            # Authentication and security
            r'\bbasic\s+authentication\b',
            r'\bbasic\s+configuration\b',
            r'\bsimple\s+interface\b',
            r'\bsimple\s+api\b',
            
            # Mock and testing
            r'\bmock\s+object\b',
            r'\bmock\s+service\b',
            r'\bmock\s+data\b',
            r'\bmock\s+response\b',
            
            # Documentation patterns
            r'\bcurrent\s+implementation\b.*?(uses|provides|supports)',
            r'\bthis\s+implementation\b.*?(uses|provides|supports)',
            r'\bthe\s+implementation\b.*?(uses|provides|supports)',
            r'\bimplementation\s+uses\b',
            r'\bimplementation\s+provides\b',
            r'\bimplementation\s+supports\b',
            
            # Architecture and design documentation
            r'\barchitecture\s+note\b',
            r'\bdesign\s+note\b',
            r'\bpattern\s+note\b',
            r'\bdependency\s+injection\b',
            r'\bresource\s+management\b',
            
            # Console and logging
            r'console\.(log|warn|error|info)',
            r'\blogging\s+implementation\b',
        ]

        # Context clues that suggest documentation rather than TODO
        self.documentation_indicators = [
            r'@param',
            r'@return',
            r'@throws',
            r'@author',
            r'@date',
            r'@version',
            r'@description',
            r'@example',
            r'@see',
            r'@since',
            r'@deprecated',
            r'\*\s*\*\s*\*',  # JSDoc comment blocks
            r'^\s*/\*\*',     # Start of JSDoc
            r'^\s*# ',        # Markdown headers
            r'^\s*## ',       # Markdown subheaders
            r'^\s*### ',      # Markdown sub-subheaders
        ]

        # Context clues that suggest actual TODO
        self.todo_indicators = [
            r'\btodo\b',
            r'\bfixme\b',
            r'\bhack\b',
            r'\bneed\s+to\b',
            r'\bshould\s+be\b',
            r'\bmust\s+be\b',
            r'\bhas\s+to\b',
            r'\brequired\s+to\b',
            r'\bmissing\b',
            r'\bincomplete\b',
            r'\bpartial\b',
            r'\bunfinished\b',
            r'\bwork\s+in\s+progress\b',
            r'\bwip\b',
        ]

        self.results = defaultdict(list)
        self.file_stats = defaultdict(int)
        self.pattern_stats = defaultdict(int)

        # Heuristic code stub patterns keyed by language
        self.code_stub_patterns = {
            'python': {
                'function_stub': re.compile(r'^\s*def\s+\w+\(.*\):'),
                'pass_stmt': re.compile(r'^\s*pass\s*$'),
                'ellipsis_stmt': re.compile(r'^\s*\.\.\.\s*$'),
                'raise_not_impl': re.compile(r'^\s*raise\s+NotImplementedError'),
                'return_not_impl': re.compile(r'^\s*return\s+(None|NotImplemented)\s*$'),
            },
            'javascript': {
                'function_stub': re.compile(r'^\s*(async\s+)?function\s+\w+\(.*\)\s*{'),
                'arrow_stub': re.compile(r'^\s*const\s+\w+\s*=\s*\(.*\)\s*=>\s*{'),
                'throw_not_impl': re.compile(r"^\s*throw\s+new\s+Error\((\"|')(TODO|Not\s+Implemented)"),
                'return_todo': re.compile(r"^\s*return\s+(null|undefined);\s*//\s*TODO"),
            },
            'typescript': {
                'function_stub': re.compile(r'^\s*(async\s+)?function\s+\w+\(.*\)\s*{'),
                'arrow_stub': re.compile(r'^\s*const\s+\w+\s*=\s*\(.*\)\s*=>\s*{'),
                'throw_not_impl': re.compile(r"^\s*throw\s+new\s+Error\((\"|')(TODO|Not\s+Implemented)"),
                'return_todo': re.compile(r"^\s*return\s+(null|undefined);\s*//\s*TODO"),
            },
        }

    def should_ignore_file(self, file_path: Path) -> bool:
        """Check if a file should be ignored based on patterns."""
        path_str = str(file_path)

        # Check against ignored patterns
        for pattern in self.ignored_file_patterns:
            if re.search(pattern, path_str, re.IGNORECASE):
                return True

        return False

    def detect_language(self, file_path: Path) -> Optional[str]:
        """Detect the programming language of a file based on its extension."""
        suffix = file_path.suffix.lower()

        for language, config in self.language_patterns.items():
            if suffix in config['extensions']:
                return language

        return None

    def is_excluded_pattern(self, comment: str) -> bool:
        """Check if a comment matches exclusion patterns (legitimate technical terms)."""
        for pattern in self.exclusion_patterns:
            if re.search(pattern, comment, re.IGNORECASE):
                return True
        return False

    def is_documentation_comment(self, comment: str) -> bool:
        """Check if a comment appears to be documentation rather than a TODO."""
        for indicator in self.documentation_indicators:
            if re.search(indicator, comment, re.IGNORECASE):
                return True
        return False

    def has_todo_indicators(self, comment: str) -> bool:
        """Check if a comment contains indicators that suggest it's an actual TODO."""
        for indicator in self.todo_indicators:
            if re.search(indicator, comment, re.IGNORECASE):
                return True
        return False

    def calculate_context_score(self, comment: str, line_num: int, file_path: Path) -> float:
        """Calculate a context score to help determine if this is a real TODO."""
        score = 0.0
        
        # Check for documentation indicators (reduce score)
        if self.is_documentation_comment(comment):
            score -= 0.5
        
        # Check for TODO indicators (increase score)
        if self.has_todo_indicators(comment):
            score += 0.3
        
        # Check if it's in a generated file (reduce score)
        if self.is_generated_file(file_path):
            score -= 0.4
        
        # Check if comment is very short (likely not a TODO)
        if len(comment.strip()) < 20 and not self.has_todo_indicators(comment):
            score -= 0.2

        # Check if comment starts with common documentation words
        doc_starters = ['note:', 'current', 'this', 'the', 'implementation', 'method', 'function']
        if any(comment.lower().startswith(starter) for starter in doc_starters):
            score -= 0.2

        score = round(score, 3)

        return max(-1.0, min(1.0, score))  # Clamp between -1 and 1

    def is_generated_file(self, file_path: Path) -> bool:
        """Check if a file appears to be generated code."""
        path_str = str(file_path)
        generated_indicators = [
            r'\.next\b',
            r'generated',
            r'build/',
            r'dist/',
            r'target/',
            r'node_modules',
            r'\.min\.',
            r'\.bundle\.',
            r'\.chunk\.',
        ]
        
        for indicator in generated_indicators:
            if re.search(indicator, path_str, re.IGNORECASE):
                return True
        return False

    def extract_comments_from_file(self, file_path: Path) -> List[Tuple[int, str]]:
        """Extract all comments from a file based on its language."""
        language = self.detect_language(file_path)
        if not language:
            return []

        config = self.language_patterns[language]
        comments = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            in_multiline = False
            multiline_content = []

            for line_num, line in enumerate(lines, 1):
                original_line = line
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Handle multi-line comments / docstrings
                start_pattern = config['multi_line_start']
                end_pattern = config['multi_line_end']
                if start_pattern and end_pattern:
                    if not in_multiline:
                        start_match = re.search(start_pattern, original_line)
                        if start_match:
                            in_multiline = True
                            multiline_content = []
                            after_start = original_line[start_match.end():]
                            end_match_inline = re.search(end_pattern, after_start)

                            if end_match_inline:
                                body = after_start[:end_match_inline.start()].strip()
                                if body:
                                    multiline_content.append(body)
                                combined = ' '.join(multiline_content).strip()
                                if combined:
                                    comments.append((line_num, combined))
                                in_multiline = False
                                multiline_content = []
                            else:
                                stripped_body = after_start.strip()
                                if stripped_body:
                                    multiline_content.append(stripped_body)
                            continue
                    else:
                        end_match = re.search(end_pattern, original_line)
                        if end_match:
                            before_end = original_line[:end_match.start()].strip()
                            if before_end:
                                multiline_content.append(before_end)
                            combined = ' '.join(multiline_content).strip()
                            if combined:
                                comments.append((line_num, combined))
                            in_multiline = False
                            multiline_content = []
                            continue
                        else:
                            inner = original_line.strip()
                            if inner:
                                multiline_content.append(inner)
                            continue

                # Extract single-line comments (only if not in multi-line mode)
                if not in_multiline and config['single_line'] and re.search(config['single_line'], line):
                    # Remove comment prefix
                    if language in ['rust', 'javascript', 'typescript', 'go', 'java', 'csharp', 'cpp', 'c', 'php']:
                        comment = re.sub(r'^\s*//\s*', '', line)
                    elif language in ['python', 'ruby', 'shell', 'yaml']:
                        comment = re.sub(r'^\s*#\s*', '', line)
                    elif language == 'markdown':
                        comment = re.sub(r'^\s*<!--\s*', '', line)
                        comment = re.sub(r'\s*-->$', '', comment)

                    if comment:
                        comments.append((line_num, comment))

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

        return comments

    def detect_code_stubs(self, file_path: Path, language: str) -> List[Dict[str, Any]]:
        """Detect code stub patterns beyond explicit comments."""
        if not self.enable_code_stub_scan:
            return []

        patterns = self.code_stub_patterns.get(language)
        if not patterns:
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []

        if language == 'python':
            stubs = self._detect_python_code_stubs(lines, patterns)
        elif language in ('javascript', 'typescript'):
            stubs = self._detect_js_code_stubs(lines, patterns)
        else:
            stubs = []

        for stub in stubs:
            self.pattern_stats[stub['reason']] += 1

        return stubs

    def _detect_python_code_stubs(self, lines: List[str], patterns: Dict[str, re.Pattern]) -> List[Dict[str, Any]]:
        stubs: List[Dict[str, Any]] = []

        for idx, raw_line in enumerate(lines, 1):
            stripped = raw_line.strip()
            if not stripped:
                continue

            if patterns['function_stub'].match(raw_line):
                stub_entry = self._scan_python_function_body(lines, idx, patterns)
                if stub_entry:
                    stubs.append(stub_entry)
                continue

            if patterns['raise_not_impl'].search(raw_line):
                stubs.append({
                    'line': idx,
                    'reason': 'python_raise_not_implemented',
                    'snippet': stripped,
                    'confidence': 0.95,
                    'context_score': 0.2,
                })
                continue

            if patterns['ellipsis_stmt'].match(raw_line):
                stubs.append({
                    'line': idx,
                    'reason': 'python_ellipsis_stub',
                    'snippet': stripped,
                    'confidence': 0.85,
                    'context_score': 0.15,
                })
                continue

        return stubs

    def _scan_python_function_body(self, lines: List[str], start_index: int, patterns: Dict[str, re.Pattern]) -> Optional[Dict[str, Any]]:
        """Inspect the first meaningful statement in a Python function for stub markers."""
        func_line = lines[start_index - 1]
        func_indent = len(func_line) - len(func_line.lstrip())

        for idx in range(start_index + 1, len(lines) + 1):
            raw_line = lines[idx - 1]
            stripped = raw_line.strip()

            if not stripped or stripped.startswith('#'):
                continue

            current_indent = len(raw_line) - len(raw_line.lstrip())
            if current_indent <= func_indent:
                break

            if patterns['pass_stmt'].match(raw_line):
                return {
                    'line': idx,
                    'reason': 'python_pass_stub',
                    'snippet': stripped,
                    'confidence': 0.82,
                    'context_score': 0.1,
                }

            if patterns['ellipsis_stmt'].match(raw_line):
                return {
                    'line': idx,
                    'reason': 'python_ellipsis_stub',
                    'snippet': stripped,
                    'confidence': 0.82,
                    'context_score': 0.1,
                }

            if patterns['raise_not_impl'].search(raw_line):
                return {
                    'line': idx,
                    'reason': 'python_raise_not_implemented',
                    'snippet': stripped,
                    'confidence': 0.95,
                    'context_score': 0.25,
                }

            if patterns['return_not_impl'].match(raw_line):
                return {
                    'line': idx,
                    'reason': 'python_return_placeholder',
                    'snippet': stripped,
                    'confidence': 0.8,
                    'context_score': 0.1,
                }

            # First substantive line is real implementation
            break

        return None

    def _detect_js_code_stubs(self, lines: List[str], patterns: Dict[str, re.Pattern]) -> List[Dict[str, Any]]:
        stubs: List[Dict[str, Any]] = []
        total_lines = len(lines)

        for idx, raw_line in enumerate(lines, 1):
            stripped = raw_line.strip()
            if not stripped:
                continue

            if patterns['throw_not_impl'].search(stripped):
                stubs.append({
                    'line': idx,
                    'reason': 'js_throw_not_implemented',
                    'snippet': stripped,
                    'confidence': 0.9,
                    'context_score': 0.2,
                })
                continue

            if patterns['return_todo'].search(stripped):
                stubs.append({
                    'line': idx,
                    'reason': 'js_return_todo',
                    'snippet': stripped,
                    'confidence': 0.82,
                    'context_score': 0.1,
                })
                continue

            if patterns['function_stub'].match(raw_line) or patterns['arrow_stub'].match(raw_line):
                stub_entry = self._scan_js_function_body(lines, idx, patterns)
                if stub_entry:
                    stubs.append(stub_entry)

        return stubs

    def _scan_js_function_body(self, lines: List[str], start_index: int, patterns: Dict[str, re.Pattern]) -> Optional[Dict[str, Any]]:
        """Inspect the first executable statement in a JS/TS function body."""
        opening_line = lines[start_index - 1]
        initial_brace_count = opening_line.count('{') - opening_line.count('}')
        brace_depth = max(initial_brace_count, 0)

        for idx in range(start_index + 1, len(lines) + 1):
            raw_line = lines[idx - 1]
            stripped = raw_line.strip()

            brace_depth += raw_line.count('{')
            brace_depth -= raw_line.count('}')

            if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
                continue

            if brace_depth < 0:
                break

            if patterns['throw_not_impl'].search(stripped):
                return {
                    'line': idx,
                    'reason': 'js_throw_not_implemented',
                    'snippet': stripped,
                    'confidence': 0.9,
                    'context_score': 0.2,
                }

            if patterns['return_todo'].search(stripped):
                return {
                    'line': idx,
                    'reason': 'js_return_todo',
                    'snippet': stripped,
                    'confidence': 0.82,
                    'context_score': 0.1,
                }

            if brace_depth <= 0:
                break

            # Found non-stub statement
            break

        return None

    def analyze_comment(self, comment: str, line_num: int, file_path: Path) -> Dict[str, Any]:
        """Analyze a single comment for hidden TODO patterns with enhanced context awareness."""
        normalized = comment.strip()
        if not normalized:
            return {}

        comment = normalized
        matches = defaultdict(list)
        confidence_scores = []
        
        # Skip if this is an excluded pattern (legitimate technical term)
        if self.is_excluded_pattern(comment):
            return {}

        # Calculate context score
        context_score = self.calculate_context_score(comment, line_num, file_path)

        # Check explicit TODO patterns (highest confidence)
        for pattern in self.explicit_todo_patterns['explicit_todos']:
            if re.search(pattern, comment, re.IGNORECASE):
                matches['explicit_todos'].append(pattern)
                # Adjust confidence based on context
                base_confidence = 1.0
                adjusted_confidence = min(1.0, max(0.1, base_confidence + context_score * 0.3))
                confidence_scores.append(('explicit', adjusted_confidence))
                self.pattern_stats[pattern] += 1

        # Check high-confidence patterns
        for category, patterns in self.high_confidence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, comment, re.IGNORECASE):
                    matches[category].append(pattern)
                    # Adjust confidence based on context
                    base_confidence = 0.9
                    adjusted_confidence = min(1.0, max(0.1, base_confidence + context_score * 0.2))
                    confidence_scores.append((category, adjusted_confidence))
                    self.pattern_stats[pattern] += 1

        # Check medium-confidence patterns
        for category, patterns in self.medium_confidence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, comment, re.IGNORECASE):
                    matches[category].append(pattern)
                    # Adjust confidence based on context
                    base_confidence = 0.6
                    adjusted_confidence = min(1.0, max(0.1, base_confidence + context_score * 0.1))
                    confidence_scores.append((category, adjusted_confidence))
                    self.pattern_stats[pattern] += 1

        # Calculate overall confidence score
        if not confidence_scores:
            return {}

        overall_confidence = max(score for _, score in confidence_scores)

        return {
            'matches': matches,
            'confidence_score': overall_confidence,
            'confidence_breakdown': confidence_scores,
            'context_score': context_score
        }

    def analyze_file(self, file_path: Path) -> Dict:
        """Analyze a single file for hidden TODO patterns."""
        language = self.detect_language(file_path)
        if not language:
            return {}

        # Skip ignored files
        if self.should_ignore_file(file_path):
            return {}

        comments = self.extract_comments_from_file(file_path)
        try:
            relative_path = str(file_path.relative_to(self.root_dir))
        except ValueError:
            relative_path = str(file_path)

        file_analysis = {
            'file_path': relative_path,
            'language': language,
            'total_comments': len(comments),
            'hidden_todos': defaultdict(list),
            'all_comments': []
        }

        for line_num, comment in comments:
            analysis = self.analyze_comment(comment, line_num, file_path)

            if analysis and analysis['matches']:
                file_analysis['hidden_todos'][line_num] = {
                    'comment': comment,
                    'matches': analysis['matches'],
                    'confidence_score': analysis['confidence_score'],
                    'confidence_breakdown': analysis['confidence_breakdown'],
                    'context_score': analysis['context_score']
                }

            # Store all comments for analysis
            file_analysis['all_comments'].append({
                'line': line_num,
                'comment': comment
            })

        # Detect stub implementations in code bodies
        for stub in self.detect_code_stubs(file_path, language):
            line_num = stub['line']
            reason = stub['reason']
            snippet = stub['snippet']
            confidence = stub['confidence']
            context = stub.get('context_score', 0.0)

            # Attempt to merge with nearby comment within 3 lines above
            nearby_comment_line = None
            for existing_line in sorted(file_analysis['hidden_todos'].keys()):
                if existing_line == line_num:
                    nearby_comment_line = existing_line
                    break
                if existing_line < line_num and line_num - existing_line <= 3:
                    nearby_comment_line = existing_line

            target_line = nearby_comment_line if nearby_comment_line is not None else line_num

            if target_line in file_analysis['hidden_todos']:
                entry = file_analysis['hidden_todos'][target_line]
                entry['matches'].setdefault('code_stubs', []).append(reason)
                entry['confidence_score'] = max(entry['confidence_score'], confidence)
                entry['confidence_breakdown'].append(('code_stub', confidence))
                entry['context_score'] = max(entry['context_score'], context)
                if target_line != line_num:
                    related = entry.setdefault('related_stub_lines', [])
                    if line_num not in related:
                        related.append(line_num)
            else:
                file_analysis['hidden_todos'][target_line] = {
                    'comment': snippet,
                    'matches': defaultdict(list, {'code_stubs': [reason]}),
                    'confidence_score': confidence,
                    'confidence_breakdown': [('code_stub', confidence)],
                    'context_score': context,
                }
                file_analysis['all_comments'].append({
                    'line': line_num,
                    'comment': snippet
                })

        return file_analysis

    def analyze_directory(self, languages: Optional[List[str]] = None, min_confidence: float = 0.7) -> Dict:
        """Analyze all files in the directory for hidden TODO patterns with improved accuracy."""
        print(f"Analyzing files with improved patterns in: {self.root_dir}")
        print(f"Minimum confidence threshold: {min_confidence}")

        # Get all files with supported extensions
        all_files = []
        for language, config in self.language_patterns.items():
            if languages and language not in languages:
                continue
            for ext in config['extensions']:
                all_files.extend(self.root_dir.rglob(f'*{ext}'))

        # Filter out ignored files
        non_ignored_files = [
            f for f in all_files if not self.should_ignore_file(f)]

        print(f"Found {len(all_files)} total files")
        print(f"Found {len(non_ignored_files)} non-ignored files")

        # Count by language
        language_counts = defaultdict(int)
        for file_path in non_ignored_files:
            language = self.detect_language(file_path)
            if language:
                language_counts[language] += 1

        print("Files by language:")
        for lang, count in sorted(language_counts.items()):
            print(f"  {lang}: {count} files")

        # Reset pattern statistics for this run
        self.pattern_stats = defaultdict(int)

        all_results = {
            'summary': {
                'total_files': len(all_files),
                'non_ignored_files': len(non_ignored_files),
                'ignored_files': len(all_files) - len(non_ignored_files),
                'language_counts': dict(language_counts),
                'files_with_hidden_todos': 0,
                'total_hidden_todos': 0,
                'high_confidence_todos': 0,
                'medium_confidence_todos': 0,
                'low_confidence_todos': 0,
                'code_stub_todos': 0,
                'pattern_counts': {},
                'min_confidence_threshold': min_confidence,
            },
            'files': {},
            'patterns': defaultdict(list)
        }

        for file_path in non_ignored_files:
            print(f"Analyzing: {file_path.relative_to(self.root_dir)}")
            file_analysis = self.analyze_file(file_path)

            if file_analysis and file_analysis['hidden_todos']:
                # Filter by confidence threshold
                filtered_todos = {}
                for line_num, data in file_analysis['hidden_todos'].items():
                    if data['confidence_score'] >= min_confidence:
                        filtered_todos[line_num] = data
                        
                        # Count by confidence level
                        if data['confidence_score'] >= 0.9:
                            all_results['summary']['high_confidence_todos'] += 1
                        elif data['confidence_score'] >= 0.6:
                            all_results['summary']['medium_confidence_todos'] += 1
                        else:
                            all_results['summary']['low_confidence_todos'] += 1

                if filtered_todos:
                    file_analysis['hidden_todos'] = filtered_todos
                    all_results['files'][file_analysis['file_path']] = file_analysis
                    all_results['summary']['files_with_hidden_todos'] += 1
                    all_results['summary']['total_hidden_todos'] += len(filtered_todos)

                    # Group by patterns
                    for line_num, data in filtered_todos.items():
                        for category, patterns in data['matches'].items():
                            all_results['patterns'][category].append({
                                'file': file_analysis['file_path'],
                                'language': file_analysis['language'],
                                'line': line_num,
                                'comment': data['comment'],
                                'patterns': patterns,
                                'confidence_score': data['confidence_score'],
                                'context_score': data['context_score']
                            })
                            if category == 'code_stubs':
                                all_results['summary']['code_stub_todos'] += 1

        all_results['summary']['pattern_counts'] = dict(self.pattern_stats)

        return all_results

    def generate_report(self, results: Dict) -> str:
        """Generate a comprehensive report with enhanced accuracy information."""
        report = []
        report.append("# Improved Hidden TODO Analysis Report (v2.0)")
        report.append("=" * 60)
        report.append("")

        # Summary
        summary = results['summary']
        report.append("## Summary")
        report.append(f"- Total files: {summary['total_files']}")
        report.append(f"- Non-ignored files: {summary['non_ignored_files']}")
        report.append(f"- Ignored files: {summary['ignored_files']}")
        report.append(f"- Files with hidden TODOs: {summary['files_with_hidden_todos']}")
        report.append(f"- Total hidden TODOs found: {summary['total_hidden_todos']}")
        report.append(f"- Code stub detections: {summary.get('code_stub_todos', 0)}")
        report.append(f"- High confidence TODOs (≥0.9): {summary['high_confidence_todos']}")
        report.append(f"- Medium confidence TODOs (≥0.6): {summary['medium_confidence_todos']}")
        report.append(f"- Low confidence TODOs (<0.6): {summary['low_confidence_todos']}")
        report.append(f"- Minimum confidence threshold: {summary['min_confidence_threshold']}")
        report.append("")

        # Language breakdown
        report.append("## Files by Language")
        for lang, count in sorted(summary['language_counts'].items()):
            report.append(f"- **{lang}**: {count} files")
        report.append("")

        # Pattern statistics
        if summary['pattern_counts']:
            report.append("## Pattern Statistics")
            for pattern, count in sorted(summary['pattern_counts'].items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    report.append(f"- `{pattern}`: {count} occurrences")
            report.append("")

        # Files with most high-confidence hidden TODOs
        if results['files']:
            report.append("## Files with High-Confidence Hidden TODOs")
            file_todo_counts = []
            for file_path, data in results['files'].items():
                high_conf_count = sum(1 for todo in data['hidden_todos'].values() 
                                    if todo['confidence_score'] >= 0.9)
                if high_conf_count > 0:
                    file_todo_counts.append((file_path, data['language'], high_conf_count))

            file_todo_counts.sort(key=lambda x: x[2], reverse=True)
            for file_path, language, count in file_todo_counts:
                report.append(f"- `{file_path}` ({language}): {count} high-confidence TODOs")
            report.append("")

        # Pattern categories with confidence scores
        if results['patterns']:
            report.append("## Pattern Categories by Confidence")
            for category, items in results['patterns'].items():
                if items:
                    high_conf_items = [item for item in items if item['confidence_score'] >= 0.9]
                    medium_conf_items = [item for item in items if 0.6 <= item['confidence_score'] < 0.9]
                    low_conf_items = [item for item in items if item['confidence_score'] < 0.6]
                    
                    if high_conf_items or medium_conf_items:
                        report.append(f"### {category.replace('_', ' ').title()} ({len(items)} items)")
                        
                        if high_conf_items:
                            report.append(f"#### High Confidence ({len(high_conf_items)} items)")
                            for item in high_conf_items[:3]:
                                context_info = f" (context: {item['context_score']:.1f})" if 'context_score' in item else ""
                                report.append(f"- `{item['file']}:{item['line']}` ({item['language']}, conf: {item['confidence_score']:.1f}{context_info}): {item['comment'][:80]}...")
                            if len(high_conf_items) > 3:
                                report.append(f"- ... and {len(high_conf_items) - 3} more high-confidence items")
                        
                        if medium_conf_items:
                            report.append(f"#### Medium Confidence ({len(medium_conf_items)} items)")
                            for item in medium_conf_items[:2]:
                                context_info = f" (context: {item['context_score']:.1f})" if 'context_score' in item else ""
                                report.append(f"- `{item['file']}:{item['line']}` ({item['language']}, conf: {item['confidence_score']:.1f}{context_info}): {item['comment'][:80]}...")
                            if len(medium_conf_items) > 2:
                                report.append(f"- ... and {len(medium_conf_items) - 2} more medium-confidence items")
                        
                        if low_conf_items:
                            report.append(f"#### Low Confidence ({len(low_conf_items)} items) - *Consider reviewing for false positives*")
                        
                        report.append("")

        return "\n".join(report)


HiddenTodoAnalyzer = HiddenTodoAnalyzer


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Analyze files for hidden TODO patterns with improved accuracy')
    parser.add_argument('--root', default='.',
                        help='Root directory to analyze (default: current directory)')
    parser.add_argument('--languages', nargs='+',
                        help='Specific languages to analyze (e.g., rust python javascript)')
    parser.add_argument(
        '--output-json', help='Output JSON file for detailed results')
    parser.add_argument('--output-md', help='Output Markdown report file')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                        help='Minimum confidence threshold (0.0-1.0, default: 0.7)')
    parser.add_argument('--verbose', '-v',
                        action='store_true', help='Verbose output')
    parser.add_argument('--disable-code-stub-scan',
                        action='store_true', help='Disable code stub detection heuristics')

    args = parser.parse_args()

    analyzer = HiddenTodoAnalyzer(
        args.root,
        enable_code_stub_scan=not args.disable_code_stub_scan,
    )
    results = analyzer.analyze_directory(args.languages, args.min_confidence)

    # Print summary
    summary = results['summary']
    print(f"\n{'='*60}")
    print("IMPROVED HIDDEN TODO ANALYSIS COMPLETE (v2.0)")
    print(f"{'='*60}")
    print(f"Total files: {summary['total_files']}")
    print(f"Non-ignored files: {summary['non_ignored_files']}")
    print(f"Ignored files: {summary['ignored_files']}")
    print(f"Files with hidden TODOs: {summary['files_with_hidden_todos']}")
    print(f"Total hidden TODOs: {summary['total_hidden_todos']}")
    print(f"High confidence (≥0.9): {summary['high_confidence_todos']}")
    print(f"Medium confidence (≥0.6): {summary['medium_confidence_todos']}")
    print(f"Low confidence (<0.6): {summary['low_confidence_todos']}")
    print(f"Confidence threshold: {summary['min_confidence_threshold']}")

    print(f"\nFiles by language:")
    for lang, count in sorted(summary['language_counts'].items()):
        print(f"  {lang}: {count} files")

    if summary['pattern_counts']:
        print(f"\nTop patterns found:")
        for pattern, count in sorted(summary['pattern_counts'].items(), key=lambda x: x[1], reverse=True)[:15]:
            if count > 0:
                print(f"  {pattern}: {count}")

    # Save reports
    if args.output_json:
        with open(args.output_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {args.output_json}")

    if args.output_md:
        report = analyzer.generate_report(results)
        with open(args.output_md, 'w') as f:
            f.write(report)
        print(f"Report saved to: {args.output_md}")
    else:
        # Print report to console
        print("\n" + analyzer.generate_report(results))


if __name__ == '__main__':
    main()
