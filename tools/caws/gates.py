#!/usr/bin/env python3
"""
CAWS Quality Gates

Enforces quality gates based on risk tier and profile requirements.
Checks coverage, mutation scores, contracts, and other quality metrics.
"""
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional


def load_tier_policy() -> Dict[str, Any]:
    """Load tier policy configuration."""
    policy_path = Path(__file__).parent.parent.parent / '.caws' / 'policy' / 'tier-policy.json'
    with open(policy_path, 'r') as f:
        return json.load(f)


def load_caws_config() -> Dict[str, Any]:
    """Load CAWS configuration."""
    config_path = Path(__file__).parent.parent.parent / '.caws.yml'
    with open(config_path, 'r') as f:
        import yaml
        return yaml.safe_load(f)


def check_coverage_gate(tier: str, coverage_file: str = "coverage.xml") -> bool:
    """Check coverage gate against tier requirements."""
    policy = load_tier_policy()
    tier_config = policy.get(tier, {})
    min_coverage = tier_config.get('min_coverage', 0.8)
    metric = tier_config.get('coverage_metric', 'branch')
    
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(coverage_file)
        root = tree.getroot()
        
        # Find coverage percentage for the specified metric
        if metric == 'branch':
            coverage_elem = root.find('.//coverage[@type="branch"]')
        elif metric == 'line':
            coverage_elem = root.find('.//coverage[@type="line"]')
        else:
            print(f"❌ Unknown coverage metric: {metric}")
            return False
        
        if coverage_elem is None:
            print(f"❌ No {metric} coverage data found in {coverage_file}")
            return False
        
        coverage_percent = float(coverage_elem.get('percent', 0)) / 100
        required_percent = min_coverage
        
        print(f"📊 Coverage: {coverage_percent:.1%} (required: {required_percent:.1%})")
        
        if coverage_percent >= required_percent:
            print(f"✅ Coverage gate passed")
            return True
        else:
            print(f"❌ Coverage gate failed: {coverage_percent:.1%} < {required_percent:.1%}")
            return False
            
    except FileNotFoundError:
        print(f"❌ Coverage file not found: {coverage_file}")
        return False
    except Exception as e:
        print(f"❌ Error reading coverage file: {e}")
        return False


def check_mutation_gate(tier: str, mutation_file: str = "mutmut-results.json") -> bool:
    """Check mutation testing gate against tier requirements."""
    policy = load_tier_policy()
    tier_config = policy.get(tier, {})
    min_mutation = tier_config.get('min_mutation', 0.5)
    
    try:
        with open(mutation_file, 'r') as f:
            mutation_data = json.load(f)
        
        mutation_score = mutation_data.get('mutation_score', 0)
        required_score = min_mutation
        
        print(f"🧬 Mutation Score: {mutation_score:.1%} (required: {required_score:.1%})")
        
        if mutation_score >= required_score:
            print(f"✅ Mutation gate passed")
            return True
        else:
            print(f"❌ Mutation gate failed: {mutation_score:.1%} < {required_score:.1%}")
            return False
            
    except FileNotFoundError:
        print(f"❌ Mutation results file not found: {mutation_file}")
        return False
    except Exception as e:
        print(f"❌ Error reading mutation results: {e}")
        return False


def check_contracts_gate(tier: str, profile: str, contracts_dir: str = "contracts") -> bool:
    """Check contracts gate against tier and profile requirements."""
    policy = load_tier_policy()
    tier_config = policy.get(tier, {})
    requires_contracts = tier_config.get('requires_contracts', False)
    
    # Check profile-specific requirements
    profile_config = tier_config.get('profiles', {}).get(profile, {})
    if 'requires_contracts' in profile_config:
        requires_contracts = profile_config['requires_contracts']
    
    if not requires_contracts:
        print(f"✅ Contracts gate skipped (not required for tier {tier}, profile {profile})")
        return True
    
    contracts_path = Path(contracts_dir)
    if not contracts_path.exists():
        print(f"❌ Contracts directory not found: {contracts_dir}")
        return False
    
    contract_files = list(contracts_path.glob("*.yaml")) + list(contracts_path.glob("*.yml"))
    if not contract_files:
        print(f"❌ No contract files found in {contracts_dir}")
        return False
    
    print(f"📋 Found {len(contract_files)} contract files")
    print(f"✅ Contracts gate passed")
    return True


def check_performance_gate(tier: str, profile: str, perf_file: str = "performance-results.json") -> bool:
    """Check performance gate against tier requirements."""
    if tier == "3":
        print(f"✅ Performance gate skipped (not required for tier {tier})")
        return True
    
    if profile not in ["web-ui", "backend-api"]:
        print(f"✅ Performance gate skipped (not required for profile {profile})")
        return True
    
    try:
        with open(perf_file, 'r') as f:
            perf_data = json.load(f)
        
        # Check API performance for backend-api
        if profile == "backend-api":
            api_p95 = perf_data.get('api_p95_ms', 0)
            if api_p95 > 0:
                print(f"⚡ API P95: {api_p95}ms")
                if api_p95 <= 1000:  # 1 second threshold
                    print(f"✅ Performance gate passed")
                    return True
                else:
                    print(f"❌ Performance gate failed: {api_p95}ms > 1000ms")
                    return False
        
        # Check web performance for web-ui
        elif profile == "web-ui":
            lcp = perf_data.get('lcp_ms', 0)
            if lcp > 0:
                print(f"⚡ LCP: {lcp}ms")
                if lcp <= 2500:  # 2.5 second threshold
                    print(f"✅ Performance gate passed")
                    return True
                else:
                    print(f"❌ Performance gate failed: {lcp}ms > 2500ms")
                    return False
        
        print(f"✅ Performance gate passed (no specific metrics to check)")
        return True
        
    except FileNotFoundError:
        print(f"⚠️  Performance results file not found: {perf_file}")
        print(f"✅ Performance gate passed (no results to check)")
        return True
    except Exception as e:
        print(f"❌ Error reading performance results: {e}")
        return False


def calculate_trust_score(tier: str, profile: str, results: Dict[str, Any]) -> int:
    """Calculate trust score based on gate results."""
    weights = {
        'coverage': 0.25,
        'mutation': 0.25,
        'contracts': 0.2,
        'a11y': 0.1,
        'perf': 0.1,
        'flake': 0.1,
    }
    
    policy = load_tier_policy()
    tier_config = policy.get(tier, {})
    
    # Calculate weighted score
    score = 0.0
    
    # Coverage score
    coverage_value = results.get('coverage', 0)
    min_coverage = tier_config.get('min_coverage', 0.8)
    coverage_score = min(coverage_value / min_coverage, 1.0) if min_coverage > 0 else 1.0
    score += weights['coverage'] * coverage_score
    
    # Mutation score
    mutation_value = results.get('mutation', 0)
    min_mutation = tier_config.get('min_mutation', 0.5)
    mutation_score = min(mutation_value / min_mutation, 1.0) if min_mutation > 0 else 1.0
    score += weights['mutation'] * mutation_score
    
    # Contracts score
    contracts_passed = results.get('contracts', False)
    score += weights['contracts'] * (1.0 if contracts_passed else 0.0)
    
    # Performance score
    perf_passed = results.get('perf', False)
    score += weights['perf'] * (1.0 if perf_passed else 0.0)
    
    # A11y score (not applicable for backend-api)
    a11y_passed = results.get('a11y', True)  # Default to True for backend
    score += weights['a11y'] * (1.0 if a11y_passed else 0.0)
    
    # Flake score
    flake_rate = results.get('flake_rate', 0.0)
    flake_score = 1.0 if flake_rate <= 0.005 else 0.5
    score += weights['flake'] * flake_score
    
    return int(score * 100)


def main():
    """Main gates function."""
    parser = argparse.ArgumentParser(description="CAWS Quality Gates")
    parser.add_argument('gate', choices=['coverage', 'mutation', 'contracts', 'perf', 'trust', 'all'],
                       help='Gate to check')
    parser.add_argument('--tier', required=True, help='Risk tier (1, 2, or 3)')
    parser.add_argument('--profile', help='Profile (web-ui, backend-api, library, cli)')
    parser.add_argument('--coverage-file', default='coverage.xml', help='Coverage file path')
    parser.add_argument('--mutation-file', default='mutmut-results.json', help='Mutation results file path')
    parser.add_argument('--perf-file', default='performance-results.json', help='Performance results file path')
    parser.add_argument('--contracts-dir', default='contracts', help='Contracts directory path')
    
    args = parser.parse_args()
    
    # Load profile from CAWS config if not provided
    if not args.profile:
        caws_config = load_caws_config()
        args.profile = caws_config.get('default_profile', 'backend-api')
    
    print(f"🔍 Checking {args.gate} gate for tier {args.tier}, profile {args.profile}")
    
    results = {}
    all_passed = True
    
    if args.gate in ['coverage', 'all']:
        results['coverage'] = 0.8 if check_coverage_gate(args.tier, args.coverage_file) else 0.0
        if not results['coverage']:
            all_passed = False
    
    if args.gate in ['mutation', 'all']:
        results['mutation'] = 0.5 if check_mutation_gate(args.tier, args.mutation_file) else 0.0
        if not results['mutation']:
            all_passed = False
    
    if args.gate in ['contracts', 'all']:
        results['contracts'] = check_contracts_gate(args.tier, args.profile, args.contracts_dir)
        if not results['contracts']:
            all_passed = False
    
    if args.gate in ['perf', 'all']:
        results['perf'] = check_performance_gate(args.tier, args.profile, args.perf_file)
        if not results['perf']:
            all_passed = False
    
    if args.gate in ['trust', 'all']:
        trust_score = calculate_trust_score(args.tier, args.profile, results)
        print(f"🎯 Trust Score: {trust_score}/100")
        
        if trust_score >= 80:
            print(f"✅ Trust score gate passed")
        else:
            print(f"❌ Trust score gate failed: {trust_score} < 80")
            all_passed = False
    
    if not all_passed:
        sys.exit(1)
    
    print(f"✅ All gates passed!")


if __name__ == "__main__":
    main()
