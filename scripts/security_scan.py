#!/usr/bin/env python3
"""
Security scanning script for Kokoro TTS API.

This script performs basic security checks including:
- Secret scanning
- Dependency vulnerability scanning
- Basic SAST (Static Application Security Testing)
"""
import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Set

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Common secret patterns
SECRET_PATTERNS = [
    r'api[_-]?key["\s]*[:=]["\s]*[a-zA-Z0-9]{20,}',
    r'secret[_-]?key["\s]*[:=]["\s]*[a-zA-Z0-9]{20,}',
    r'password["\s]*[:=]["\s]*["\'][^"\']{8,}["\']',
    r'token["\s]*[:=]["\s]*["\'][a-zA-Z0-9]{20,}["\']',
    r'private[_-]?key["\s]*[:=]["\s]*["\'][a-zA-Z0-9]{20,}["\']',
    r'-----BEGIN PRIVATE KEY-----',
    r'-----BEGIN RSA PRIVATE KEY-----',
    r'-----BEGIN EC PRIVATE KEY-----',
    r'sk-[a-zA-Z0-9]{20,}',  # OpenAI API keys
    r'pk_[a-zA-Z0-9]{20,}',  # Stripe keys
    r'AKIA[0-9A-Z]{16}',     # AWS access keys
    r'[0-9a-f]{32}',         # MD5 hashes (potential secrets)
    r'[0-9a-f]{40}',         # SHA1 hashes (potential secrets)
    r'[0-9a-f]{64}',         # SHA256 hashes (potential secrets)
]

# Files to exclude from secret scanning
EXCLUDE_PATTERNS = [
    r'\.git/',
    r'__pycache__/',
    r'\.pytest_cache/',
    r'node_modules/',
    r'\.venv/',
    r'venv/',
    r'\.env\.example',
    r'requirements\.txt',
    r'package-lock\.json',
    r'yarn\.lock',
    r'\.lock',
    r'\.log',
    r'\.pyc',
    r'\.pyo',
    r'\.pyd',
    r'\.so',
    r'\.dylib',
    r'\.dll',
    r'\.exe',
    r'security_scan\.py',  # Exclude our own security scanning script
    r'run_mutation_tests\.py',  # Exclude our mutation testing script
]

# Dangerous function patterns for SAST
DANGEROUS_PATTERNS = [
    (r'eval\s*\(', 'Use of eval() function'),
    (r'exec\s*\(', 'Use of exec() function'),
    (r'__import__\s*\(', 'Use of __import__() function'),
    (r'compile\s*\(', 'Use of compile() function'),
    (r'os\.system\s*\(', 'Use of os.system() - consider subprocess'),
    (r'subprocess\.call\s*\(', 'Use of subprocess.call() without shell=True'),
    (r'shell\s*=\s*True', 'Use of shell=True in subprocess'),
    (r'pickle\.loads?\s*\(', 'Use of pickle - security risk'),
    (r'marshal\.loads?\s*\(', 'Use of marshal - security risk'),
    (r'input\s*\(', 'Use of input() in production code'),
    (r'raw_input\s*\(', 'Use of raw_input() in production code'),
]

def should_exclude_file(file_path: str) -> bool:
    """Check if file should be excluded from scanning."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False

def scan_for_secrets(file_path: str) -> List[Dict[str, Any]]:
    """Scan a file for potential secrets."""
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            for pattern in SECRET_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    findings.append({
                        'file': file_path,
                        'line': i,
                        'column': match.start() + 1,
                        'pattern': pattern,
                        'match': match.group(),
                        'severity': 'high',
                        'type': 'secret'
                    })
    except Exception as e:
        print(f"Error scanning {file_path}: {e}")
    
    return findings

def scan_for_dangerous_patterns(file_path: str) -> List[Dict[str, Any]]:
    """Scan a file for dangerous code patterns."""
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            for pattern, description in DANGEROUS_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    findings.append({
                        'file': file_path,
                        'line': i,
                        'column': match.start() + 1,
                        'pattern': pattern,
                        'description': description,
                        'severity': 'medium',
                        'type': 'sast'
                    })
    except Exception as e:
        print(f"Error scanning {file_path}: {e}")
    
    return findings

def scan_dependencies() -> List[Dict[str, Any]]:
    """Scan dependencies for known vulnerabilities."""
    findings = []
    
    # Check if requirements.txt exists
    requirements_file = project_root / "requirements.txt"
    if not requirements_file.exists():
        return findings
    
    try:
        # Try to use safety if available
        result = subprocess.run([
            sys.executable, "-m", "safety", "check", "--json"
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0:
            # No vulnerabilities found
            return findings
        elif result.returncode == 64:  # Vulnerabilities found
            try:
                data = json.loads(result.stdout)
                for vuln in data:
                    findings.append({
                        'package': vuln.get('package_name', 'unknown'),
                        'version': vuln.get('analyzed_version', 'unknown'),
                        'vulnerability': vuln.get('advisory', 'Unknown vulnerability'),
                        'severity': vuln.get('severity', 'medium'),
                        'type': 'dependency'
                    })
            except json.JSONDecodeError:
                # Fallback: parse text output
                for line in result.stdout.split('\n'):
                    if 'vulnerability' in line.lower():
                        findings.append({
                            'package': 'unknown',
                            'version': 'unknown',
                            'vulnerability': line.strip(),
                            'severity': 'medium',
                            'type': 'dependency'
                        })
    except FileNotFoundError:
        # safety not available, skip dependency scanning
        pass
    except Exception as e:
        print(f"Error scanning dependencies: {e}")
    
    return findings

def scan_project() -> Dict[str, Any]:
    """Scan the entire project for security issues."""
    results = {
        'secrets': [],
        'sast': [],
        'dependencies': [],
        'summary': {
            'total_findings': 0,
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0
        }
    }
    
    print("🔍 Scanning for secrets...")
    # Scan Python files for secrets
    for py_file in project_root.rglob("*.py"):
        if should_exclude_file(str(py_file)):
            continue
        
        relative_path = py_file.relative_to(project_root)
        findings = scan_for_secrets(str(py_file))
        results['secrets'].extend(findings)
    
    print("🔍 Scanning for dangerous patterns...")
    # Scan Python files for dangerous patterns (exclude scripts directory)
    for py_file in project_root.rglob("*.py"):
        if should_exclude_file(str(py_file)) or "scripts/" in str(py_file):
            continue
        
        relative_path = py_file.relative_to(project_root)
        findings = scan_for_dangerous_patterns(str(py_file))
        results['sast'].extend(findings)
    
    print("🔍 Scanning dependencies...")
    # Scan dependencies
    results['dependencies'] = scan_dependencies()
    
    # Calculate summary
    all_findings = results['secrets'] + results['sast'] + results['dependencies']
    results['summary']['total_findings'] = len(all_findings)
    
    for finding in all_findings:
        severity = finding.get('severity', 'low')
        if severity == 'high':
            results['summary']['high_severity'] += 1
        elif severity == 'medium':
            results['summary']['medium_severity'] += 1
        else:
            results['summary']['low_severity'] += 1
    
    return results

def main():
    """Main security scanning function."""
    print("🔒 Running security scan...")
    
    results = scan_project()
    
    # Save results
    results_file = project_root / "security-scan-results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Report results
    print(f"\n📊 Security Scan Results:")
    print(f"  Total findings: {results['summary']['total_findings']}")
    print(f"  High severity: {results['summary']['high_severity']}")
    print(f"  Medium severity: {results['summary']['medium_severity']}")
    print(f"  Low severity: {results['summary']['low_severity']}")
    
    # Report specific findings
    if results['secrets']:
        print(f"\n🚨 Secret findings ({len(results['secrets'])}):")
        for finding in results['secrets'][:5]:  # Show first 5
            print(f"  - {finding['file']}:{finding['line']} - {finding['match'][:20]}...")
    
    if results['sast']:
        print(f"\n⚠️  SAST findings ({len(results['sast'])}):")
        for finding in results['sast'][:5]:  # Show first 5
            print(f"  - {finding['file']}:{finding['line']} - {finding['description']}")
    
    if results['dependencies']:
        print(f"\n📦 Dependency vulnerabilities ({len(results['dependencies'])}):")
        for finding in results['dependencies'][:5]:  # Show first 5
            print(f"  - {finding['package']} {finding['version']} - {finding['vulnerability']}")
    
    # Exit with appropriate code
    if results['summary']['high_severity'] > 0:
        print("\n❌ Security scan failed (high severity findings)")
        sys.exit(1)
    elif results['summary']['medium_severity'] > 0:
        print("\n⚠️  Security scan passed with warnings (medium severity findings)")
        sys.exit(0)
    else:
        print("\n✅ Security scan passed")
        sys.exit(0)

if __name__ == "__main__":
    main()
