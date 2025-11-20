#!/bin/bash
# Start all Docker containers for Betting Expert Advisor

set -e

echo "=========================================="
echo "  Betting Expert Advisor - Docker Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with required configuration."
    exit 1
fi

# Stop any running containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build images
echo ""
echo "🔨 Building Docker images..."
docker-compose build --no-cache

# Start services
echo ""
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service status
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "=========================================="
echo "  ✅ All Services Started!"
echo "=========================================="
echo ""
echo "Available services:"
echo "  🌐 Frontend Dashboard: http://localhost:3000"
echo "  📊 Analytics Dashboard: http://localhost:3000/analytics"
echo "  🔌 API Server: http://localhost:8000"
echo "  📈 API Docs: http://localhost:8000/docs"
echo "  🗄️  PostgreSQL: localhost:5433"
echo "  🔴 Redis: localhost:6380"
echo ""
echo "Logs:"
echo "  View all logs: docker-compose logs -f"
echo "  API logs: docker-compose logs -f api"
echo "  Scheduler logs: docker-compose logs -f scheduler"
echo "  Frontend logs: docker-compose logs -f frontend"
echo ""
echo "Management:"
echo "  Stop all: docker-compose down"
echo "  Restart: docker-compose restart"
echo "  View status: docker-compose ps"
echo ""
echo "🎉 System is ready! Check your Telegram for alerts."
echo ""
