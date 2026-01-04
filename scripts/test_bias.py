#!/usr/bin/env python3
"""Verification script for home team bias fix."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.generate_daily_odds import analyze_fixture
from src.social.ml_predictor import get_predictor

def test_away_favorite():
    """Test that away favorites can be correctly identified."""
    predictor = get_predictor()
    
    # Mock fixture where away team is a heavy favorite with VALUE
    fixture = {
        'id': 'test_away_fav',
        'home_team': 'Underdog FC',
        'away_team': 'Giant United',
        'commence_time': '2026-01-05T15:00:00Z',
        'league': 'soccer_epl',
        'bookmakers': [
            {
                'key': 'tight_bookie',
                'markets': [
                    {
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Giant United', 'price': 1.25}, # Implies 80% prob
                            {'name': 'Underdog FC', 'price': 10.0},
                            {'name': 'Draw', 'price': 5.5}
                        ]
                    }
                ]
            },
            {
                'key': 'value_bookie',
                'markets': [
                    {
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Giant United', 'price': 1.50}, # 20% value!
                            {'name': 'Underdog FC', 'price': 8.0},
                            {'name': 'Draw', 'price': 4.0}
                        ]
                    }
                ]
            }
        ]
    }
    
    print(f"Analyzing: {fixture['home_team']} vs {fixture['away_team']}")
    print(f"Best Odds: Home @ 10.0, Away @ 1.50, Draw @ 5.5")
    
    results = analyze_fixture(fixture, predictor)
    
    if results:
        for result in results:
            print(f"[{result['market']}] Result: {result['prediction'].upper()} @ {result['odds']:.2f} (Confidence: {result['confidence']:.2%}, EV: {result.get('ev', 0):+.2f})")
            if result['market'] == 'Match Winner' and result['prediction'] == 'away':
                print("✅ SUCCESS: Correctly identified away win value opportunity.")
    else:
        print("❌ FAILURE: No recommendation generated.")

def test_home_favorite():
    """Test that home favorites are still correctly identified."""
    predictor = get_predictor()
    
    # Mock fixture where home team is a heavy favorite and has Over/Under odds
    fixture = {
        'id': 'test_home_fav',
        'home_team': 'Giant United',
        'away_team': 'Underdog FC',
        'commence_time': '2026-01-05T15:00:00Z',
        'league': 'soccer_epl',
        'bookmakers': [
            {
                'key': 'onexbet',
                'title': '1xBet',
                'markets': [
                    {
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Giant United', 'price': 1.25},
                            {'name': 'Underdog FC', 'price': 10.0},
                            {'name': 'Draw', 'price': 5.5}
                        ]
                    },
                    {
                        'key': 'totals',
                        'outcomes': [
                            {'name': 'Over 2.5', 'price': 1.80},
                            {'name': 'Under 2.5', 'price': 2.00}
                        ]
                    }
                ]
            }
        ]
    }
    
    print(f"\nAnalyzing: {fixture['home_team']} vs {fixture['away_team']}")
    print(f"Odds: Home @ 1.25, Away @ 10.0, Draw @ 5.5")
    print(f"Odds: Over 2.5 @ 1.80, Under 2.5 @ 2.00")
    
    results = analyze_fixture(fixture, predictor)
    
    if results:
        for result in results:
            print(f"[{result['market']}] Result: {result['prediction'].upper()} @ {result['odds']:.2f} (Confidence: {result['confidence']:.2%})")
            if result['market'] == 'Match Winner' and result['prediction'] == 'home':
                print("✅ SUCCESS: Correctly identified home win opportunity.")
            if 'Over/Under' in result['market']:
                print(f"✅ SUCCESS: Correctly processed Over/Under market.")
    else:
        print("❌ FAILURE: No recommendation generated.")

if __name__ == "__main__":
    test_away_favorite()
    test_home_favorite()
