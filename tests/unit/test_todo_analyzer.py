#!/usr/bin/env python3
"""
Test suite for HiddenTodoAnalyzer

Tests the todo analyzer functionality including comment extraction,
pattern matching, context scoring, and file filtering.

@author: @darianrosebrook
@date: 2025-10-17
@version: 1.0.0
"""

import sys
import unittest
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.linting.todo_analyzer import HiddenTodoAnalyzer


class HiddenTodoAnalyzerTests(unittest.TestCase):
    """Test cases for HiddenTodoAnalyzer functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tmp_root = Path(__file__).resolve().parent
        self.analyzer = HiddenTodoAnalyzer(root_dir=str(self.tmp_root))

    def test_documentation_comments_are_excluded(self):
        """Test that documentation comments are properly excluded."""
        comment = "@param user_data The serialized payload."
        self.assertTrue(self.analyzer.is_documentation_comment(comment))
        result = self.analyzer.analyze_comment(comment, 12, Path("src/service.py"))
        self.assertEqual(result, {})

    def test_todo_indicators_raise_context_score(self):
        """Test that TODO indicators increase context score."""
        comment = "Need to replace this placeholder with the real implementation."
        score = self.analyzer.calculate_context_score(
            comment, 20, Path("src/core/module.py")
        )
        self.assertGreaterEqual(score, 0.29)

    def test_generated_files_reduce_context_score(self):
        """Test that generated files reduce context score."""
        comment = "Need to replace this placeholder with the real implementation."
        score = self.analyzer.calculate_context_score(
            comment, 5, Path("dist/generated.js")
        )
        self.assertLessEqual(score, -0.09)

    def test_explicit_todos_return_context_and_confidence(self):
        """Test that explicit TODOs are properly detected with confidence scores."""
        comment = "TODO: finalize the persistence layer wiring."
        result = self.analyzer.analyze_comment(
            comment, 32, Path("src/persistence/adapter.py")
        )

        self.assertIn("explicit_todos", result["matches"])
        self.assertTrue(result["matches"]["explicit_todos"])
        self.assertGreater(result["confidence_score"], 0.0)
        self.assertLessEqual(result["confidence_score"], 1.0)
        self.assertIn("context_score", result)

    def test_placeholder_code_detection(self):
        """Test detection of placeholder code patterns."""
        comment = "This is a placeholder implementation that should be replaced."
        result = self.analyzer.analyze_comment(
            comment, 45, Path("src/utils/helper.py")
        )

        self.assertIn("placeholder_code", result["matches"])
        self.assertGreater(result["confidence_score"], 0.6)

    def test_temporary_solution_detection(self):
        """Test detection of temporary solution patterns."""
        comment = "This is a temporary fix that needs proper implementation."
        result = self.analyzer.analyze_comment(
            comment, 78, Path("src/api/endpoint.py")
        )

        self.assertIn("temporary_solutions", result["matches"])
        self.assertGreater(result["confidence_score"], 0.6)

    def test_incomplete_implementation_detection(self):
        """Test detection of incomplete implementation patterns."""
        comment = "Not yet implemented - needs proper error handling."
        result = self.analyzer.analyze_comment(
            comment, 123, Path("src/validation/validator.py")
        )

        self.assertIn("incomplete_implementation", result["matches"])
        self.assertGreater(result["confidence_score"], 0.6)

    def test_hardcoded_values_detection(self):
        """Test detection of hardcoded value patterns."""
        comment = "This magic number should be made configurable."
        result = self.analyzer.analyze_comment(
            comment, 156, Path("src/config/settings.py")
        )

        self.assertIn("hardcoded_values", result["matches"])
        self.assertGreater(result["confidence_score"], 0.6)

    def test_future_improvements_detection(self):
        """Test detection of future improvement patterns."""
        comment = "Should be implemented with proper caching in production."
        result = self.analyzer.analyze_comment(
            comment, 89, Path("src/cache/manager.py")
        )

        self.assertIn("future_improvements", result["matches"])
        self.assertGreater(result["confidence_score"], 0.6)

    def test_excluded_patterns_are_filtered(self):
        """Test that legitimate technical terms are excluded."""
        excluded_comments = [
            "This is a performance optimization strategy.",
            "The simulation environment provides realistic data.",
            "Basic authentication is implemented here.",
            "Mock object for testing purposes.",
            "Current implementation uses efficient algorithms.",
        ]

        for comment in excluded_comments:
            result = self.analyzer.analyze_comment(comment, 10, Path("src/test.py"))
            self.assertEqual(result, {}, f"Comment should be excluded: {comment}")

    def test_file_ignore_patterns(self):
        """Test that files are properly ignored based on patterns."""
        ignored_paths = [
            Path("tests/unit/test_file.py"),
            Path("node_modules/package/index.js"),
            Path("build/dist/output.js"),
            Path("htmlcov/coverage.html"),
            Path("logs/server.log"),
            Path("artifacts/benchmark.json"),
            Path(".git/config"),
            Path("package.json"),
            Path("__pycache__/module.pyc"),
        ]

        for path in ignored_paths:
            self.assertTrue(
                self.analyzer.should_ignore_file(path),
                f"Path should be ignored: {path}"
            )

    def test_file_not_ignored_for_source_code(self):
        """Test that legitimate source code files are not ignored."""
        source_paths = [
            Path("src/main.py"),
            Path("api/routes/users.py"),
            Path("scripts/deploy.sh"),
            Path("dashboard/src/components/Button.tsx"),
            Path("raycast/src/utils/helper.ts"),
        ]

        for path in source_paths:
            self.assertFalse(
                self.analyzer.should_ignore_file(path),
                f"Path should NOT be ignored: {path}"
            )

    def test_language_detection(self):
        """Test that programming languages are correctly detected."""
        test_cases = [
            (Path("src/main.py"), "python"),
            (Path("api/routes.js"), "javascript"),
            (Path("dashboard/components.tsx"), "typescript"),
            (Path("scripts/deploy.sh"), "shell"),
            (Path("README.md"), "markdown"),
            (Path("config.yml"), "yaml"),
            (Path("data.json"), "json"),
            (Path("src/main.rs"), "rust"),
            (Path("src/main.go"), "go"),
            (Path("src/main.java"), "java"),
            (Path("src/main.cs"), "csharp"),
            (Path("src/main.cpp"), "cpp"),
        ]

        for path, expected_lang in test_cases:
            detected_lang = self.analyzer.detect_language(path)
            self.assertEqual(
                detected_lang, expected_lang,
                f"Language detection failed for {path}: expected {expected_lang}, got {detected_lang}"
            )

    def test_comment_extraction_python(self):
        """Test comment extraction from Python files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''#!/usr/bin/env python3
"""
This is a docstring comment.
It spans multiple lines.
"""

import os

# This is a single line comment
def function():
    """Function docstring."""
    # TODO: implement this function
    # This is another comment
    pass

# FIXME: this needs proper error handling
''')
            temp_file = Path(f.name)

        try:
            comments = self.analyzer.extract_comments_from_file(temp_file)
            
            # Should extract the docstring content and single-line comments
            self.assertGreater(len(comments), 0)
            
            # Check for specific comments
            comment_texts = [comment for _, comment in comments]
            self.assertIn("This is a docstring comment.", " ".join(comment_texts))
            self.assertIn("This is a single line comment", " ".join(comment_texts))
            self.assertIn("TODO: implement this function", " ".join(comment_texts))
            self.assertIn("FIXME: this needs proper error handling", " ".join(comment_texts))
            
        finally:
            temp_file.unlink()

    def test_comment_extraction_javascript(self):
        """Test comment extraction from JavaScript files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write('''// This is a single line comment
function example() {
    /* This is a multi-line comment
       that spans multiple lines */
    
    // TODO: implement proper validation
    console.log("Hello World");
}

// FIXME: add error handling
''')
            temp_file = Path(f.name)

        try:
            comments = self.analyzer.extract_comments_from_file(temp_file)
            
            # Should extract both single-line and multi-line comments
            self.assertGreater(len(comments), 0)
            
            comment_texts = [comment for _, comment in comments]
            self.assertIn("This is a single line comment", " ".join(comment_texts))
            self.assertIn("This is a multi-line comment", " ".join(comment_texts))
            self.assertIn("TODO: implement proper validation", " ".join(comment_texts))
            self.assertIn("FIXME: add error handling", " ".join(comment_texts))
            
        finally:
            temp_file.unlink()

    def test_context_score_calculation(self):
        """Test context score calculation with various inputs."""
        test_cases = [
            # (comment, line_num, file_path, expected_min_score, expected_max_score)
            ("TODO: implement this", 10, Path("src/main.py"), 0.3, 1.0),
            ("@param data The input data", 5, Path("src/api.py"), -0.5, -0.3),
            ("Need to fix this bug", 20, Path("dist/generated.js"), -0.1, 0.3),
            ("This is a short comment", 15, Path("src/util.py"), -0.2, 0.1),
        ]

        for comment, line_num, file_path, min_score, max_score in test_cases:
            score = self.analyzer.calculate_context_score(comment, line_num, file_path)
            self.assertGreaterEqual(score, min_score, f"Score too low for: {comment}")
            self.assertLessEqual(score, max_score, f"Score too high for: {comment}")

    def test_confidence_score_adjustment(self):
        """Test that confidence scores are properly adjusted by context."""
        comment = "TODO: implement this function"
        
        # Test with positive context (TODO indicators)
        result_positive = self.analyzer.analyze_comment(
            comment, 10, Path("src/main.py")
        )
        
        # Test with negative context (documentation indicators)
        comment_with_docs = "TODO: implement this function @param data input"
        result_negative = self.analyzer.analyze_comment(
            comment_with_docs, 10, Path("src/main.py")
        )
        
        # Positive context should have higher confidence
        self.assertGreater(
            result_positive["confidence_score"], 
            result_negative["confidence_score"]
        )

    def test_empty_comment_handling(self):
        """Test that empty comments are handled properly."""
        empty_comments = ["", "   ", "#", "//", "<!-- -->"]
        
        for comment in empty_comments:
            result = self.analyzer.analyze_comment(comment, 10, Path("src/test.py"))
            self.assertEqual(result, {})

    def test_analyze_file_with_real_content(self):
        """Test analyzing a real file with various comment types."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''#!/usr/bin/env python3
"""
Module docstring
"""

import os

# TODO: implement this function properly
def placeholder_function():
    """Function that needs implementation."""
    # This is a temporary solution
    pass

# FIXME: add proper error handling
class Example:
    """Example class with issues."""
    
    def method(self):
        # Need to replace this with real implementation
        return None
''')
            temp_file = Path(f.name)

        try:
            file_analysis = self.analyzer.analyze_file(temp_file)
            
            self.assertIn('file_path', file_analysis)
            self.assertIn('language', file_analysis)
            self.assertIn('total_comments', file_analysis)
            self.assertIn('hidden_todos', file_analysis)
            self.assertIn('all_comments', file_analysis)
            
            self.assertEqual(file_analysis['language'], 'python')
            self.assertGreater(file_analysis['total_comments'], 0)
            
            # Should find some hidden TODOs
            if file_analysis['hidden_todos']:
                self.assertGreater(len(file_analysis['hidden_todos']), 0)
                
        finally:
            temp_file.unlink()

    def test_multiline_comment_handling(self):
        """Test that multi-line comments are properly handled."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''"""
This is a multi-line docstring.
It contains TODO: implement this feature
And also mentions placeholder implementation
"""

# This is a regular comment
def test():
    pass
''')
            temp_file = Path(f.name)

        try:
            comments = self.analyzer.extract_comments_from_file(temp_file)
            
            # Should extract the docstring content as a single comment
            comment_texts = [comment for _, comment in comments]
            full_text = " ".join(comment_texts)
            
            self.assertIn("This is a multi-line docstring", full_text)
            self.assertIn("TODO: implement this feature", full_text)
            self.assertIn("placeholder implementation", full_text)
            self.assertIn("This is a regular comment", full_text)
            
        finally:
            temp_file.unlink()

    def test_python_stub_detection_pass(self):
        """Python function with pass should be flagged as stub."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "stub.py"
            file_path.write_text(textwrap.dedent('''
                def placeholder():
                    pass
            ''').strip() + '\n')

            analyzer = HiddenTodoAnalyzer(root_dir=str(tmp_path))
            analysis = analyzer.analyze_file(file_path)

            self.assertTrue(analysis['hidden_todos'])
            stub_entries = [entry for entry in analysis['hidden_todos'].values()
                            if 'code_stubs' in entry['matches']]
            self.assertTrue(stub_entries, "Expected code stub detection for pass statement")
            self.assertGreaterEqual(stub_entries[0]['confidence_score'], 0.8)

    def test_python_todo_comment_merges_with_stub(self):
        """Ensure TODO comment inherits stub context when adjacent to pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "module.py"
            file_path.write_text(textwrap.dedent('''
                # TODO: replace placeholder implementation
                def placeholder():
                    pass
            ''').strip() + '\n')

            analyzer = HiddenTodoAnalyzer(root_dir=str(tmp_path))
            analysis = analyzer.analyze_file(file_path)

            self.assertIn(1, analysis['hidden_todos'])
            entry = analysis['hidden_todos'][1]
            self.assertIn('code_stubs', entry['matches'])
            self.assertGreaterEqual(entry['confidence_score'], 0.85)

    def test_python_raise_not_implemented_detection(self):
        """Raise NotImplementedError should emit high-confidence stub."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "handler.py"
            file_path.write_text(textwrap.dedent('''
                def handler():
                    raise NotImplementedError("pending work")
            ''').strip() + '\n')

            analyzer = HiddenTodoAnalyzer(root_dir=str(tmp_path))
            analysis = analyzer.analyze_file(file_path)

            stub_entries = [entry for entry in analysis['hidden_todos'].values()
                            if 'code_stubs' in entry['matches']]
            self.assertTrue(stub_entries)
            self.assertGreaterEqual(stub_entries[0]['confidence_score'], 0.9)

    def test_js_stub_detection_throw(self):
        """JavaScript throw TODO should be detected as stub."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "api.js"
            file_path.write_text(textwrap.dedent('''
                function fetchData() {
                    throw new Error('TODO fetch implementation');
                }
            ''').strip() + '\n')

            analyzer = HiddenTodoAnalyzer(root_dir=str(tmp_path))
            analysis = analyzer.analyze_file(file_path)

            stub_entries = [entry for entry in analysis['hidden_todos'].values()
                            if 'code_stubs' in entry['matches']]
            self.assertTrue(stub_entries)
            self.assertGreaterEqual(stub_entries[0]['confidence_score'], 0.85)

    def test_real_function_not_flagged(self):
        """Legitimate implementation should not trigger stub detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "math_ops.py"
            file_path.write_text(textwrap.dedent('''
                def add(a, b):
                    return a + b
            ''').strip() + '\n')

            analyzer = HiddenTodoAnalyzer(root_dir=str(tmp_path))
            analysis = analyzer.analyze_file(file_path)

            stub_entries = [entry for entry in analysis['hidden_todos'].values()
                            if 'code_stubs' in entry['matches']]
            self.assertFalse(stub_entries, "Real implementation incorrectly flagged as stub")

    def test_directory_summary_counts_stub(self):
        """Directory analysis should include code stub count in summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "stub.py"
            file_path.write_text(textwrap.dedent('''
                def pending():
                    pass
            ''').strip() + '\n')

            analyzer = HiddenTodoAnalyzer(root_dir=str(tmp_path))
            with patch('builtins.print'):
                results = analyzer.analyze_directory(languages=['python'], min_confidence=0.6)

            self.assertGreater(results['summary']['code_stub_todos'], 0)


class HiddenTodoAnalyzerIntegrationTests(unittest.TestCase):
    """Integration tests for HiddenTodoAnalyzer with real project structure."""

    def setUp(self) -> None:
        """Set up test fixtures for integration tests."""
        self.project_root = ROOT
        self.analyzer = HiddenTodoAnalyzer(root_dir=str(self.project_root))

    def test_analyze_project_directory(self):
        """Test analyzing the actual project directory."""
        results = self.analyzer.analyze_directory(
            languages=['python'], 
            min_confidence=0.6
        )
        
        self.assertIn('summary', results)
        self.assertIn('files', results)
        self.assertIn('patterns', results)
        
        summary = results['summary']
        self.assertIn('total_files', summary)
        self.assertIn('non_ignored_files', summary)
        self.assertIn('files_with_hidden_todos', summary)
        self.assertIn('total_hidden_todos', summary)
        
        # Should have found some files
        self.assertGreater(summary['non_ignored_files'], 0)
        
        # Should have found some hidden TODOs in our test
        self.assertGreater(summary['total_hidden_todos'], 0)

    def test_generate_report(self):
        """Test report generation functionality."""
        results = self.analyzer.analyze_directory(
            languages=['python'], 
            min_confidence=0.6
        )
        
        report = self.analyzer.generate_report(results)
        
        self.assertIsInstance(report, str)
        self.assertIn("Hidden TODO Analysis Report", report)
        self.assertIn("Summary", report)
        self.assertIn("Files by Language", report)
        
        # Should contain some actual data
        self.assertIn("Total files:", report)
        self.assertIn("Non-ignored files:", report)


if __name__ == "__main__":
    unittest.main()
