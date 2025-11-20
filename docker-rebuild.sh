#!/bin/bash
# Rebuild and restart Docker containers

set -e

echo "🔨 Rebuilding Docker images..."
docker-compose build --no-cache

echo ""
echo "🔄 Restarting services..."
docker-compose down
docker-compose up -d

echo ""
echo "✅ Rebuild complete!"
echo ""
echo "View logs: ./docker-logs.sh"
