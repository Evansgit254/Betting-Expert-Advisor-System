#!/bin/bash
# Daily automated monitoring script
# Add to crontab for automated checks: 0 9,15,21 * * * /path/to/daily_monitor.sh

# Get the directory where this script is located, then go to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

# Activate virtual environment
source venv/bin/activate

# Set timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="logs/daily_checks"
mkdir -p "$LOG_DIR"

echo "=================================================="
echo "  Daily Betting System Check - $TIMESTAMP"
echo "=================================================="

# 1. Check system status
echo ""
echo "📊 System Status..."
python scripts/dashboard.py | tee "$LOG_DIR/dashboard_$TIMESTAMP.log"

# 2. Check for opportunities across all leagues
echo ""
echo "🌍 Checking all leagues..."
python scripts/multi_league_tracker.py --once | tee "$LOG_DIR/opportunities_$TIMESTAMP.log"

# 3. Send summary email (if configured)
# Uncomment and configure if you want email notifications
# python scripts/send_daily_report.py

echo ""
echo "=================================================="
echo "  Check complete - $TIMESTAMP"
echo "=================================================="
echo ""
echo "Logs saved to: $LOG_DIR/"
