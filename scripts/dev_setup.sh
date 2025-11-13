#!/bin/bash
# Development environment setup script
# This script sets up the complete development environment

set -e  # Exit on error

echo "🚀 Setting up Betting Expert Advisor development environment..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}Error: Python $required_version or higher is required${NC}"
    echo "Current version: $python_version"
    exit 1
fi
echo -e "${GREEN}✓ Python version OK: $python_version${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Install development dependencies
echo -e "${YELLOW}Installing development dependencies...${NC}"
pip install \
    pytest \
    pytest-cov \
    pytest-asyncio \
    black \
    flake8 \
    mypy \
    isort \
    pre-commit \
    ipython \
    jupyter

# Setup pre-commit hooks
echo -e "${YELLOW}Setting up pre-commit hooks...${NC}"
pre-commit install
echo -e "${GREEN}✓ Pre-commit hooks installed${NC}"

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p data/sample
mkdir -p logs
mkdir -p models
mkdir -p reports
echo -e "${GREEN}✓ Directories created${NC}"

# Copy .env.example to .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠️  Please update .env with your API keys${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
python -c "from src.db import init_db; init_db()"
echo -e "${GREEN}✓ Database initialized${NC}"

# Run tests to verify setup
echo -e "${YELLOW}Running tests to verify setup...${NC}"
pytest tests/ -v --tb=short -x

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed. Please check the output above.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Development environment setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Update .env with your API keys"
echo "3. Run tests: pytest tests/"
echo "4. Start developing!"
echo ""
echo "Useful commands:"
echo "  - Run tests: pytest tests/ -v"
echo "  - Run with coverage: pytest --cov=src --cov-report=html"
echo "  - Format code: black src/ tests/"
echo "  - Lint code: flake8 src/ tests/"
echo "  - Type check: mypy src/"
echo ""
