#!/bin/bash
# Run backtest simulation

set -e

echo "=== Running Backtest Simulation ==="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run backtest
python src/backtest.py

echo ""
echo "=== Backtest Complete ==="
echo "Results saved to backtest_results.csv"
echo ""
