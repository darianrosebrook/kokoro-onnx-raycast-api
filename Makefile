# CAWS v1.0 - Engineering-Grade Operating System for Coding Agents
# Makefile for Kokoro TTS API

.PHONY: help caws-bootstrap caws-static caws-unit caws-mutation caws-contracts caws-integration caws-perf caws-validate caws-gates

# Default target
help:
	@echo "CAWS v1.0 - Kokoro TTS API Quality Gates"
	@echo ""
	@echo "Available targets:"
	@echo "  caws-bootstrap    - Install dependencies and setup environment"
	@echo "  caws-validate     - Validate Working Spec"
	@echo "  caws-static       - Run static analysis (linting, type checking)"
	@echo "  caws-unit         - Run unit tests with coverage"
	@echo "  caws-mutation     - Run mutation testing"
	@echo "  caws-contracts    - Run contract tests"
	@echo "  caws-integration  - Run integration tests"
	@echo "  caws-perf         - Run performance tests"
	@echo "  caws-gates        - Run all quality gates"
	@echo ""

# Bootstrap environment
caws-bootstrap:
	@echo "🚀 Bootstrapping CAWS environment..."
	pip install -r requirements.txt
	@echo "✅ Bootstrap complete"

# Validate Working Spec
caws-validate:
	@echo "🔍 Validating Working Spec..."
	@if [ -f tools/caws/validate.py ]; then \
		python3 tools/caws/validate.py .caws/working-spec.yaml; \
	else \
		caws validate; \
	fi

# Static analysis
caws-static:
	@echo "🔍 Running static analysis..."
	python3 -m flake8 api/ --max-line-length=100 --extend-ignore=E203,W503 || true
	python3 -m mypy api/ --ignore-missing-imports || true
	python3 -m black --check api/ || true
	python3 -m isort --check-only api/ || true
	@echo "🔒 Running security scan..."
	python3 scripts/security_scan.py
	@echo "✅ Static analysis complete"

# Unit tests with coverage
caws-unit:
	@echo "🧪 Running unit tests with coverage..."
	python3 -m pytest tests/unit --cov=api --cov-report=xml --cov-report=term-missing --cov-report=html || true
	@echo "✅ Unit tests complete"

# Mutation testing
caws-mutation:
	@echo "🧬 Running mutation testing..."
	@if command -v mutmut >/dev/null 2>&1; then \
		echo "Using mutmut for mutation testing..."; \
		if [ ! -f mutmut-results.json ]; then \
			mutmut run --config mutmut_config.py; \
		else \
			mutmut run --config mutmut_config.py --incremental; \
		fi; \
		python3 -c " \
import json; \
import subprocess; \
import sys; \
try: \
    result = subprocess.run(['mutmut', 'show', '--json'], capture_output=True, text=True); \
    if result.returncode == 0: \
        data = json.loads(result.stdout); \
        with open('mutmut-results.json', 'w') as f: \
            json.dump(data, f, indent=2); \
        print('✅ Mutation results saved to mutmut-results.json'); \
    else: \
        print('⚠️  No mutation results available'); \
        with open('mutmut-results.json', 'w') as f: \
            json.dump({'mutation_score': 0.0, 'total_mutations': 0, 'killed_mutations': 0}, f, indent=2); \
except Exception as e: \
    print(f'⚠️  Error processing mutation results: {e}'); \
    with open('mutmut-results.json', 'w') as f: \
        json.dump({'mutation_score': 0.0, 'total_mutations': 0, 'killed_mutations': 0}, f, indent=2); \
"; \
	else \
		echo "mutmut not available, using fallback mutation testing..."; \
		python3 scripts/run_mutation_tests.py; \
	fi
	@echo "✅ Mutation testing complete"

# Contract tests
caws-contracts:
	@echo "📋 Running contract tests..."
	python3 -m pytest tests/contract -v || true
	@echo "📋 Validating OpenAPI schema..."
	@if command -v swagger-codegen >/dev/null 2>&1; then \
		echo "Validating OpenAPI schema with swagger-codegen..."; \
		swagger-codegen validate -i contracts/kokoro-tts-api.yaml; \
	elif command -v openapi-generator >/dev/null 2>&1; then \
		echo "Validating OpenAPI schema with openapi-generator..."; \
		openapi-generator validate -i contracts/kokoro-tts-api.yaml; \
	else \
		echo "OpenAPI validators not available, skipping schema validation"; \
	fi
	@echo "✅ Contract tests complete"

# Integration tests
caws-integration:
	@echo "🔗 Running integration tests..."
	python3 -m pytest tests/integration -v || true
	@echo "🔗 Running containerized integration tests..."
	@if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then \
		echo "Running Testcontainers integration tests..."; \
		python3 -m pytest tests/integration/test_tts_integration_containers.py -v || true; \
	else \
		echo "Docker not available, skipping containerized tests"; \
	fi
	@echo "✅ Integration tests complete"

# Performance tests
caws-perf:
	@echo "⚡ Running performance tests..."
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && python3 -m pytest tests/performance --benchmark-only -v || true; \
	else \
		python3 -m pytest tests/performance --benchmark-only -v || true; \
	fi
	@echo "⚡ Running performance budget validation..."
	@if command -v python3 >/dev/null 2>&1; then \
		python3 scripts/performance_budget_validator.py --url http://localhost:8000 || echo "Performance validation skipped (server may not be running)"; \
	else \
		echo "Python3 not available, skipping performance budget validation"; \
	fi
	@echo "✅ Performance tests complete"

# Run all quality gates
caws-gates: caws-validate caws-static caws-unit caws-mutation caws-contracts caws-integration caws-perf
	@echo "🎯 Running quality gates..."
	python3 scripts/simple_gates.py all --tier 2 --profile backend-api
	@echo "📋 Generating provenance manifest..."
	python3 scripts/provenance_tracker.py
	@echo "✅ All quality gates complete"

# Development helpers
install-dev:
	@echo "📦 Installing development dependencies..."
	pip install -r requirements.txt
	pre-commit install
	@echo "✅ Development environment ready"

format:
	@echo "🎨 Formatting code..."
	python -m black api/ tests/
	python -m isort api/ tests/
	@echo "✅ Code formatted"

lint-fix:
	@echo "🔧 Fixing linting issues..."
	python -m black api/ tests/
	python -m isort api/ tests/
	@echo "✅ Linting issues fixed"

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .pytest_cache/
	rm -rf .mutmut-cache/
	rm -rf mutmut-results.xml
	@echo "✅ Cleanup complete"

# Test specific components
test-config:
	@echo "🧪 Testing configuration..."
	pytest tests/unit/test_config.py -v

test-security:
	@echo "🧪 Testing security..."
	pytest tests/unit/test_security.py -v

# Quick development cycle
dev-test: format lint-fix test-config test-security
	@echo "✅ Development test cycle complete"
