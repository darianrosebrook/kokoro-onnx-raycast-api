#!/usr/bin/env python3
"""
CAWS Working Spec Validator

Validates Working Spec YAML files against the CAWS schema and enforces
quality gates based on risk tier and profile requirements.
"""
import json
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List
import jsonschema
from jsonschema import validate, ValidationError


def load_schema(schema_path: str) -> Dict[str, Any]:
    """Load JSON schema from file."""
    with open(schema_path, 'r') as f:
        return json.load(f)


def load_working_spec(spec_path: str) -> Dict[str, Any]:
    """Load Working Spec YAML from file."""
    with open(spec_path, 'r') as f:
        return yaml.safe_load(f)


def validate_working_spec(spec: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate Working Spec against schema and return list of errors."""
    errors = []
    
    try:
        validate(instance=spec, schema=schema)
    except ValidationError as e:
        errors.append(f"Schema validation error: {e.message}")
        if e.absolute_path:
            errors.append(f"  Path: {' -> '.join(str(p) for p in e.absolute_path)}")
    
    return errors


def validate_risk_tier_requirements(spec: Dict[str, Any]) -> List[str]:
    """Validate risk tier specific requirements."""
    errors = []
    risk_tier = spec.get('risk_tier')
    profile = spec.get('profile')
    
    if risk_tier == 1:
        # Tier 1 requirements
        if not spec.get('contracts'):
            errors.append("Tier 1 requires contracts to be defined")
        
        if not spec.get('non_functional', {}).get('security'):
            errors.append("Tier 1 requires security requirements to be defined")
    
    elif risk_tier == 2:
        # Tier 2 requirements
        if profile == 'backend-api' and not spec.get('contracts'):
            errors.append("Tier 2 backend-api requires contracts to be defined")
        
        if not spec.get('non_functional', {}).get('perf'):
            errors.append("Tier 2 requires performance requirements to be defined")
    
    return errors


def validate_acceptance_criteria(spec: Dict[str, Any]) -> List[str]:
    """Validate acceptance criteria format and completeness."""
    errors = []
    acceptance = spec.get('acceptance', [])
    
    if not acceptance:
        errors.append("At least one acceptance criterion is required")
        return errors
    
    for i, criterion in enumerate(acceptance):
        if not criterion.get('id'):
            errors.append(f"Acceptance criterion {i+1} missing 'id' field")
        
        if not criterion.get('given'):
            errors.append(f"Acceptance criterion {i+1} missing 'given' field")
        
        if not criterion.get('when'):
            errors.append(f"Acceptance criterion {i+1} missing 'when' field")
        
        if not criterion.get('then'):
            errors.append(f"Acceptance criterion {i+1} missing 'then' field")
        
        # Validate ID format
        criterion_id = criterion.get('id', '')
        if criterion_id and not criterion_id.startswith('A'):
            errors.append(f"Acceptance criterion {i+1} ID must start with 'A': {criterion_id}")
    
    return errors


def validate_invariants(spec: Dict[str, Any]) -> List[str]:
    """Validate invariants are defined and meaningful."""
    errors = []
    invariants = spec.get('invariants', [])
    
    if not invariants:
        errors.append("At least one invariant is required")
        return errors
    
    for i, invariant in enumerate(invariants):
        if not invariant or len(invariant.strip()) < 10:
            errors.append(f"Invariant {i+1} is too short or empty: '{invariant}'")
    
    return errors


def validate_scope_definition(spec: Dict[str, Any]) -> List[str]:
    """Validate scope is well-defined."""
    errors = []
    scope = spec.get('scope', {})
    
    if not scope.get('in'):
        errors.append("Scope 'in' is required and must not be empty")
    elif len(scope['in']) < 2:
        errors.append("Scope 'in' should have at least 2 items for clarity")
    
    if not scope.get('out'):
        errors.append("Scope 'out' is required (can be empty array)")
    
    return errors


def main():
    """Main validation function."""
    if len(sys.argv) != 2:
        print("Usage: python validate.py <working-spec.yaml>")
        sys.exit(1)
    
    spec_path = sys.argv[1]
    
    # Load schema and spec
    schema_path = Path(__file__).parent.parent.parent / '.caws' / 'schemas' / 'working-spec.schema.json'
    schema = load_schema(str(schema_path))
    spec = load_working_spec(spec_path)
    
    # Collect all validation errors
    all_errors = []
    
    # Schema validation
    all_errors.extend(validate_working_spec(spec, schema))
    
    # Risk tier requirements
    all_errors.extend(validate_risk_tier_requirements(spec))
    
    # Acceptance criteria
    all_errors.extend(validate_acceptance_criteria(spec))
    
    # Invariants
    all_errors.extend(validate_invariants(spec))
    
    # Scope definition
    all_errors.extend(validate_scope_definition(spec))
    
    # Report results
    if all_errors:
        print("❌ Working Spec validation failed:")
        for error in all_errors:
            print(f"  • {error}")
        sys.exit(1)
    else:
        print("✅ Working Spec validation passed")
        print(f"  • Risk Tier: {spec.get('risk_tier')}")
        print(f"  • Profile: {spec.get('profile')}")
        print(f"  • Acceptance Criteria: {len(spec.get('acceptance', []))}")
        print(f"  • Invariants: {len(spec.get('invariants', []))}")


if __name__ == "__main__":
    main()
