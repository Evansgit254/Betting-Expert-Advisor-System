# Installation & Setup Guide

Complete step-by-step installation instructions for Betting Expert Advisor.

---

## System Requirements

### Minimum Requirements
- **OS**: Linux, macOS, or Windows 10+
- **Python**: 3.11 or higher
- **RAM**: 2GB minimum, 4GB recommended
- **Disk**: 500MB free space
- **Network**: Internet connection for API access

### Optional Requirements
- **Docker**: 20.10+ (for containerized deployment)
- **Docker Compose**: 1.29+ (for monitoring stack)

---

## Installation Methods

Choose the method that best suits your needs:

### Method 1: Standard Python Installation (Recommended)

#### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/betting-expert-advisor.git
cd betting-expert-advisor
```

#### Step 2: Create Virtual Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

#### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected output:** Installation of ~20 packages including pandas, scikit-learn, lightgbm, etc.

#### Step 4: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your preferred text editor:
```bash
nano .env  # or vim, code, etc.
```

**Minimal configuration for testing:**
```env
ENV=development
DB_URL=sqlite:///./data/bets.db
MODE=DRY_RUN
```

#### Step 5: Initialize Database

```bash
python -c "from src.db import init_db; init_db()"
```

**Expected output:** Database tables created in `data/bets.db`

#### Step 6: Verify Installation

```bash
# Run tests
pytest

# Run simulation
python src/main.py --mode simulate --dry-run
```

---

### Method 2: Docker Installation

#### Step 1: Install Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**macOS:**
Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop)

**Windows:**
Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop)

#### Step 2: Clone Repository

```bash
git clone https://github.com/yourusername/betting-expert-advisor.git
cd betting-expert-advisor
```

#### Step 3: Build and Run

```bash
# Build image
docker-compose build

# Run simulation
docker-compose up
```

**Expected output:** Container starts and runs simulation mode

#### Step 4: Access Running Container

```bash
# List containers
docker ps

# Execute commands inside container
docker-compose exec app python src/main.py --mode fetch
```

---

### Method 3: Quick Setup Script (Linux/macOS)

```bash
# Clone repository
git clone https://github.com/yourusername/betting-expert-advisor.git
cd betting-expert-advisor

# Make script executable
chmod +x scripts/setup.sh

# Run setup
./scripts/setup.sh
```

The script will:
- ✅ Check Python version
- ✅ Create virtual environment
- ✅ Install dependencies
- ✅ Create `.env` file
- ✅ Initialize database

---

## Post-Installation Setup

### 1. Directory Structure Verification

After installation, verify these directories exist:

```bash
ls -la
```

You should see:
```
data/          # Database storage
models/        # ML model artifacts
logs/          # Application logs (created on first run)
data/sample/   # Sample datasets
```

### 2. Configuration

Edit `.env` to configure the system:

```bash
# Execution mode (CRITICAL: Use DRY_RUN for testing)
MODE=DRY_RUN

# Risk management parameters
DEFAULT_KELLY_FRACTION=0.2    # Conservative Kelly (20%)
MAX_STAKE_FRAC=0.05           # Max 5% of bankroll per bet
DAILY_LOSS_LIMIT=1000         # Stop trading after $1000 daily loss
MAX_OPEN_BETS=10              # Max concurrent positions

# Database (SQLite for local, PostgreSQL for production)
DB_URL=sqlite:///./data/bets.db

# Logging
LOG_LEVEL=INFO
```

### 3. API Keys (Optional - for real data)

If using real data sources, add API keys to `.env`:

```bash
# TheOddsAPI
THEODDS_API_KEY=your_theodds_api_key_here

# Betfair Exchange
BETFAIR_APP_KEY=your_betfair_app_key
BETFAIR_SESSION_TOKEN=your_session_token

# Bookmaker API
BOOKIE_API_BASE_URL=https://api.yourbookie.com
BOOKIE_API_KEY=your_bookie_api_key
```

**⚠️ SECURITY WARNING:**
- Never commit `.env` to version control
- Never share API keys publicly
- Rotate keys regularly
- Use environment-specific keys (dev/staging/prod)

---

## Verification Tests

### 1. Import Test

```bash
python -c "import src; print('✓ Package imports successfully')"
```

### 2. Database Test

```bash
python -c "from src.db import init_db, get_session; init_db(); print('✓ Database initialized')"
```

### 3. Unit Tests

```bash
pytest tests/ -v
```

**Expected:** All tests pass (may skip some if dependencies missing)

### 4. Simulation Test

```bash
python src/main.py --mode simulate --dry-run
```

**Expected:** System finds mock fixtures, identifies value bets, simulates placement

### 5. Backtest Test

```bash
python src/backtest.py
```

**Expected:** 
- Generates synthetic data
- Runs 60-day backtest
- Outputs results to `backtest_results.csv`
- Prints summary statistics

---

## Troubleshooting

### Common Issues

#### Issue: `ModuleNotFoundError: No module named 'src'`

**Cause:** Running from wrong directory  
**Solution:** 
```bash
cd /path/to/betting-expert-advisor
python src/main.py --mode simulate
```

#### Issue: `ModuleNotFoundError: No module named 'sqlalchemy'`

**Cause:** Dependencies not installed  
**Solution:**
```bash
pip install -r requirements.txt
```

#### Issue: `PermissionError` on database file

**Cause:** Insufficient permissions  
**Solution:**
```bash
mkdir -p data
chmod 755 data
```

#### Issue: Python version too old

**Cause:** Python < 3.11  
**Solution:** Install Python 3.11+
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv

# macOS (using Homebrew)
brew install python@3.11
```

#### Issue: Docker build fails

**Cause:** Docker daemon not running  
**Solution:**
```bash
# Start Docker
sudo systemctl start docker  # Linux
# or open Docker Desktop on macOS/Windows
```

#### Issue: Port 8000 already in use

**Cause:** Another service using port  
**Solution:** Change port in command:
```bash
python src/main.py --mode serve --port 8001
```

---

## Environment-Specific Setup

### Development Environment

```bash
# .env
ENV=development
MODE=DRY_RUN
LOG_LEVEL=DEBUG
DB_URL=sqlite:///./data/dev.db
```

### Testing Environment

```bash
# .env.test
ENV=testing
MODE=DRY_RUN
LOG_LEVEL=WARNING
DB_URL=sqlite:///./data/test.db
```

### Production Environment

```bash
# .env.production (use secret management!)
ENV=production
MODE=DRY_RUN  # NEVER set to LIVE without extensive validation
LOG_LEVEL=INFO
DB_URL=postgresql://user:pass@localhost:5432/betting_db
```

---

## Optional Components

### Monitoring Stack (Grafana + Prometheus)

```bash
cd monitoring
docker-compose up -d
```

**Access:**
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Application metrics: http://localhost:8000/metrics

### IDE Setup (VS Code)

Recommended extensions:
- Python (Microsoft)
- Pylance
- Black Formatter
- autoDocstring

VS Code settings (`.vscode/settings.json`):
```json
{
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.testing.pytestEnabled": true
}
```

---

## Next Steps After Installation

1. **Read Documentation**
   - Review [README.md](README.md) for comprehensive overview
   - Check [QUICKSTART.md](QUICKSTART.md) for quick examples

2. **Run First Simulation**
   ```bash
   python src/main.py --mode simulate --dry-run
   ```

3. **Explore Codebase**
   - `src/strategy.py` - Betting strategy
   - `src/risk.py` - Risk management
   - `src/feature.py` - Feature engineering

4. **Run Tests**
   ```bash
   pytest --cov=src --cov-report=html
   open htmlcov/index.html
   ```

5. **Execute Backtest**
   ```bash
   python src/backtest.py
   ```

6. **Review Legal Requirements**
   - Read [LICENSE](LICENSE)
   - Understand legal responsibilities
   - Consult legal counsel before live deployment

---

## Uninstallation

### Remove Python Installation

```bash
# Deactivate virtual environment
deactivate

# Remove directory
cd ..
rm -rf betting-expert-advisor
```

### Remove Docker Installation

```bash
# Stop containers
docker-compose down

# Remove images
docker rmi betting-advisor:latest

# Remove volumes
docker volume prune
```

---

## Getting Help

- 📖 **Documentation**: See [README.md](README.md)
- 🐛 **Bug Reports**: Open GitHub issue
- 💬 **Questions**: GitHub Discussions
- 🤝 **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Safety Checklist Before First Run

- [ ] Using DRY_RUN mode (not LIVE)
- [ ] No real API keys in testing environment
- [ ] Database initialized successfully
- [ ] Tests passing
- [ ] Understanding of legal disclaimers
- [ ] Appropriate bankroll settings configured

---

**Installation complete! You're ready to explore the system.**

**Start with:** `python src/main.py --mode simulate --dry-run`
