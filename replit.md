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
  - Dashboard: `/` (Web-based monitoring dashboard)
  - Health endpoint: `/health`
  - Metrics endpoint: `/metrics` (Prometheus format)
  - API info: `/api/info`
  - Bet reporting: `/report/bet`, `/report/prediction`, `/report/error`
  - Circuit breakers: Auto-protect all external API calls

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
- **Database Session Management**: Unified on `handle_db_errors()` context manager across entire codebase for consistent error handling and transaction management

### Known Issues & Workarounds
- **LightGBM OpenMP dependency**: The `libgomp` library is required for LightGBM but causes import issues. Fixed by using lazy imports - ML functionality is only loaded when needed (train/simulate/place modes), not for monitoring API (serve mode).

## User Preferences
- **Default Mode**: DRY_RUN (no real money at risk)
- **Database**: SQLite for development
- **API Keys**: Not configured (uses mock data by default)

## Recent Changes

### Production Upgrade (November 14, 2025) 🚀
**Complete production-ready upgrade with resilience, observability, and deployment infrastructure:**

**Circuit Breakers & Resilience**:
- Implemented pybreaker-based circuit breakers for all external APIs (TheOdds, Pinnacle, Betfair)
- Configurable failure thresholds and reset timeouts
- Automatic fallback to cached data when services unavailable
- Circuit breaker status monitoring endpoint

**Global Exception Handling**:
- FastAPI global exception handler with request correlation IDs
- Pydantic validation models for all API endpoints
- Automatic critical error alerting via send_alert()
- Structured error responses with full traceability

**Configuration-Driven Risk Management**:
- Moved 15+ magic numbers to Settings class in src/config.py
- Risk thresholds: consecutive losses, drawdown warnings, rate limiting
- Betting constraints: min/max odds, stakes, edge requirements
- Backtest defaults: days, initial bankroll, games per day

**Code Quality**:
- Consolidated EV calculations (removed duplicate from utils.py)
- Logger standardization verified across codebase
- Code formatting applied (black, isort)
- Critical flake8 issues resolved

**Docker & CI/CD**:
- Multi-stage Dockerfile with non-root user (appuser)
- docker-compose.yml with PostgreSQL 15 + Redis 7 + health checks
- PostgreSQL driver added (psycopg2-binary)
- Enhanced CI pipeline: linting, testing, Docker builds, security scanning

**Monitoring Dashboard**:
- Web-based monitoring dashboard at http://0.0.0.0:5000
- Real-time system status, health checks, metrics visualization
- Circuit breaker status table
- API endpoint documentation
- Auto-refresh every 30 seconds

**Files Created**: `src/adapters/_circuit.py`, `src/static/dashboard.html`, `PRODUCTION_UPGRADE_REPORT.md`  
**Files Modified**: 12 files across src/, Docker configs, requirements  
**Architect Reviewed**: ✅ All task groups reviewed, critical issues fixed  
**Status**: PRODUCTION-READY ✅

### Database Session Management Refactoring (November 13, 2025)
**Complete refactoring to standardize database session handling:**
- Unified all database access to use `handle_db_errors()` context manager exclusively
- Removed deprecated `get_session()` wrapper function from codebase
- Updated 20+ files across core modules, scripts, demo files, and tests
- **Architect Reviewed**: ✅ Passed - no regressions, backward compatibility maintained

### Initial Setup (November 2025)
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

## Production Deployment

### Quick Start with Docker
```bash
# Start all services (PostgreSQL, Redis, App, Monitoring)
docker-compose up -d

# View logs
docker-compose logs -f monitoring

# Access dashboard
open http://localhost:5000
```

### Production Checklist
- [ ] Configure API keys (THEODDS_API_KEY, BETFAIR_APP_KEY)
- [ ] Set ENV=production, MODE=DRY_RUN
- [ ] Complete 30-day paper trading validation
- [ ] Set up Telegram alerting (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
- [ ] Configure PostgreSQL with backups
- [ ] Review risk thresholds in src/config.py
- [ ] Test circuit breakers with simulated failures
- [ ] Set up monitoring and alerting infrastructure

### Future Enhancements
- WebSocket support for real-time dashboard updates
- Grafana/Prometheus stack for advanced monitoring
- Distributed tracing (OpenTelemetry)
- Automated backtesting in CI/CD pipeline
- Blue-green deployment strategy
- Automated model retraining pipeline
