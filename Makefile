# CAWS v1.0 - Engineering-Grade Operating System for Coding Agents
# Makefile for Kokoro TTS API

.PHONY: help caws-bootstrap caws-static caws-unit caws-mutation caws-contracts caws-integration caws-e2e caws-a11y caws-perf caws-validate caws-gates

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
	@echo "  caws-e2e          - Run end-to-end tests"
	@echo "  caws-a11y         - Run accessibility tests"
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
	python tools/caws/validate.py .caws/working-spec.yaml

# Static analysis
caws-static:
	@echo "🔍 Running static analysis..."
	python -m flake8 api/ --max-line-length=100 --extend-ignore=E203,W503
	python -m mypy api/ --ignore-missing-imports
	python -m black --check api/
	python -m isort --check-only api/
	@echo "✅ Static analysis complete"

# Unit tests with coverage
caws-unit:
	@echo "🧪 Running unit tests with coverage..."
	pytest tests/unit --cov=api --cov-report=xml --cov-report=term-missing --cov-report=html
	@echo "✅ Unit tests complete"

# Mutation testing
caws-mutation:
	@echo "🧬 Running mutation testing..."
	mutmut run --paths-to-mutate=api/
	mutmut junitxml > mutmut-results.xml
	@echo "✅ Mutation testing complete"

# Contract tests
caws-contracts:
	@echo "📋 Running contract tests..."
	pytest tests/contract -v
	@echo "✅ Contract tests complete"

# Integration tests
caws-integration:
	@echo "🔗 Running integration tests..."
	pytest tests/integration -v
	@echo "✅ Integration tests complete"

# End-to-end tests
caws-e2e:
	@echo "🎯 Running end-to-end tests..."
	pytest tests/e2e -v
	@echo "✅ End-to-end tests complete"

# Accessibility tests
caws-a11y:
	@echo "♿ Running accessibility tests..."
	@echo "No a11y tests for backend-api profile"
	@echo "✅ Accessibility tests complete"

# Performance tests
caws-perf:
	@echo "⚡ Running performance tests..."
	pytest tests/performance --benchmark-only -v
	@echo "✅ Performance tests complete"

# Run all quality gates
caws-gates: caws-validate caws-static caws-unit caws-mutation caws-contracts caws-integration caws-perf
	@echo "🎯 Running quality gates..."
	python tools/caws/gates.py all --tier 2 --profile backend-api
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
