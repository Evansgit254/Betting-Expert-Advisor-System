
import os
import sys
import logging
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(os.getcwd())

from scripts.live_tracker import LiveOddsTracker
from src.config import settings

def test_full_flow():
    print("🚀 Starting End-to-End Alert Test...")
    
    # Initialize tracker
    tracker = LiveOddsTracker()
    
    # Mock DataFetcher source
    print("🛠️  Mocking data source...")
    tracker.fetcher.source = MagicMock()
    
    # Mock Fixtures
    fixtures_data = [{
        "market_id": "test_market_1",
        "home": "Test Home Team",
        "away": "Test Away Team",
        "start": datetime.now(timezone.utc) + timedelta(hours=1),
        "sport": "soccer_epl"
    }]
    tracker.fetcher.source.fetch_fixtures.return_value = fixtures_data
    
    # Mock Odds (High odds for Home to create value)
    odds_data = [
        {"market_id": "test_market_1", "selection": "Test Home Team", "odds": 3.0, "provider": "TestBookie"},
        {"market_id": "test_market_1", "selection": "Test Away Team", "odds": 2.0, "provider": "TestBookie"},
        {"market_id": "test_market_1", "selection": "draw", "odds": 3.0, "provider": "TestBookie"}
    ]
    tracker.fetcher.source.fetch_odds.return_value = odds_data
    
    # Mock Model (High probability for Home)
    print("🧠 Mocking ML model...")
    tracker.model = MagicMock()
    # Return probability > 1/odds (1/3.0 = 0.33). Let's say 0.5 (50%)
    # 0.5 * 3.0 = 1.5 EV (50% edge)
    tracker.model.predict_proba.return_value = 0.5
    
    # Force ACTIVE_SPORTS to just one for test
    settings.ACTIVE_SPORTS = ["soccer_epl"]
    
    print("🏃 Running check_opportunities()...")
    try:
        opportunities = tracker.check_opportunities()
        
        if opportunities:
            print(f"✅ SUCCESS: Found {len(opportunities)} value bets!")
            print("Check your Telegram for the alert.")
        else:
            print("❌ FAILURE: No opportunities found.")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_flow()
