#!/bin/bash
# View Docker logs

SERVICE=${1:-""}

if [ -z "$SERVICE" ]; then
    echo "📋 Viewing all logs (Ctrl+C to exit)..."
    docker-compose logs -f
else
    echo "📋 Viewing logs for: $SERVICE"
    docker-compose logs -f "$SERVICE"
fi
