#!/bin/bash
# Run all tests with coverage

set -e

echo "=== Running Test Suite ==="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run pytest with coverage
pytest tests/ -v \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml

echo ""
echo "=== Test Results ==="
echo "Coverage report saved to htmlcov/index.html"
echo ""
