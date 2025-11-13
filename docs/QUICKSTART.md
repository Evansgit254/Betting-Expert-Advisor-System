# Quick Start Guide

Get up and running with Betting Expert Advisor in 5 minutes.

## Prerequisites

- Python 3.11+
- 500MB free disk space
- (Optional) Docker for containerized deployment

## Installation

### Option 1: Local Installation (Recommended for Development)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/betting-expert-advisor.git
cd betting-expert-advisor

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create configuration
cp .env.example .env

# 5. Initialize database
python -c "from src.db import init_db; init_db()"
```

### Option 2: Docker

```bash
# 1. Clone repository
git clone https://github.com/yourusername/betting-expert-advisor.git
cd betting-expert-advisor

# 2. Build and run
docker-compose up --build
```

## First Run - Simulation Mode

### Fetch Sample Data

```bash
python src/main.py --mode fetch
```

**Expected output:** Display of mock fixtures and odds

### Run Simulation

```bash
python src/main.py --mode simulate --dry-run
```

**Expected output:** 
- Value bets identified
- Simulated bet placements
- Bets saved to database

### Run Backtest

```bash
python src/backtest.py
```

**Expected output:**
- 60-day historical simulation
- Performance metrics
- Results saved to `backtest_results.csv`

## Training a Model

```bash
# Simple model training
python src/main.py --mode train

# Advanced training with hyperparameter tuning
python src/main.py --mode train --advanced
```

## Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=src --cov-report=html

# View coverage
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

## Monitoring Dashboard

```bash
# Start monitoring server
python src/main.py --mode serve

# Access at http://localhost:8000
# Endpoints:
# - /health - Health check
# - /metrics - Prometheus metrics
# - / - API info
```

### Full Monitoring Stack (Grafana + Prometheus)

```bash
cd monitoring
docker-compose up -d

# Access:
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
```

## Directory Structure After Setup

```
betting-expert-advisor/
├── data/
│   └── bets.db              # SQLite database
├── models/
│   └── model.pkl            # Trained model
├── logs/                    # Application logs
├── backtest_results.csv     # Latest backtest
└── htmlcov/                 # Coverage reports
```

## Common Commands

| Task | Command |
|------|---------|
| Fetch data | `python src/main.py --mode fetch` |
| Train model | `python src/main.py --mode train` |
| Simulate | `python src/main.py --mode simulate --dry-run` |
| Place bets (dry-run) | `python src/main.py --mode place --dry-run` |
| Run backtest | `python src/backtest.py` |
| Run tests | `pytest` |
| Start API | `python src/main.py --mode serve` |

## Configuration

Edit `.env` to configure:

```bash
# Execution mode (NEVER use LIVE without extensive testing!)
MODE=DRY_RUN

# Bankroll settings
DEFAULT_KELLY_FRACTION=0.2
MAX_STAKE_FRAC=0.05
DAILY_LOSS_LIMIT=1000
MAX_OPEN_BETS=10

# API keys (required for real data)
THEODDS_API_KEY=your_key_here
BOOKIE_API_KEY=your_key_here
```

## Verification Checklist

✅ Tests pass: `pytest`  
✅ Backtest runs: `python src/backtest.py`  
✅ Docker builds: `docker-compose build`  
✅ API starts: `python src/main.py --mode serve`  

## Next Steps

1. **Read full README.md** - Comprehensive documentation
2. **Review legal disclaimer** - Understand responsibilities
3. **Explore test files** - Learn system behavior
4. **Customize strategy** - Modify `src/strategy.py`
5. **Add real data source** - Implement adapter in `src/adapters/`

## Troubleshooting

### "No module named 'src'"
**Solution:** Run commands from project root, not `src/` directory

### "Database locked"
**Solution:** Close any other processes accessing the database

### Import errors
**Solution:** Ensure virtual environment is activated

### Tests fail
**Solution:** Check you're using Python 3.11+ and all dependencies installed

## Safety Reminders

⚠️ **ALWAYS USE DRY-RUN MODE FOR TESTING**  
⚠️ **NEVER commit API keys to version control**  
⚠️ **Consult legal counsel before live deployment**  
⚠️ **Only gamble what you can afford to lose**  

## Support

- 📖 Full documentation: [README.md](README.md)
- 🐛 Report issues: GitHub Issues
- 💬 Questions: Open a discussion
- 🤝 Contributing: See [CONTRIBUTING.md](CONTRIBUTING.md)

---

**Ready to start? Run your first simulation:**

```bash
python src/main.py --mode simulate --dry-run
```
