#!/bin/bash
# Manage the Betting Expert Advisor daemon

SERVICE="betting-advisor"

case "$1" in
    start)
        echo "🚀 Starting Betting Expert Advisor daemon..."
        systemctl --user start $SERVICE
        systemctl --user status $SERVICE --no-pager
        ;;
    stop)
        echo "⏹️  Stopping Betting Expert Advisor daemon..."
        systemctl --user stop $SERVICE
        echo "✅ Stopped"
        ;;
    restart)
        echo "🔄 Restarting Betting Expert Advisor daemon..."
        systemctl --user restart $SERVICE
        systemctl --user status $SERVICE --no-pager
        ;;
    status)
        systemctl --user status $SERVICE --no-pager
        ;;
    logs)
        echo "📋 Live logs (Ctrl+C to exit):"
        journalctl --user -u $SERVICE -f
        ;;
    logs-file)
        echo "📋 Daemon log file (Ctrl+C to exit):"
        tail -f "$(dirname "$0")/../logs/daemon.log"
        ;;
    enable)
        echo "✅ Enabling auto-start on boot..."
        systemctl --user enable $SERVICE
        echo "🔐 Enabling lingering (run when not logged in)..."
        sudo loginctl enable-linger $USER
        echo "✅ Done! Service will start automatically on boot."
        ;;
    disable)
        echo "⏹️  Disabling auto-start..."
        systemctl --user disable $SERVICE
        echo "✅ Done"
        ;;
    install)
        echo "Running installation..."
        "$(dirname "$0")/install-daemon.sh"
        ;;
    uninstall)
        echo "🗑️  Uninstalling daemon..."
        systemctl --user stop $SERVICE 2>/dev/null || true
        systemctl --user disable $SERVICE 2>/dev/null || true
        rm -f ~/.config/systemd/user/$SERVICE.service
        systemctl --user daemon-reload
        echo "✅ Uninstalled"
        ;;
    *)
        echo "╔════════════════════════════════════════════════════════════╗"
        echo "║       Betting Expert Advisor - Daemon Manager             ║"
        echo "╚════════════════════════════════════════════════════════════╝"
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "COMMANDS:"
        echo "  install    - Install the daemon (first time setup)"
        echo "  start      - Start the daemon"
        echo "  stop       - Stop the daemon"
        echo "  restart    - Restart the daemon"
        echo "  status     - Check daemon status"
        echo "  logs       - View live logs (systemd journal)"
        echo "  logs-file  - View live logs (log file)"
        echo "  enable     - Enable auto-start on boot"
        echo "  disable    - Disable auto-start"
        echo "  uninstall  - Remove the daemon"
        echo ""
        echo "EXAMPLES:"
        echo "  $0 install      # First time setup"
        echo "  $0 start        # Start monitoring"
        echo "  $0 logs         # Watch live activity"
        echo "  $0 enable       # Auto-start on boot"
        echo ""
        exit 1
        ;;
esac
