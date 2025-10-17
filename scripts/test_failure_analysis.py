#!/usr/bin/env python3
"""
Test Failure Analysis Script

Analyzes test failures and provides actionable recommendations for fixing them.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple


def run_tests_and_capture_output() -> Tuple[str, int]:
    """Run tests and capture output."""
    print("🧪 Running tests to capture failure details...")
    
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', 'tests/unit', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        return result.stdout + result.stderr, result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return "", 1


def parse_test_failures(test_output: str) -> List[Dict[str, Any]]:
    """Parse test output to extract failure information."""
    failures = []
    
    # Split output into lines and look for FAILED lines
    lines = test_output.split('\n')
    current_failure = None
    
    for line in lines:
        if line.strip().startswith('FAILED'):
            # Extract test path from FAILED line
            # Format: FAILED tests/unit/test_config.py::TestTTSConfig::test_default_config_values
            parts = line.strip().split()
            if len(parts) >= 2:
                test_path = parts[1]
                test_file = test_path.split('::')[0]
                test_name = test_path.split('::')[-1] if '::' in test_path else test_path
                
                current_failure = {
                    'test_file': test_file,
                    'test_name': test_name,
                    'error_message': '',
                    'category': 'unknown',
                    'severity': 'low'
                }
                failures.append(current_failure)
        
        elif current_failure and line.strip():
            # Collect error message lines
            if not current_failure['error_message']:
                current_failure['error_message'] = line.strip()
            else:
                current_failure['error_message'] += ' ' + line.strip()
    
    # Categorize failures
    for failure in failures:
        failure['category'] = categorize_failure(failure['error_message'])
        failure['severity'] = get_severity(failure['category'], failure['error_message'])
    
    return failures


def categorize_failure(error_msg: str) -> str:
    """Categorize test failure based on error message."""
    error_lower = error_msg.lower()
    
    if 'assertionerror' in error_lower:
        if '== ' in error_msg or '!=' in error_msg:
            return 'assertion_mismatch'
        elif 'assert' in error_lower:
            return 'assertion_failure'
    elif 'attributeerror' in error_lower:
        return 'missing_attribute'
    elif 'validationerror' in error_lower or 'pydantic' in error_lower:
        return 'validation_error'
    elif 'nameerror' in error_lower:
        return 'missing_import'
    elif 'httpexception' in error_lower:
        return 'http_error'
    elif 'valueerror' in error_lower:
        return 'value_error'
    elif 'typeerror' in error_lower:
        return 'type_error'
    elif 'timeout' in error_lower:
        return 'timeout'
    else:
        return 'unknown'


def get_severity(category: str, error_msg: str) -> str:
    """Determine failure severity."""
    if category in ['missing_attribute', 'missing_import']:
        return 'high'  # Usually easy to fix
    elif category in ['assertion_mismatch', 'validation_error']:
        return 'medium'  # May require config changes
    elif category in ['http_error', 'timeout']:
        return 'high'  # Infrastructure issues
    else:
        return 'low'


def analyze_failure_patterns(failures: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze patterns in test failures."""
    analysis = {
        'total_failures': len(failures),
        'by_category': {},
        'by_file': {},
        'by_severity': {},
        'common_issues': [],
        'recommendations': []
    }
    
    # Group by category
    for failure in failures:
        category = failure['category']
        if category not in analysis['by_category']:
            analysis['by_category'][category] = []
        analysis['by_category'][category].append(failure)
    
    # Group by file
    for failure in failures:
        test_file = failure['test_file']
        if test_file not in analysis['by_file']:
            analysis['by_file'][test_file] = []
        analysis['by_file'][test_file].append(failure)
    
    # Group by severity
    for failure in failures:
        severity = failure['severity']
        if severity not in analysis['by_severity']:
            analysis['by_severity'][severity] = []
        analysis['by_severity'][severity].append(failure)
    
    # Identify common issues
    if 'assertion_mismatch' in analysis['by_category']:
        analysis['common_issues'].append({
            'issue': 'Configuration mismatches',
            'count': len(analysis['by_category']['assertion_mismatch']),
            'description': 'Tests expect different default values than current config'
        })
    
    if 'missing_attribute' in analysis['by_category']:
        analysis['common_issues'].append({
            'issue': 'Missing attributes/methods',
            'count': len(analysis['by_category']['missing_attribute']),
            'description': 'Tests trying to access non-existent attributes or methods'
        })
    
    if 'validation_error' in analysis['by_category']:
        analysis['common_issues'].append({
            'issue': 'Pydantic validation errors',
            'count': len(analysis['by_category']['validation_error']),
            'description': 'Input validation failing due to changed requirements'
        })
    
    # Generate recommendations
    if analysis['by_category'].get('assertion_mismatch'):
        analysis['recommendations'].append({
            'priority': 'high',
            'action': 'Update test expectations to match current configuration',
            'files': list(set(f['test_file'] for f in analysis['by_category']['assertion_mismatch']))
        })
    
    if analysis['by_category'].get('missing_attribute'):
        analysis['recommendations'].append({
            'priority': 'high',
            'action': 'Fix mocking issues - check attribute names and imports',
            'files': list(set(f['test_file'] for f in analysis['by_category']['missing_attribute']))
        })
    
    if analysis['by_category'].get('validation_error'):
        analysis['recommendations'].append({
            'priority': 'medium',
            'action': 'Update test data to match current validation rules',
            'files': list(set(f['test_file'] for f in analysis['by_category']['validation_error']))
        })
    
    return analysis


def print_analysis_report(analysis: Dict[str, Any]):
    """Print formatted analysis report."""
    print("=" * 80)
    print("🔍 TEST FAILURE ANALYSIS REPORT")
    print("=" * 80)
    print(f"📊 Total Failures: {analysis['total_failures']}")
    print()
    
    # Summary by category
    print("📋 FAILURES BY CATEGORY")
    print("-" * 40)
    for category, failures in analysis['by_category'].items():
        print(f"  {category.replace('_', ' ').title()}: {len(failures)}")
        for failure in failures[:3]:  # Show first 3 examples
            print(f"    • {failure['test_name']}")
        if len(failures) > 3:
            print(f"    ... and {len(failures) - 3} more")
    print()
    
    # Summary by severity
    print("⚠️  FAILURES BY SEVERITY")
    print("-" * 40)
    for severity, failures in analysis['by_severity'].items():
        emoji = "🔴" if severity == 'high' else "🟡" if severity == 'medium' else "🟢"
        print(f"  {severity.title()}: {len(failures)} {emoji}")
    print()
    
    # Common issues
    if analysis['common_issues']:
        print("🎯 COMMON ISSUES")
        print("-" * 40)
        for issue in analysis['common_issues']:
            print(f"  • {issue['issue']}: {issue['count']} failures")
            print(f"    {issue['description']}")
        print()
    
    # Recommendations
    if analysis['recommendations']:
        print("💡 RECOMMENDATIONS")
        print("-" * 40)
        for i, rec in enumerate(analysis['recommendations'], 1):
            priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
            print(f"  {i}. {priority_emoji} {rec['action']}")
            if rec['files']:
                print(f"     Files: {', '.join(rec['files'][:3])}")
                if len(rec['files']) > 3:
                    print(f"     ... and {len(rec['files']) - 3} more")
        print()
    
    # Top failing files
    print("📁 TOP FAILING FILES")
    print("-" * 40)
    sorted_files = sorted(analysis['by_file'].items(), key=lambda x: len(x[1]), reverse=True)
    for test_file, failures in sorted_files[:5]:
        print(f"  {test_file}: {len(failures)} failures")
    print()
    
    print("=" * 80)


def generate_fix_commands(analysis: Dict[str, Any]) -> List[str]:
    """Generate specific fix commands based on analysis."""
    commands = []
    
    # Configuration fixes
    if 'assertion_mismatch' in analysis['by_category']:
        commands.append("# Fix configuration mismatches:")
        commands.append("grep -r 'assert.*==' tests/unit/ | head -10")
        commands.append("# Update test expectations to match current config values")
    
    # Mocking fixes
    if 'missing_attribute' in analysis['by_category']:
        commands.append("# Fix mocking issues:")
        commands.append("grep -r 'patch.*api.model.providers' tests/unit/")
        commands.append("# Check that mocked attributes exist in the actual modules")
    
    # Validation fixes
    if 'validation_error' in analysis['by_category']:
        commands.append("# Fix validation errors:")
        commands.append("grep -r 'TTSRequest' tests/unit/ | grep -v 'import'")
        commands.append("# Update test data to match current Pydantic models")
    
    return commands


def main():
    """Main function to analyze test failures."""
    print("🔍 Analyzing test failures...")
    
    # Run tests and capture output
    test_output, exit_code = run_tests_and_capture_output()
    
    if exit_code == 0:
        print("✅ All tests are passing! No analysis needed.")
        return 0
    
    # Parse failures
    failures = parse_test_failures(test_output)
    
    if not failures:
        print("⚠️  No failures detected in output. Check test execution.")
        return 1
    
    # Analyze patterns
    analysis = analyze_failure_patterns(failures)
    
    # Print report
    print_analysis_report(analysis)
    
    # Generate fix commands
    fix_commands = generate_fix_commands(analysis)
    if fix_commands:
        print("🛠️  SUGGESTED FIX COMMANDS")
        print("-" * 40)
        for cmd in fix_commands:
            print(cmd)
        print()
    
    # Save analysis to file
    analysis_path = Path('.agent/test_failure_analysis.json')
    analysis_path.parent.mkdir(exist_ok=True)
    
    with open(analysis_path, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"📄 Analysis saved to {analysis_path}")
    
    return 1  # Return non-zero to indicate failures exist


if __name__ == "__main__":
    exit(main())
