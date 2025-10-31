#!/usr/bin/env python3
"""
Documentation Quality Linter

Automatically detects and reports documentation quality issues including:
- Superiority claims and marketing language
- Unfounded achievement claims
- Temporal documentation in wrong locations
- Missing evidence for status claims
- Code examples that don't work
"""

import re
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class QualityIssue:
    file_path: str
    line_number: int
    severity: Severity
    rule_id: str
    message: str
    suggested_fix: str = ""


class DocumentationQualityLinter:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.issues: List[QualityIssue] = []

        # Define prohibited patterns
        self.superiority_patterns = [
            r'\b(revolutionary|breakthrough|innovative|groundbreaking)\b',
            r'\b(cutting-edge|state-of-the-art|next-generation)\b',
            r'\b(advanced|premium|superior|best|leading)\b',
            r'\b(industry-leading|award-winning|game-changing)\b'
        ]

        self.achievement_patterns = [
            r'\b(production-ready|enterprise-grade|battle-tested)\b',
            r'\b(complete|finished|done|achieved|delivered)\b',
            r'\b(implemented|operational|ready|deployed)\b',
            r'\b(launched|released|100%|fully)\b',
            r'\b(comprehensive|entire|total|all|every)\b',
            r'\b(perfect|ideal|optimal|maximum|minimum)\b',
            r'\b(unlimited|infinite|endless)\b'
        ]

        self.temporal_patterns = [
            r'SESSION_.*_SUMMARY\.md',
            r'IMPLEMENTATION_STATUS\.md',
            r'TODO_.*_COMPLETE\.md',
            r'.*_SUMMARY\.md',
            r'.*_REPORT\.md',
            r'.*_AUDIT\.md',
            r'.*_CHECKLIST\.md',
            r'PHASE.*\.md',
            r'NEXT_ACTIONS\.md'
        ]

        # Define allowed locations for temporal docs
        self.temporal_allowed_dirs = [
            'docs/archive/',
            'docs/archive/session-reports/',
            'docs/archive/implementation-tracking/',
            'docs/archive/project-docs/',
            'docs/archive/summaries/',
            'docs/archive/security-audits/',
            'docs/archive/deployment-readiness/',
            'docs/archive/multimodal-rag/',
            'docs/archive/aspirational/',
            'docs/archive/misleading-claims/'
        ]

    def lint_file(self, file_path: Path) -> List[QualityIssue]:
        """Lint a single file for documentation quality issues."""
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            issues.append(QualityIssue(
                file_path=str(file_path),
                line_number=0,
                severity=Severity.ERROR,
                rule_id="FILE_READ_ERROR",
                message=f"Could not read file: {e}",
                suggested_fix="Check file permissions and encoding"
            ))
            return issues

        # Check for superiority claims
        for i, line in enumerate(lines, 1):
            for pattern in self.superiority_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(QualityIssue(
                        file_path=str(file_path),
                        line_number=i,
                        severity=Severity.ERROR,
                        rule_id="SUPERIORITY_CLAIM",
                        message=f"Superiority claim detected: '{line.strip()}'",
                        suggested_fix="Remove marketing language and focus on technical capabilities"
                    ))

        # Check for unfounded achievement claims
        for i, line in enumerate(lines, 1):
            for pattern in self.achievement_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(QualityIssue(
                        file_path=str(file_path),
                        line_number=i,
                        severity=Severity.WARNING,
                        rule_id="UNFOUNDED_ACHIEVEMENT",
                        message=f"Unfounded achievement claim detected: '{line.strip()}'",
                        suggested_fix="Verify claim with evidence or use more accurate language"
                    ))

        # Check for temporal documentation in wrong locations
        if file_path.name.endswith('.md'):
            for pattern in self.temporal_patterns:
                if re.search(pattern, file_path.name, re.IGNORECASE):
                    # Check if file is in allowed directory
                    allowed = any(str(file_path).startswith(str(self.project_root / allowed_dir))
                                  for allowed_dir in self.temporal_allowed_dirs)

                    if not allowed:
                        issues.append(QualityIssue(
                            file_path=str(file_path),
                            line_number=0,
                            severity=Severity.ERROR,
                            rule_id="TEMPORAL_DOC_WRONG_LOCATION",
                            message=f"Temporal documentation '{file_path.name}' in wrong location",
                            suggested_fix=f"Move to appropriate archive directory (docs/archive/)"
                        ))

        # Check for emoji usage (except approved ones)
        approved_emojis = ['⚠️', '✅', '🚫']
        for i, line in enumerate(lines, 1):
            # Find all emojis in the line
            emoji_pattern = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001F900-\U0001F9FF\U0001F018-\U0001F0F5\U0001F200-\U0001F2FF]'
            emojis = re.findall(emoji_pattern, line)

            for emoji in emojis:
                if emoji not in approved_emojis:
                    issues.append(QualityIssue(
                        file_path=str(file_path),
                        line_number=i,
                        severity=Severity.WARNING,
                        rule_id="EMOJI_USAGE",
                        message=f"Emoji usage detected: '{emoji}' in '{line.strip()}'",
                        suggested_fix="Remove emoji or use approved emojis only (⚠️, ✅, 🚫)"
                    ))

        return issues

    def lint_project(self) -> List[QualityIssue]:
        """Lint entire project for documentation quality issues."""
        all_issues = []

        # Find all markdown files
        md_files = list(self.project_root.rglob("*.md"))
        txt_files = list(self.project_root.rglob("*.txt"))
        rst_files = list(self.project_root.rglob("*.rst"))
        adoc_files = list(self.project_root.rglob("*.adoc"))

        all_doc_files = md_files + txt_files + rst_files + adoc_files

        # Exclude certain directories
        excluded_dirs = {
            'node_modules', '.git', 'target', 'dist', 'build', '__pycache__',
            '.venv', '.stryker-tmp', 'site-packages', '.dist-info', '.whl',
            'venv', 'env', 'virtualenv', 'conda', 'anaconda', '.build',
            'checkouts', 'Tests', 'examples', 'models', 'vocabs', 'merges'
        }

        for file_path in all_doc_files:
            # Skip files in excluded directories
            if any(part in excluded_dirs for part in file_path.parts):
                continue

            # Skip files in target directory (Rust build artifacts)
            if 'target' in str(file_path):
                continue

            # Skip archive files (they're historical and don't need quality checks)
            if 'docs/archive/' in str(file_path):
                continue

            # Skip third-party dependencies and build artifacts
            if any(dep in str(file_path) for dep in [
                '.venv', 'site-packages', '.dist-info', '.whl', '.build',
                'checkouts', 'Tests', 'examples', 'models', 'vocabs', 'merges',
                'LICENSE.txt', 'bert-vocab.txt', 'bench-all-gg.txt', 'CMakeLists.txt'
            ]):
                continue

            issues = self.lint_file(file_path)
            all_issues.extend(issues)

        return all_issues

    def check_code_examples(self, file_path: Path) -> List[QualityIssue]:
        """Check if code examples in documentation actually work."""
        issues = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return issues

        # Find code blocks
        code_blocks = re.findall(r'```(\w+)?\n(.*?)\n```', content, re.DOTALL)

        for i, (language, code) in enumerate(code_blocks):
            if language in ['javascript', 'js', 'typescript', 'ts', 'python', 'py']:
                # Basic syntax check for common issues
                if language in ['javascript', 'js', 'typescript', 'ts']:
                    # Check for common JS/TS issues
                    if 'fetch(' in code and 'await' not in code:
                        issues.append(QualityIssue(
                            file_path=str(file_path),
                            line_number=0,
                            severity=Severity.WARNING,
                            rule_id="ASYNC_FETCH",
                            message="fetch() call without await in code example",
                            suggested_fix="Add await keyword or handle promise properly"
                        ))

                elif language in ['python', 'py']:
                    # Check for common Python issues
                    if 'import' in code and 'from' in code:
                        # Check for relative imports that might not work
                        if './' in code or '../' in code:
                            issues.append(QualityIssue(
                                file_path=str(file_path),
                                line_number=0,
                                severity=Severity.WARNING,
                                rule_id="RELATIVE_IMPORT",
                                message="Relative import in code example",
                                suggested_fix="Use absolute import or provide context"
                            ))

        return issues

    def generate_report(self, issues: List[QualityIssue], output_format: str = "text") -> str:
        """Generate a report of all issues found."""
        if output_format == "json":
            return json.dumps([
                {
                    "file": issue.file_path,
                    "line": issue.line_number,
                    "severity": issue.severity.value,
                    "rule": issue.rule_id,
                    "message": issue.message,
                    "suggested_fix": issue.suggested_fix
                }
                for issue in issues
            ], indent=2)

        elif output_format == "text":
            if not issues:
                return "✅ No documentation quality issues found!"

            report = []
            report.append("📋 Documentation Quality Report")
            report.append("=" * 50)

            # Group by severity
            errors = [i for i in issues if i.severity == Severity.ERROR]
            warnings = [i for i in issues if i.severity == Severity.WARNING]
            infos = [i for i in issues if i.severity == Severity.INFO]

            if errors:
                report.append(f"\n❌ ERRORS ({len(errors)}):")
                for issue in errors:
                    report.append(
                        f"  {issue.file_path}:{issue.line_number} - {issue.message}")
                    if issue.suggested_fix:
                        report.append(f"    💡 {issue.suggested_fix}")

            if warnings:
                report.append(f"\n⚠️  WARNINGS ({len(warnings)}):")
                for issue in warnings:
                    report.append(
                        f"  {issue.file_path}:{issue.line_number} - {issue.message}")
                    if issue.suggested_fix:
                        report.append(f"    💡 {issue.suggested_fix}")

            if infos:
                report.append(f"\nℹ️  INFO ({len(infos)}):")
                for issue in infos:
                    report.append(
                        f"  {issue.file_path}:{issue.line_number} - {issue.message}")

            return "\n".join(report)

        else:
            return f"Unknown output format: {output_format}"


def main():
    """Main entry point for the documentation quality linter."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Documentation Quality Linter")
    parser.add_argument("--path", default=".", help="Path to project root")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--exit-code", action="store_true",
                        help="Exit with non-zero code if issues found")

    args = parser.parse_args()

    linter = DocumentationQualityLinter(args.path)
    issues = linter.lint_project(show_progress=True)

    report = linter.generate_report(issues, args.format)
    print(report)

    if args.exit_code and issues:
        # Count errors and warnings
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        warning_count = len(
            [i for i in issues if i.severity == Severity.WARNING])

        # Exit with error code if there are errors or too many warnings
        if error_count > 0 or warning_count > 10:
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
