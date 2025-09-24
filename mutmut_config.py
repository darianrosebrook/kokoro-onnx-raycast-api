"""
Mutation testing configuration for Kokoro TTS API.

This configuration defines how mutmut should run mutation testing
on the codebase, including which files to test and which to ignore.
"""

# Files to mutate (only the main API code)
paths_to_mutate = [
    "api/",
]

# Files to ignore during mutation testing
ignore_paths = [
    # Test files
    "tests/",
    "test_*.py",
    "*_test.py",
    
    # Configuration files
    "*.pyc",
    "__pycache__/",
    ".pytest_cache/",
    
    # Documentation and scripts
    "docs/",
    "scripts/",
    "tools/",
    
    # Performance and monitoring (these are often integration-heavy)
    "api/performance/",
    "api/monitoring/",
    
    # Model loading (hardware-specific, hard to test)
    "api/model/loader*.py",
    "api/model/hardware/",
    
    # Routes (mostly FastAPI boilerplate)
    "api/routes/",
    
    # Main entry point (integration-heavy)
    "api/main.py",
]

# Pre-mutation commands (setup before running mutations)
pre_mutation = [
    "python -m pytest tests/unit/test_config.py -v",
    "python -m pytest tests/unit/test_security.py -v",
]

# Post-mutation commands (cleanup after mutations)
post_mutation = [
    "echo 'Mutation testing completed'",
]

# Timeout for each mutation test (in seconds)
timeout = 30

# Number of processes to use for mutation testing
processes = 2

# Coverage threshold (mutations that don't improve coverage are skipped)
coverage_threshold = 80

# Test command to run for each mutation
test_command = "python -m pytest {test_path} -v"

# Test time multiplier (how much longer mutations can take vs original tests)
test_time_multiplier = 2.0

# Use baseline coverage to skip mutations that don't improve coverage
use_coverage = True

# Skip mutations that would result in syntax errors
skip_syntax_errors = True

# Skip mutations that would result in import errors
skip_import_errors = True

# Output format for results
output_format = "json"

# Output file for results
output_file = "mutmut-results.json"
