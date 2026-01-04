#!/usr/bin/env python3
"""Script to test Telegram alerts with mock data."""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.notifications.telegram import send_odds_alert

def main():
    print("🚀 Sending test Telegram alert...")
    
    mock_recommendations = [
        {
            'home_team': 'Villarreal',
            'away_team': 'Real Madrid',
            'league': 'La Liga',
            'market': 'Match Winner',
            'prediction': 'away',
            'odds': 1.85,
            'confidence': 0.82,
            'ev': 0.12,
            'tier': 1,
            'commence_time': '2026-01-05T20:00:00'
        },
        {
            'home_team': 'Villarreal',
            'away_team': 'Real Madrid',
            'league': 'La Liga',
            'market': 'Over/Under 2.5',
            'prediction': 'OVER 2.5',
            'odds': 1.75,
            'confidence': 0.75,
            'ev': 0.08,
            'tier': 2,
            'commence_time': '2026-01-05T20:00:00'
        },
        {
            'home_team': 'Getafe',
            'away_team': 'Atletico Madrid',
            'league': 'La Liga',
            'market': 'Match Winner',
            'prediction': 'draw',
            'odds': 3.20,
            'confidence': 0.65,
            'ev': 0.05,
            'tier': 2,
            'commence_time': '2026-01-05T18:00:00'
        }
    ]
    
    success = send_odds_alert(mock_recommendations)
    
    if success:
        print("✅ Success! Check your Telegram for the alert.")
    else:
        print("❌ Failed to send Telegram alert. Check logs and .env configuration.")

if __name__ == "__main__":
    main()
