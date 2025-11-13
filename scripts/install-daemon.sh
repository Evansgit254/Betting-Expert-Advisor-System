#!/bin/bash
# Install Betting Expert Advisor as a systemd user service
# This allows it to run in the background without needing root/sudo

set -e

# Get absolute path to project
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║    Betting Expert Advisor - Daemon Installation           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Create logs directory
mkdir -p logs

# Create systemd user directory if it doesn't exist
mkdir -p ~/.config/systemd/user

# Copy service file and replace placeholders
SERVICE_FILE="$HOME/.config/systemd/user/betting-advisor.service"

echo "📝 Creating systemd service file..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Betting Expert Advisor - Automated Betting System
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_ROOT
Environment="PATH=$PROJECT_ROOT/venv/bin:/usr/bin:/bin"
ExecStart=$PROJECT_ROOT/venv/bin/python $PROJECT_ROOT/scripts/multi_league_tracker.py --interval 3600
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_ROOT/logs/daemon.log
StandardError=append:$PROJECT_ROOT/logs/daemon-error.log

# Resource limits (adjust as needed)
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=default.target
EOF

echo "✅ Service file created at: $SERVICE_FILE"
echo ""

# Reload systemd user daemon
echo "🔄 Reloading systemd user daemon..."
systemctl --user daemon-reload

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                   ✅ INSTALLATION COMPLETE                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 NEXT STEPS:"
echo ""
echo "1. Enable auto-start on boot:"
echo "   systemctl --user enable betting-advisor"
echo ""
echo "2. Start the service now:"
echo "   systemctl --user start betting-advisor"
echo ""
echo "3. Check status:"
echo "   systemctl --user status betting-advisor"
echo ""
echo "4. View logs:"
echo "   journalctl --user -u betting-advisor -f"
echo "   or: tail -f $PROJECT_ROOT/logs/daemon.log"
echo ""
echo "5. Enable lingering (run even when not logged in):"
echo "   sudo loginctl enable-linger $USER"
echo ""
echo "📚 Management commands saved to: scripts/manage-daemon.sh"
echo ""
