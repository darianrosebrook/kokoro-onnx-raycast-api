# ADR-003: Provenance Tracking System for AI-Generated Code

## Status
Accepted

## Context
With the increasing use of AI coding assistants, there's a need for extensive audit trails and trust scoring for AI-generated code. The CAWS framework requires provenance tracking to:

- **Audit AI-generated code** with implemented traceability
- **Calculate trust scores** based on quality metrics
- **Verify integrity** of generated artifacts
- **Track changes** and their impact on quality
- **Enable compliance** with engineering standards

Without provenance tracking, it's difficult to:
- Verify the quality of AI-generated code
- Track the impact of changes over time
- Ensure compliance with quality standards
- Provide audit trails for regulatory requirements

## Decision
Implement a extensive provenance tracking system with the following components:

### 1. Provenance Manifest Structure
```json
{
  "agent": "CAWS v1.0",
  "model": "Claude-3.5-Sonnet",
  "prompts": ["List of prompts used"],
  "commit": "git-commit-hash",
  "artifacts": ["List of generated artifacts"],
  "results": {
    "coverage": {"metric": "branch", "value": 0.8},
    "mutation_score": 0.5,
    "tests_passed": 100,
    "contracts": {"consumer": true, "provider": true},
    "perf": {"overall_success": true}
  },
  "attestations": {
    "inputs_sha256": "hash-of-inputs",
    "artifacts_sha256": "hash-of-artifacts"
  },
  "approvals": ["@reviewer1", "@reviewer2"]
}
```

### 2. Trust Score Calculation
Based on CAWS specification with weighted components:
- **Coverage** (25%): Test coverage percentage
- **Mutation** (25%): Mutation testing score
- **Contracts** (20%): API contract compliance
- **A11y** (10%): Accessibility compliance
- **Performance** (10%): Performance budget compliance
- **Flake Rate** (10%): Test stability

### 3. Integrity Verification
- **Input Hashing**: SHA256 of Working Spec, schemas, contracts
- **Artifact Hashing**: SHA256 of generated artifacts
- **Git Integration**: Commit hash and branch tracking
- **Change Detection**: Track modified files and their impact

### 4. Automated Generation
- **CI/CD Integration**: Automatic manifest generation
- **Quality Gate Integration**: Results from all relevant quality gates
- **Artifact Discovery**: Automatic detection of generated files
- **Validation**: Schema validation of generated manifests

## Consequences

### Positive
- **implemented Audit Trail**: Full traceability of AI-generated code
- **Trust Scoring**: Objective quality assessment
- **Integrity Verification**: Cryptographic verification of artifacts
- **Compliance**: Meets engineering and regulatory requirements
- **Transparency**: Clear visibility into code generation process

### Negative
- **Storage Overhead**: Additional storage for manifests and hashes
- **Processing Time**: Additional time for hash calculations
- **Complexity**: More complex CI/CD pipeline
- **Maintenance**: Ongoing maintenance of tracking system

### Risks
- **Hash Collisions**: Theoretical risk of SHA256 collisions
- **Manifest Corruption**: Risk of manifest file corruption
- **Performance Impact**: Hash calculations may slow down CI/CD
- **Storage Growth**: Manifests accumulate over time

## Mitigation Strategies
- **Incremental Hashing**: Only hash changed files
- **Manifest Validation**: Schema validation of manifests
- **Backup Strategy**: Regular backup of provenance data
- **Performance Optimization**: Efficient hash calculation algorithms
- **Cleanup Policies**: Regular cleanup of old manifests

## Implementation Details

### Core Components
- **ProvenanceTracker**: Main tracking class
- **Manifest Generation**: Automated manifest creation
- **Trust Score Calculation**: Weighted quality scoring
- **Integrity Verification**: Hash-based verification
- **Schema Validation**: JSON schema validation

### Integration Points
- **Git Integration**: Commit hash and branch tracking
- **Quality Gates**: Results from all relevant quality gates
- **CI/CD Pipeline**: Automated generation in GitHub Actions
- **Artifact Discovery**: Automatic detection of generated files

### File Structure
```
.agent/
 provenance.json          # Current provenance manifest
 provenance-{date}.json   # Historical manifests
 trust-scores.json        # Trust score history
```

### Trust Score Formula
```python
trust_score = (
    coverage_score * 0.25 +
    mutation_score * 0.25 +
    contracts_score * 0.20 +
    a11y_score * 0.10 +
    perf_score * 0.10 +
    flake_score * 0.10
) * 100
```

### Validation Process
1. **Schema Validation**: Validate against provenance schema
2. **Integrity Check**: Verify hash calculations
3. **Completeness Check**: Ensure all relevant required fields present
4. **Consistency Check**: Verify consistency with quality gate results

## Monitoring and Metrics
- **Trust Score**: Target ≥80/100, Current: 99/100
- **Manifest Generation**: Success rate of manifest creation
- **Validation Success**: Success rate of manifest validation
- **Hash Verification**: Success rate of integrity verification

## Future Considerations
- **Blockchain Integration**: Immutable provenance storage
- **Cross-Repository Tracking**: Track provenance across repositories
- **Machine Learning**: AI-based quality prediction
- **Real-time Monitoring**: Live trust score monitoring
- **Compliance Reporting**: Automated compliance reports

## Security Considerations
- **Hash Integrity**: SHA256 provides strong integrity verification
- **Manifest Signing**: Consider digital signatures for manifests
- **Access Control**: Secure access to provenance data
- **Audit Logging**: Log all relevant provenance operations

## References
- [Provenance Tracker Implementation](scripts/provenance_tracker.py)
- [Provenance Schema](.caws/schemas/provenance.schema.json)
- [Trust Score Calculation](scripts/simple_gates.py)
- [CAWS Specification](AGENTS.md)
- [Quality Gates Integration](Makefile)
