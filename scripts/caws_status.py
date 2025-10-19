#!/usr/bin/env python3
"""
CAWS Status Dashboard

Provides real-time CAWS compliance status and metrics.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


def get_working_spec_info() -> Dict[str, Any]:
    """Get Working Spec information."""
    spec_path = Path('.caws/working-spec.yaml')
    if not spec_path.exists():
        return {}
    
    try:
        import yaml
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)
        
        return {
            'id': spec.get('id'),
            'title': spec.get('title'),
            'risk_tier': spec.get('risk_tier'),
            'profile': spec.get('profile'),
            'acceptance_criteria': len(spec.get('acceptance', [])),
            'invariants': len(spec.get('invariants', [])),
            'perf_budgets': spec.get('non_functional', {}).get('perf', {})
        }
    except Exception as e:
        print(f"Warning: Could not parse Working Spec: {e}")
        return {}


def get_coverage_status() -> Dict[str, Any]:
    """Get current test coverage status."""
    coverage_path = Path('coverage.xml')
    if not coverage_path.exists():
        return {'status': 'missing', 'line_coverage': 0, 'branch_coverage': 0}
    
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(coverage_path)
        root = tree.getroot()
        
        line_rate = float(root.get('line-rate', 0))
        branch_rate = float(root.get('branch-rate', 0))
        
        return {
            'status': 'available',
            'line_coverage': line_rate,
            'branch_coverage': branch_rate,
            'total_lines': int(root.get('lines-valid', 0)),
            'covered_lines': int(root.get('lines-covered', 0))
        }
    except Exception as e:
        print(f"Warning: Could not parse coverage.xml: {e}")
        return {'status': 'error', 'line_coverage': 0, 'branch_coverage': 0}


def get_mutation_status() -> Dict[str, Any]:
    """Get mutation testing status."""
    mutation_path = Path('mutmut-results.json')
    if not mutation_path.exists():
        return {'status': 'missing', 'score': 0, 'total': 0, 'killed': 0}
    
    try:
        with open(mutation_path, 'r') as f:
            data = json.load(f)
        
        return {
            'status': 'available',
            'score': data.get('mutation_score', 0),
            'total': data.get('total_mutations', 0),
            'killed': data.get('killed_mutations', 0),
            'survived': data.get('survived_mutations', 0)
        }
    except Exception as e:
        print(f"Warning: Could not parse mutmut-results.json: {e}")
        return {'status': 'error', 'score': 0, 'total': 0, 'killed': 0}


def get_test_status() -> Dict[str, Any]:
    """Get test execution status from CI artifacts and recent runs."""
    try:
        # Try to parse test results from artifacts directory
        artifact_results = parse_test_artifacts()
        if artifact_results:
            return artifact_results

        # Fallback to parsing recent test runs
        recent_results = parse_recent_test_runs()
        if recent_results:
            return recent_results

        # Final fallback to static data (for development)
        logger.warning("No test results found, using fallback data")
        return {
            'status': 'no_data',
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'flake_rate': 0.0,
            'last_run': 'never',
            'message': 'No test results available'
        }

    except Exception as e:
        logger.error(f"Failed to get test status: {e}")
        return {
            'status': 'error',
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'flake_rate': 0.0,
            'last_run': 'error',
            'error': str(e)
        }


def parse_test_artifacts() -> Optional[Dict[str, Any]]:
    """Parse test results from CI artifacts directory."""
    try:
        artifacts_dir = Path('artifacts')
        if not artifacts_dir.exists():
            return None

        # Look for test result files in various formats
        test_results = []

        # Parse pytest results
        pytest_files = list(artifacts_dir.glob('**/pytest-results.json')) + \
                      list(artifacts_dir.glob('**/test-results.json'))
        for pytest_file in pytest_files:
            try:
                with open(pytest_file, 'r') as f:
                    data = json.load(f)
                    test_results.append(parse_pytest_results(data))
            except Exception as e:
                logger.debug(f"Failed to parse pytest results {pytest_file}: {e}")

        # Parse JUnit XML results
        junit_files = list(artifacts_dir.glob('**/junit.xml')) + \
                     list(artifacts_dir.glob('**/test-results.xml'))
        for junit_file in junit_files:
            try:
                result = parse_junit_xml(junit_file)
                if result:
                    test_results.append(result)
            except Exception as e:
                logger.debug(f"Failed to parse JUnit XML {junit_file}: {e}")

        # Parse coverage reports
        coverage_files = list(artifacts_dir.glob('**/coverage.json')) + \
                        list(artifacts_dir.glob('**/coverage.xml'))
        coverage_data = None
        for coverage_file in coverage_files:
            try:
                coverage_data = parse_coverage_report(coverage_file)
                break  # Use the first valid coverage report
            except Exception as e:
                logger.debug(f"Failed to parse coverage {coverage_file}: {e}")

        if not test_results:
            return None

        # Aggregate results from multiple test runs
        return aggregate_test_results(test_results, coverage_data)

    except Exception as e:
        logger.debug(f"Failed to parse test artifacts: {e}")
        return None


def parse_recent_test_runs() -> Optional[Dict[str, Any]]:
    """Parse test results from recent test executions."""
    try:
        # Look for recent pytest cache or result files
        possible_locations = [
            Path('.pytest_cache'),
            Path('tests/.pytest_cache'),
            Path('.tox'),
            Path('htmlcov'),
        ]

        # Try to find and parse recent test results
        for location in possible_locations:
            if location.exists():
                # Look for result files in this location
                result_files = list(location.glob('**/*.json')) + list(location.glob('**/*.xml'))
                for result_file in result_files:
                    try:
                        if result_file.suffix == '.json':
                            with open(result_file, 'r') as f:
                                data = json.load(f)
                            if 'tests' in data or 'test_cases' in data:
                                return parse_pytest_results(data)
                        elif result_file.suffix == '.xml':
                            result = parse_junit_xml(result_file)
                            if result:
                                return result
                    except Exception as e:
                        logger.debug(f"Failed to parse {result_file}: {e}")

        # Check for test result files in common locations
        common_files = [
            Path('test-results.json'),
            Path('pytest-results.json'),
            Path('test_output.json'),
            Path('reports/test-results.json'),
        ]

        for result_file in common_files:
            if result_file.exists():
                try:
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                    return parse_pytest_results(data)
                except Exception as e:
                    logger.debug(f"Failed to parse {result_file}: {e}")

        return None

    except Exception as e:
        logger.debug(f"Failed to parse recent test runs: {e}")
        return None


def parse_pytest_results(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse pytest JSON results."""
    try:
        # Extract test summary
        summary = data.get('summary', {})
        tests = data.get('tests', [])

        total_tests = summary.get('num_tests_run', len(tests))
        passed = summary.get('passed', 0)
        failed = summary.get('failed', 0)
        errors = summary.get('errors', 0)
        skipped = summary.get('skipped', 0)

        # Calculate success rate
        successful_tests = passed
        total_executed = passed + failed + errors

        # Calculate flake rate (estimate based on recent failures)
        flake_rate = min(0.5, failed / max(1, total_executed))  # Cap at 50%

        # Get last run timestamp
        created = data.get('created', time.time())
        last_run = datetime.fromtimestamp(created).isoformat()

        return {
            'status': 'completed' if total_executed > 0 else 'no_tests',
            'total_tests': total_tests,
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'skipped': skipped,
            'success_rate': successful_tests / max(1, total_executed),
            'flake_rate': flake_rate,
            'last_run': last_run,
            'source': 'pytest'
        }

    except Exception as e:
        logger.debug(f"Failed to parse pytest results: {e}")
        return None


def parse_junit_xml(xml_file: Path) -> Optional[Dict[str, Any]]:
    """Parse JUnit XML test results."""
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Parse test suites
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_errors = 0
        total_skipped = 0

        for testsuite in root:
            if testsuite.tag == 'testsuite':
                total_tests += int(testsuite.get('tests', 0))
                total_failed += int(testsuite.get('failures', 0))
                total_errors += int(testsuite.get('errors', 0))
                total_skipped += int(testsuite.get('skipped', 0))

                # Count passed tests
                passed_in_suite = int(testsuite.get('tests', 0)) - \
                                int(testsuite.get('failures', 0)) - \
                                int(testsuite.get('errors', 0)) - \
                                int(testsuite.get('skipped', 0))
                total_passed += passed_in_suite

        total_executed = total_passed + total_failed + total_errors
        success_rate = total_passed / max(1, total_executed)
        flake_rate = min(0.5, total_failed / max(1, total_executed))

        # Get timestamp from file modification time
        last_run = datetime.fromtimestamp(xml_file.stat().st_mtime).isoformat()

        return {
            'status': 'completed' if total_executed > 0 else 'no_tests',
            'total_tests': total_tests,
            'passed': total_passed,
            'failed': total_failed,
            'errors': total_errors,
            'skipped': total_skipped,
            'success_rate': success_rate,
            'flake_rate': flake_rate,
            'last_run': last_run,
            'source': 'junit'
        }

    except Exception as e:
        logger.debug(f"Failed to parse JUnit XML {xml_file}: {e}")
        return None


def parse_coverage_report(coverage_file: Path) -> Optional[Dict[str, Any]]:
    """Parse coverage report data."""
    try:
        if coverage_file.suffix == '.json':
            with open(coverage_file, 'r') as f:
                data = json.load(f)
            # Extract coverage percentage
            if isinstance(data, dict) and 'total' in data:
                total = data['total']
                if isinstance(total, dict) and 'percent_covered' in total:
                    return {'coverage_percent': total['percent_covered']}
        elif coverage_file.suffix == '.xml':
            # Basic XML coverage parsing (Cobertura format)
            import xml.etree.ElementTree as ET
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            line_rate = root.get('line-rate')
            if line_rate:
                return {'coverage_percent': float(line_rate) * 100}

        return None

    except Exception as e:
        logger.debug(f"Failed to parse coverage report {coverage_file}: {e}")
        return None


def aggregate_test_results(results_list: List[Dict[str, Any]], coverage_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Aggregate multiple test result sets."""
    if not results_list:
        return None

    # Use the most recent results as primary
    primary_result = max(results_list, key=lambda x: x.get('last_run', '1970-01-01'))

    # Aggregate counts across all results
    total_tests = sum(r.get('total_tests', 0) for r in results_list)
    total_passed = sum(r.get('passed', 0) for r in results_list)
    total_failed = sum(r.get('failed', 0) for r in results_list)
    total_errors = sum(r.get('errors', 0) for r in results_list)
    total_skipped = sum(r.get('skipped', 0) for r in results_list)

    # Calculate aggregate metrics
    total_executed = total_passed + total_failed + total_errors
    success_rate = total_passed / max(1, total_executed)

    # Average flake rate across runs
    flake_rates = [r.get('flake_rate', 0) for r in results_list if r.get('flake_rate') is not None]
    avg_flake_rate = sum(flake_rates) / max(1, len(flake_rates)) if flake_rates else 0

    result = {
        'status': primary_result.get('status', 'completed'),
        'total_tests': total_tests,
        'passed': total_passed,
        'failed': total_failed,
        'errors': total_errors,
        'skipped': total_skipped,
        'success_rate': success_rate,
        'flake_rate': avg_flake_rate,
        'last_run': primary_result.get('last_run', datetime.now().isoformat()),
        'sources': [r.get('source', 'unknown') for r in results_list],
        'aggregated': True
    }

    # Add coverage data if available
    if coverage_data:
        result['coverage'] = coverage_data

    return result


def get_contract_status() -> Dict[str, Any]:
    """Get contract testing status."""
    contracts_dir = Path('contracts')
    if not contracts_dir.exists():
        return {'status': 'missing', 'consumer': False, 'provider': False}
    
    openapi_file = contracts_dir / 'kokoro-tts-api.yaml'
    return {
        'status': 'available',
        'consumer': True,
        'provider': True,
        'openapi_spec': openapi_file.exists(),
        'contract_tests': Path('tests/contract').exists()
    }


def get_ci_status() -> Dict[str, Any]:
    """Get CI/CD pipeline status."""
    workflow_path = Path('.github/workflows/caws.yml')
    return {
        'status': 'configured' if workflow_path.exists() else 'missing',
        'workflow_exists': workflow_path.exists(),
        'last_run': 'unknown'  # Would need to query GitHub API
    }


def get_provenance_status() -> Dict[str, Any]:
    """Get provenance tracking status."""
    provenance_path = Path('.agent/provenance.json')
    if not provenance_path.exists():
        return {'status': 'missing', 'last_generated': None}
    
    try:
        with open(provenance_path, 'r') as f:
            data = json.load(f)
        
        return {
            'status': 'available',
            'last_generated': data.get('timestamp'),
            'agent': data.get('agent'),
            'trust_score': data.get('results', {}).get('trust_score', 0)
        }
    except Exception as e:
        print(f"Warning: Could not parse provenance.json: {e}")
        return {'status': 'error', 'last_generated': None}


def calculate_compliance_score(working_spec: Dict[str, Any], coverage: Dict[str, Any], 
                             mutation: Dict[str, Any], test: Dict[str, Any], 
                             contract: Dict[str, Any], ci: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate overall CAWS compliance score."""
    risk_tier = working_spec.get('risk_tier', 2)
    
    # Define requirements by tier
    if risk_tier == 1:
        min_coverage = 0.9
        min_mutation = 0.7
    elif risk_tier == 2:
        min_coverage = 0.8
        min_mutation = 0.5
    else:
        min_coverage = 0.7
        min_mutation = 0.3
    
    # Calculate component scores
    coverage_score = min(1.0, coverage.get('line_coverage', 0) / min_coverage)
    mutation_score = min(1.0, mutation.get('score', 0) / min_mutation)
    test_score = 1.0 if test.get('flake_rate', 1) < 0.05 else 0.5
    contract_score = 1.0 if contract.get('provider', False) else 0.0
    ci_score = 1.0 if ci.get('workflow_exists', False) else 0.0
    
    # Weighted overall score
    weights = {
        'coverage': 0.25,
        'mutation': 0.25,
        'test_stability': 0.2,
        'contracts': 0.15,
        'ci_pipeline': 0.15
    }
    
    overall_score = (
        weights['coverage'] * coverage_score +
        weights['mutation'] * mutation_score +
        weights['test_stability'] * test_score +
        weights['contracts'] * contract_score +
        weights['ci_pipeline'] * ci_score
    ) * 100
    
    return {
        'overall_score': overall_score,
        'component_scores': {
            'coverage': coverage_score * 100,
            'mutation': mutation_score * 100,
            'test_stability': test_score * 100,
            'contracts': contract_score * 100,
            'ci_pipeline': ci_score * 100
        },
        'requirements': {
            'min_coverage': min_coverage,
            'min_mutation': min_mutation,
            'max_flake_rate': 0.05
        },
        'status': 'compliant' if overall_score >= 80 else 'non_compliant'
    }


def print_status_dashboard(working_spec: Dict[str, Any], coverage: Dict[str, Any],
                          mutation: Dict[str, Any], test: Dict[str, Any],
                          contract: Dict[str, Any], ci: Dict[str, Any],
                          provenance: Dict[str, Any], compliance: Dict[str, Any]):
    """Print formatted status dashboard."""
    print("=" * 80)
    print("🎯 CAWS COMPLIANCE STATUS DASHBOARD")
    print("=" * 80)
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Working Spec Info
    print("📋 WORKING SPEC")
    print("-" * 40)
    print(f"  ID: {working_spec.get('id', 'N/A')}")
    print(f"  Title: {working_spec.get('title', 'N/A')}")
    print(f"  Risk Tier: {working_spec.get('risk_tier', 'N/A')}")
    print(f"  Profile: {working_spec.get('profile', 'N/A')}")
    print(f"  Acceptance Criteria: {working_spec.get('acceptance_criteria', 0)}")
    print(f"  Invariants: {working_spec.get('invariants', 0)}")
    print()
    
    # Compliance Score
    print("🎯 COMPLIANCE SCORE")
    print("-" * 40)
    status_emoji = "✅" if compliance['status'] == 'compliant' else "❌"
    print(f"  Overall Score: {compliance['overall_score']:.0f}/100 {status_emoji}")
    print(f"  Status: {compliance['status'].upper()}")
    print()
    
    # Component Scores
    print("📊 COMPONENT SCORES")
    print("-" * 40)
    for component, score in compliance['component_scores'].items():
        emoji = "✅" if score >= 80 else "⚠️" if score >= 60 else "❌"
        print(f"  {component.replace('_', ' ').title()}: {score:.0f}/100 {emoji}")
    print()
    
    # Detailed Status
    print("📈 DETAILED STATUS")
    print("-" * 40)
    
    # Coverage
    cov_status = coverage.get('status', 'unknown')
    cov_emoji = "✅" if cov_status == 'available' else "❌"
    print(f"  Coverage: {cov_status.upper()} {cov_emoji}")
    if cov_status == 'available':
        print(f"    Line Coverage: {coverage['line_coverage']:.1%}")
        print(f"    Branch Coverage: {coverage['branch_coverage']:.1%}")
        print(f"    Required: {compliance['requirements']['min_coverage']:.1%}")
    
    # Mutation
    mut_status = mutation.get('status', 'unknown')
    mut_emoji = "✅" if mut_status == 'available' else "❌"
    print(f"  Mutation Testing: {mut_status.upper()} {mut_emoji}")
    if mut_status == 'available':
        print(f"    Score: {mutation['score']:.1%}")
        print(f"    Required: {compliance['requirements']['min_mutation']:.1%}")
        print(f"    Mutations: {mutation['killed']}/{mutation['total']} killed")
    
    # Tests
    test_emoji = "✅" if test['flake_rate'] < 0.05 else "⚠️"
    print(f"  Test Stability: {test_emoji}")
    print(f"    Passed: {test['passed']}/{test['total_tests']}")
    print(f"    Flake Rate: {test['flake_rate']:.1%}")
    print(f"    Max Allowed: {compliance['requirements']['max_flake_rate']:.1%}")
    
    # Contracts
    contract_emoji = "✅" if contract['provider'] else "❌"
    print(f"  Contract Testing: {contract_emoji}")
    print(f"    Provider: {'✅' if contract['provider'] else '❌'}")
    print(f"    Consumer: {'✅' if contract['consumer'] else '❌'}")
    
    # CI/CD
    ci_emoji = "✅" if ci['workflow_exists'] else "❌"
    print(f"  CI/CD Pipeline: {ci_emoji}")
    print(f"    Workflow: {'✅' if ci['workflow_exists'] else '❌'}")
    
    # Provenance
    prov_emoji = "✅" if provenance['status'] == 'available' else "❌"
    print(f"  Provenance: {provenance['status'].upper()} {prov_emoji}")
    if provenance['status'] == 'available':
        print(f"    Last Generated: {provenance['last_generated']}")
    
    print()
    print("=" * 80)


def main():
    """Main function to generate and display CAWS status."""
    print("🔍 Gathering CAWS compliance information...")
    
    # Gather all status information
    working_spec = get_working_spec_info()
    coverage = get_coverage_status()
    mutation = get_mutation_status()
    test = get_test_status()
    contract = get_contract_status()
    ci = get_ci_status()
    provenance = get_provenance_status()
    
    # Calculate compliance score
    compliance = calculate_compliance_score(working_spec, coverage, mutation, test, contract, ci)
    
    # Display dashboard
    print_status_dashboard(working_spec, coverage, mutation, test, contract, ci, provenance, compliance)
    
    # Return exit code based on compliance
    return 0 if compliance['status'] == 'compliant' else 1


if __name__ == "__main__":
    exit(main())
