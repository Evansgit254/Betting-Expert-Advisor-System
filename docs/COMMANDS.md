# Command Reference 📖

**Quick command guide for Betting Expert Advisor**

---

## ✅ Working Commands

### 1. Run Interactive Demo
```bash
python demo.py
```
**What it does:**
- Shows complete betting workflow
- Analyzes 3 sample opportunities
- Calculates Kelly stakes
- Executes bets in dry-run mode
- Simulates results
- Updates database

**Output:**
```
💰 Starting Bankroll: $10,000.00
📊 Opportunities Analyzed: 3
✅ Value Bets Found: 3
🎯 Bets Executed: 3
💵 Total Staked: $203.46
```

---

### 2. Test System Integration
```bash
python scripts/quick_system_test.py
```
**What it does:**
- Tests all 5 core components
- Validates database, risk management, execution, persistence, backtesting
- Shows pass/fail for each

**Output:**
```
✅ Database
✅ Risk
✅ Execution
✅ Persistence
✅ Backtesting
Result: 5/5 tests passed (100%)
🎉 ALL SYSTEMS OPERATIONAL!
```

---

### 3. Verify Database
```bash
python scripts/verify_db.py
```
**What it does:**
- Lists all database tables
- Shows column counts
- Verifies schema

**Output:**
```
✅ Database file exists: sqlite:///./data/bets.db

📊 Tables found (5):
  • bets (14 columns)
  • model_metadata (9 columns)
  • strategy_performance (18 columns)
  • daily_stats (11 columns)
  • alembic_version (1 column)
  
✅ All expected tables present!
```

---

### 4. Initialize/Reset Database
```bash
python scripts/init_db.py
```
**What it does:**
- Creates all tables
- Runs migrations
- Sets up schema

**Output:**
```
Creating database tables...
Running database migrations...
Migrations completed successfully!
Database initialized successfully!
```

---

### 5. Run Full Test Suite
```bash
pytest tests/ -v --cov=src
```
**What it does:**
- Runs all 451 unit and integration tests
- Generates code coverage report

**Output:**
```
439 passed, 12 skipped in 54.20s
Coverage: 65%
```

---

### 6. Run Specific Test Files
```bash
# Database tests
pytest tests/test_db.py -v

# Risk management tests
pytest tests/test_risk.py -v

# Executor tests
pytest tests/test_executor_coverage.py -v

# Backtest tests
pytest tests/test_backtest.py -v
```

---

## 🚧 Commands Needing Configuration

### Fetch Live Odds (Requires API Key)
```bash
# Set API key first
export THEODDS_API_KEY=your_api_key_here

# Then fetch
python -m src.main --mode fetch
```

### Train ML Model (Has minor bugs - use demo instead)
```bash
python -m src.main --mode train
# Note: Currently has data format issues
# Use demo.py for working example
```

### Simulate Betting
```bash
python -m src.main --mode simulate --bankroll 10000
```

### Place Bets
```bash
# Dry run (safe)
python -m src.main --mode place --dry-run

# Live mode (requires bookmaker API)
export MODE=LIVE
python -m src.main --mode place
```

### Start Web Server
```bash
python -m src.main --mode serve --host 127.0.0.1 --port 8000
```

---

## 📊 Database Query Commands

### View All Bets
```bash
python -c "
from src.db import get_session, BetRecord
with get_session() as session:
    bets = session.query(BetRecord).all()
    print(f'Total bets: {len(bets)}')
    for bet in bets[:10]:
        print(f'{bet.id}: {bet.market_id} - \${bet.stake:.2f} @ {bet.odds} - {bet.result}')
"
```

### Get Statistics
```bash
python -c "
from src.db import get_session, BetRecord
from sqlalchemy import func

with get_session() as session:
    total = session.query(func.count(BetRecord.id)).scalar()
    staked = session.query(func.sum(BetRecord.stake)).scalar() or 0
    pl = session.query(func.sum(BetRecord.profit_loss)).scalar() or 0
    
    print(f'Total bets: {total}')
    print(f'Total staked: \${staked:.2f}')
    print(f'Total P&L: \${pl:.2f}')
    print(f'ROI: {(pl/staked*100) if staked > 0 else 0:.2f}%')
"
```

### Filter Bets
```bash
python -c "
from src.db import get_session, BetRecord

with get_session() as session:
    # Only winning bets
    wins = session.query(BetRecord).filter(BetRecord.result == 'win').all()
    print(f'Winning bets: {len(wins)}')
    
    # Only dry run bets
    dry_runs = session.query(BetRecord).filter(BetRecord.is_dry_run == True).all()
    print(f'Dry run bets: {len(dry_runs)}')
"
```

---

## 🎯 Recommended Workflow

### For Learning/Testing:
```bash
# 1. Run the demo
python demo.py

# 2. Check database
python scripts/verify_db.py

# 3. Run system tests
python scripts/quick_system_test.py

# 4. Run full test suite
pytest tests/ -v
```

### For Development:
```bash
# 1. Initialize database
python scripts/init_db.py

# 2. Run tests
pytest tests/ -v --cov=src --cov-report=html

# 3. View coverage
open htmlcov/index.html  # or xdg-open on Linux

# 4. Test specific features
python demo.py
```

### For Production:
```bash
# 1. Set environment
export MODE=LIVE
export THEODDS_API_KEY=your_key
export DB_URL=postgresql://user:pass@localhost/betting_db

# 2. Initialize database
python scripts/init_db.py

# 3. Test with dry run
python -m src.main --mode place --dry-run

# 4. Monitor
python scripts/verify_db.py
```

---

## 🔧 Useful One-Liners

### Count bets by result:
```bash
python -c "from src.db import get_session, BetRecord; from sqlalchemy import func; session = get_session().__enter__(); print(session.query(BetRecord.result, func.count(BetRecord.id)).group_by(BetRecord.result).all())"
```

### Get recent bets:
```bash
python -c "from src.db import get_session, BetRecord; session = get_session().__enter__(); [print(f'{b.id}: {b.market_id} @ {b.odds}') for b in session.query(BetRecord).order_by(BetRecord.placed_at.desc()).limit(5)]"
```

### Calculate win rate:
```bash
python -c "from src.db import get_session, BetRecord; from sqlalchemy import func; session = get_session().__enter__(); total = session.query(func.count(BetRecord.id)).filter(BetRecord.result != None).scalar(); wins = session.query(func.count(BetRecord.id)).filter(BetRecord.result == 'win').scalar(); print(f'Win rate: {wins/total*100 if total > 0 else 0:.1f}% ({wins}/{total})')"
```

---

## 📝 Help Commands

```bash
# Show all options
python -m src.main --help

# Show pytest options
pytest --help

# Show available tests
pytest --collect-only
```

---

## 🎯 Quick Start

If you're new to the system, start here:

```bash
# 1. See it in action
python demo.py

# 2. Verify everything works
python scripts/quick_system_test.py

# 3. Check the database
python scripts/verify_db.py

# Done! You're ready to use the system.
```

---

## 📚 Documentation Files

- `COMMANDS.md` - This file
- `QUICK_START.md` - Detailed getting started guide  
- `SYSTEM_TEST_RESULTS.md` - Test results and system status
- `DATABASE_SETUP.md` - Database documentation
- `SKIPPED_TESTS_RESOLUTION.md` - Test fixes applied

---

*Last updated: October 28, 2025*
