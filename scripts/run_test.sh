#!/bin/bash
# Simple wrapper to run the endpoint test

set -e

cd "$(dirname "$0")/.."

echo "Installing websockets if needed..."
source .venv/bin/activate
pip install -q websockets

echo ""
echo "Running full endpoint test..."
echo ""

python3 scripts/test_endpoints.py















