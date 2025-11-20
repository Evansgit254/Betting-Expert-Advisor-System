# 🤖 Betting Expert Advisor

A professional-grade, AI-powered sports betting system designed for automated value detection, arbitrage execution, and portfolio management.

![System Status](https://img.shields.io/badge/Status-Production%20Ready-success)
![Coverage](https://img.shields.io/badge/Leagues-6-blue)
![Models](https://img.shields.io/badge/Models-Ensemble-purple)

## 🌟 Key Features

### 🧠 Advanced Machine Learning
- **Ensemble Models**: Combines LightGBM, XGBoost, and Neural Networks for robust predictions.
- **25+ Features**: Analyzes form, injuries, head-to-head, sentiment, and market movements.
- **Automated Retraining**: Self-improving system that retrains every 3 days (Wed/Sat) and deploys only if accuracy improves >1%.
- **Sentiment Analysis**: Integrates social signals and news sentiment into predictions.

### 💰 Betting Strategy & Execution
- **Value Betting**: Identifies +EV opportunities where model probability > market implied probability.
- **Arbitrage**: Detects and executes risk-free arbitrage bets across multiple bookmakers.
- **Portfolio Optimization**: Uses Modern Portfolio Theory (Sharpe Ratio maximization) for optimal stake allocation.
- **Live In-Play**: Dynamic odds tracking and execution during matches (Over/Under, Match Winner).
- **Alternative Markets**: Supports Over/Under, BTTS, and Correct Score markets.

### 🛡️ Safety & Risk Management
- **Emergency Kill Switch**: Instantly stop all betting via API, Telegram, or CLI.
- **Circuit Breaker**: Pauses execution after consecutive failures or rapid drawdowns.
- **Bankroll Management**: Kelly Criterion staking with strict maximum limits (15% pre-match, 5% live).
- **Dry Run Mode**: Test strategies safely with simulated paper trading.

### 📊 Real-Time Dashboard
- **Live Monitoring**: WebSocket-powered dashboard updates every 3 seconds.
- **Performance Metrics**: Track ROI, Win Rate, Sharpe Ratio, and Drawdown in real-time.
- **Telegram Bot**: Receive instant alerts and control the system from your phone.

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local scripts)
- API Keys (TheOddsAPI, Betfair - optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/betting-expert-advisor.git
   cd betting-expert-advisor
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and preferences
   ```

3. **Start the System**
   ```bash
   make up
   # OR
   docker-compose up -d
   ```

4. **Access the Dashboard**
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠️ Operational Guide

### 1. Training Models
The system comes with a scheduler, but you can manually train models:
```bash
# Train ensemble models
docker exec betting-advisor-scheduler python scripts/train_ensemble.py
```

### 2. Backups & Disaster Recovery
A local backup script is provided to secure your data:
```bash
# Run manual backup
./scripts/local_backup.sh

# Restore from backup
# (See script output for exact restore command)
```
**Recommendation:** Add to crontab for daily backups: `0 2 * * * /path/to/scripts/local_backup.sh`

### 3. Live Betting
To enable live in-play betting:
1. Set `LIVE_BETTING_ENABLED=true` in `.env`
2. Ensure you have a live data provider configured.
3. Monitor `logs/live_tracker.log` for activity.

### 4. Emergency Procedures
**Stop Betting Immediately:**
- **Telegram**: Send `/kill` to the bot.
- **API**: `POST /api/emergency/stop`
- **CLI**: `make stop` or `docker-compose stop`

---

## 📂 Project Structure

```
├── src/                  # Core application source code
│   ├── adapters/         # Bookmaker API integrations (Betfair, etc.)
│   ├── markets/          # Market analyzers (Totals, BTTS)
│   ├── models/           # ML model definitions
│   ├── strategy.py       # Betting strategies & portfolio logic
│   └── ...
├── scripts/              # Utility scripts (training, backups, data)
├── frontend/             # Next.js Dashboard
├── k8s/                  # Kubernetes configurations (optional)
├── docker-compose.yml    # Local deployment config
└── Makefile              # Operational shortcuts
```

## 🤝 Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License
[MIT](LICENSE)
