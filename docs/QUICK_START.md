# Quick Start Guide 🚀

**Betting Expert Advisor - Getting Started**

---

## Available Commands

### 1. **Fetch Odds Data**
```bash
# Using mock data (no API key required)
python -m src.main --mode fetch

# Using real TheOddsAPI (requires API key)
export THEODDS_API_KEY=your_api_key_here
python -m src.main --mode fetch
```

### 2. **Train ML Model**
```bash
# Simple training (fast)
python -m src.main --mode train

# Advanced training with cross-validation (slower, better results)
python -m src.main --mode train --advanced
```

### 3. **Simulate Betting**
```bash
# Simulate with default $10,000 bankroll
python -m src.main --mode simulate

# Simulate with custom bankroll
python -m src.main --mode simulate --bankroll 5000
```

### 4. **Place Bets (Dry Run)**
```bash
# Dry run mode (safe - no real money)
python -m src.main --mode place --dry-run

# Live mode (requires bookmaker API configured)
python -m src.main --mode place
```

### 5. **Start Web Server**
```bash
# Start API server on default port 8000
python -m src.main --mode serve

# Custom host and port
python -m src.main --mode serve --host 0.0.0.0 --port 5000
```

---

## Common Workflows

### Workflow 1: Test with Mock Data (No API Keys)

```bash
# 1. Fetch mock data
python -m src.main --mode fetch

# 2. Train a model
python -m src.main --mode train

# 3. Simulate betting
python -m src.main --mode simulate --bankroll 10000
```

### Workflow 2: Use Real Odds Data

**Step 1: Get API Key**
- Sign up at https://the-odds-api.com/
- Get your free API key (500 requests/month)

**Step 2: Configure**
```bash
# Create .env file
cat > .env << EOF
THEODDS_API_KEY=your_api_key_here
MODE=DRY_RUN
DB_URL=sqlite:///./data/bets.db
EOF
```

**Step 3: Fetch Real Data**
```bash
python -m src.main --mode fetch
```

### Workflow 3: Full Betting Pipeline

```bash
# 1. Train model on synthetic data
python -m src.main --mode train --advanced

# 2. Fetch live odds
python -m src.main --mode fetch

# 3. Place bets (dry run)
python -m src.main --mode place --dry-run

# 4. Check database
python scripts/verify_db.py
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Operation Mode
MODE=DRY_RUN              # DRY_RUN or LIVE
ENV=development           # development or production

# Database
DB_URL=sqlite:///./data/bets.db

# TheOddsAPI (for real odds data)
THEODDS_API_KEY=your_key_here
THEODDS_API_BASE=https://api.the-odds-api.com/v4

# Betfair (optional)
BETFAIR_APP_KEY=your_key_here
BETFAIR_SESSION_TOKEN=your_token_here

# Risk Management
DEFAULT_KELLY_FRACTION=0.2     # 20% Kelly (conservative)
MAX_STAKE_FRAC=0.05            # Max 5% of bankroll per bet
DAILY_LOSS_LIMIT=1000.0        # Max daily loss
MAX_OPEN_BETS=10               # Max concurrent bets

# Logging
LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR
```

### Config File

Settings are in `src/config.py`:

```python
class Settings(BaseSettings):
    ENV: str = "development"
    DB_URL: str = "sqlite:///./data/bets.db"
    MODE: str = "DRY_RUN"
    DEFAULT_KELLY_FRACTION: float = 0.2
    MAX_STAKE_FRAC: float = 0.05
    DAILY_LOSS_LIMIT: float = 1000.0
    MAX_OPEN_BETS: int = 10
```

---

## Examples

### Example 1: Train and Simulate

```bash
# Train a model
python -m src.main --mode train

# Output:
# INFO:__main__:=== Train Mode ===
# INFO:__main__:Generating synthetic training data...
# INFO:__main__:Building features...
# INFO:__main__:Training on 1800 samples
# Model trained with accuracy: 0.62

# Simulate betting
python -m src.main --mode simulate --bankroll 10000

# Output:
# INFO:__main__:=== Simulate Mode ===
# Bankroll: $10000.00
# Total bets: 15
# Win rate: 53.3%
# Final P&L: $+234.50
```

### Example 2: Fetch Live Odds

```bash
# Set API key
export THEODDS_API_KEY=abc123xyz

# Fetch odds
python -m src.main --mode fetch

# Output:
# INFO:__main__:Fetched 50 fixtures
#    market_id              home              away  home_odds  away_odds
# 0  abc123    Manchester United  Liverpool FC        2.10       3.50
# 1  def456    Arsenal FC         Chelsea FC         1.85       4.20
# ...
```

### Example 3: Place Bets (Dry Run)

```bash
python -m src.main --mode place --dry-run

# Output:
# INFO:__main__:=== Place Mode ===
# INFO:src.executor:[DRY-RUN] Executing bet: market_123 - home @ 2.5 for $100.00
# INFO:src.executor:Bet saved to database with ID 20
# 
# Bets placed: 3
# Total staked: $450.00
# Status: All bets saved to database
```

---

## Testing Commands

### Run Quick System Test
```bash
python scripts/quick_system_test.py

# Output:
# ✅ Database
# ✅ Risk
# ✅ Execution
# ✅ Persistence
# ✅ Backtesting
# Result: 5/5 tests passed (100%)
# 🎉 ALL SYSTEMS OPERATIONAL!
```

### Run Full Test Suite
```bash
pytest tests/ -v --cov=src

# Output:
# 439 passed, 12 skipped in 54.20s
# Coverage: 65%
```

### Verify Database
```bash
python scripts/verify_db.py

# Output:
# ✅ Database file exists: sqlite:///./data/bets.db
# 📊 Tables found (5):
#   • bets
#   • model_metadata
#   • strategy_performance
#   • daily_stats
#   • alembic_version
# ✅ All expected tables present!
```

---

## Data Sources

### 1. Mock Data (Default - No API Key Needed)
- **Location:** `src/data_fetcher.py` → `MockDataSource`
- **Usage:** Automatic when no API key configured
- **Data:** Synthetic fixtures and odds

### 2. TheOddsAPI (Real Data)
- **Website:** https://the-odds-api.com/
- **Free Tier:** 500 requests/month
- **Sports:** Soccer, Basketball, Baseball, Hockey, etc.
- **Regions:** US, UK, EU, AU

### 3. Betfair Exchange (Advanced)
- **Website:** https://www.betfair.com/
- **Type:** Betting exchange
- **Requires:** App key and session token
- **Features:** Market depth, live odds

---

## Database Queries

### View Recent Bets
```bash
# Using Python
python << EOF
from src.db import get_session, BetRecord
with get_session() as session:
    bets = session.query(BetRecord).limit(10).all()
    for bet in bets:
        print(f"{bet.market_id}: ${bet.stake:.2f} @ {bet.odds} - {bet.result}")
EOF
```

### Get Statistics
```python
from src.db import get_session, BetRecord
from sqlalchemy import func

with get_session() as session:
    stats = session.query(
        func.count(BetRecord.id).label('total'),
        func.sum(BetRecord.stake).label('total_staked'),
        func.sum(BetRecord.profit_loss).label('total_pl')
    ).filter(BetRecord.is_dry_run == False).first()
    
    print(f"Total bets: {stats.total}")
    print(f"Total staked: ${stats.total_staked:.2f}")
    print(f"Total P&L: ${stats.total_pl:.2f}")
```

---

## Troubleshooting

### Issue: "No fixtures fetched"
**Cause:** Using MockDataSource with empty data  
**Solution:** Configure THEODDS_API_KEY for real data

### Issue: "API key invalid"
**Cause:** Invalid or expired API key  
**Solution:** Check your API key at https://the-odds-api.com/account/

### Issue: "Database is locked"
**Cause:** Multiple processes accessing database  
**Solution:** Close other connections or use PostgreSQL for production

### Issue: "No value bets found"
**Cause:** Edge thresholds too strict  
**Solution:** This is normal - adjust thresholds in strategy or wait for better opportunities

---

## Performance Tips

1. **Use advanced training for better predictions**
   ```bash
   python -m src.main --mode train --advanced
   ```

2. **Adjust Kelly fraction for conservative betting**
   ```bash
   export DEFAULT_KELLY_FRACTION=0.1  # 10% Kelly (very conservative)
   ```

3. **Set appropriate edge thresholds**
   ```python
   # In src/strategy.py
   min_edge = 0.03  # Require 3% edge minimum
   ```

4. **Enable detailed logging**
   ```bash
   export LOG_LEVEL=DEBUG
   ```

---

## Going Live Checklist

Before switching to LIVE mode:

- [ ] Tested extensively in DRY_RUN mode
- [ ] Configured real bookmaker API credentials
- [ ] Set appropriate bankroll limits
- [ ] Configured daily loss limits
- [ ] Tested with small stakes first
- [ ] Set up monitoring and alerts
- [ ] Backed up database
- [ ] Reviewed and understood all bets being placed

**Switch to live:**
```bash
export MODE=LIVE
python -m src.main --mode place
```

---

## Support & Documentation

- 📖 **Full Test Results:** `SYSTEM_TEST_RESULTS.md`
- 🗄️ **Database Setup:** `DATABASE_SETUP.md`
- 🧪 **Test Resolution:** `SKIPPED_TESTS_RESOLUTION.md`
- 🏗️ **Architecture:** `CODEBASE_INSPECTION_REPORT.md`

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `--mode fetch` | Get odds data |
| `--mode train` | Train ML model |
| `--mode simulate` | Run backtest simulation |
| `--mode place` | Place bets |
| `--mode serve` | Start API server |
| `--dry-run` | Safe mode (no real money) |
| `--bankroll N` | Set bankroll amount |
| `--advanced` | Use advanced ML training |
| `--help` | Show all options |

---

**Ready to get started? Try this:**

```bash
# Complete workflow with mock data
python -m src.main --mode train
python -m src.main --mode simulate --bankroll 10000
python scripts/verify_db.py
```

🎯 **Your betting system is ready to use!**
