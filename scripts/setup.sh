#!/bin/bash
# Setup script for Betting Expert Advisor

set -e

echo "=== Betting Expert Advisor Setup ==="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p data models logs data/sample

# Copy .env.example to .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys and configuration"
fi

# Initialize database
echo "Initializing database..."
python3 -c "from src.db import init_db; init_db(); print('Database initialized')"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys"
echo "2. Run tests: pytest"
echo "3. Try simulation: python src/main.py --mode simulate --dry-run"
echo "4. View README.md for more information"
echo ""
