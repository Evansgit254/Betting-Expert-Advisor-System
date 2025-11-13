"""Centralized path configuration for the application.

All file paths are defined here to avoid hardcoding throughout the codebase.
Paths are relative to the project root and use pathlib for cross-platform compatibility.
"""
from pathlib import Path

# Get project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
REAL_DATA_DIR = DATA_DIR / "real_data"
SAMPLE_DATA_DIR = DATA_DIR / "sample"

# Model directories
MODELS_DIR = PROJECT_ROOT / "models"

# Logs directories
LOGS_DIR = PROJECT_ROOT / "logs"
DAILY_CHECKS_DIR = LOGS_DIR / "daily_checks"

# Paper trading directory
PAPER_TRADING_DIR = PROJECT_ROOT / "paper_trading"
PAPER_TRADING_FILE = PAPER_TRADING_DIR / "bets.json"

# Opportunities files
LIVE_OPPORTUNITIES_FILE = PROJECT_ROOT / "live_opportunities.json"
MULTI_LEAGUE_OPPORTUNITIES_FILE = PROJECT_ROOT / "multi_league_opportunities.json"

# Results directory
RESULTS_DIR = PROJECT_ROOT / "results"


# Ensure directories exist
def ensure_dirs():
    """Create all necessary directories if they don't exist."""
    for directory in [
        DATA_DIR,
        REAL_DATA_DIR,
        SAMPLE_DATA_DIR,
        MODELS_DIR,
        LOGS_DIR,
        DAILY_CHECKS_DIR,
        PAPER_TRADING_DIR,
        RESULTS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


# Auto-create directories on import
ensure_dirs()
