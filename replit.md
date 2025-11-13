# Betting Expert Advisor - Replit Setup

## Project Overview
This is an ML-driven sports betting advisory system with automated risk management and comprehensive analytics. The system provides a monitoring API for tracking bets, model performance, and system health.

## Current Setup

### Architecture
- **Backend**: Python 3.11 with FastAPI monitoring API
- **Database**: SQLite (development), PostgreSQL-compatible
- **ML Framework**: LightGBM (lazy-loaded only when needed)
- **Monitoring**: Prometheus metrics + FastAPI health endpoints

### Active Components
- **Monitoring API Server**: Running on port 5000 (http://0.0.0.0:5000)
  - Health endpoint: `/health`
  - Metrics endpoint: `/metrics` (Prometheus format)
  - Root endpoint: `/` (API documentation)
  - Bet reporting: `/report/bet`, `/report/prediction`, `/report/error`

### Project Structure
- `src/main.py` - CLI entry point with multiple modes (fetch, train, simulate, place, serve)
- `src/monitoring.py` - FastAPI monitoring server
- `src/ml_pipeline.py` - Machine learning training pipeline
- `src/db.py` - Database models and ORM layer
- `data/` - Data storage (real historical data and sample data)
- `scripts/` - Automation scripts for paper trading, backtesting, etc.

### Important Configuration
- Environment variables are loaded from `.env` file
- systemd-python package removed from requirements (not needed in Replit)
- Lazy imports used for ML libraries to allow monitoring API to run independently

### Known Issues & Workarounds
- **LightGBM OpenMP dependency**: The `libgomp` library is required for LightGBM but causes import issues. Fixed by using lazy imports - ML functionality is only loaded when needed (train/simulate/place modes), not for monitoring API (serve mode).

## User Preferences
- **Default Mode**: DRY_RUN (no real money at risk)
- **Database**: SQLite for development
- **API Keys**: Not configured (uses mock data by default)

## Recent Changes (Import Setup)
1. Removed systemd-python from requirements (not compatible with Replit environment)
2. Modified src/main.py to use lazy imports for ML libraries
3. Set up monitoring API workflow on port 5000
4. Installed system dependencies: gcc, pkg-config

## How to Use

### Monitoring API (Current)
The monitoring server is running automatically and provides:
- Real-time system health checks
- Prometheus metrics for bets, predictions, and errors
- API endpoints for reporting betting activity

### Other Modes (Available via CLI)
```bash
# Fetch betting data
python -m src.main --mode fetch

# Train ML model
python -m src.main --mode train

# Simulate betting (paper trading)
python -m src.main --mode simulate --dry-run

# Place bets (DRY-RUN by default)
python -m src.main --mode place --dry-run
```

## Future Enhancements
- Configure TheOddsAPI key for live data
- Set up Telegram notifications
- Deploy to production with proper API keys
- Add web dashboard (Streamlit/Gradio mentioned in roadmap)
