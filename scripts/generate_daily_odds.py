#!/usr/bin/env python3
"""Generate 5+ daily betting opportunities automatically."""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / '.env')

from src.logging_config import get_logger
from src.social.ml_predictor import get_predictor
from src.notifications.telegram import send_odds_alert, send_daily_report
from src.analytics.stats import analytics

logger = get_logger(__name__)

# Multiple leagues for coverage
LEAGUES = [
    'soccer_epl',              # English Premier League
    'soccer_spain_la_liga',    # Spanish La Liga
    'soccer_germany_bundesliga', # German Bundesliga
    'soccer_italy_serie_a',    # Italian Serie A
    'soccer_france_ligue_one', # French Ligue 1
    'soccer_england_championship', # English Championship
    'soccer_uefa_champs_league', # Champions League
    'soccer_uefa_europa_league', # Europa League
]

API_KEY = '66c905085e910a6165abb27261bc2e48'
BASE_URL = 'https://api.the-odds-api.com/v4'

def fetch_all_fixtures():
    """Fetch fixtures from all leagues."""
    all_fixtures = []
    
    for league in LEAGUES:
        try:
            response = requests.get(
                f'{BASE_URL}/sports/{league}/odds',
                params={
                    'apiKey': API_KEY,
                    'regions': 'uk,eu,us',
                    'markets': 'h2h',
                    'oddsFormat': 'decimal'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                fixtures = response.json()
                for fixture in fixtures:
                    fixture['league'] = league
                all_fixtures.extend(fixtures)
                logger.info(f"✓ {league}: {len(fixtures)} fixtures")
            else:
                logger.warning(f"✗ {league}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching {league}: {e}")
    
    return all_fixtures


def analyze_fixture(fixture, predictor, max_hours=36):
    """Analyze a fixture and generate recommendation if within time window."""
    try:
        # Check time window
        commence_time = datetime.strptime(fixture['commence_time'], '%Y-%m-%dT%H:%M:%SZ')
        now = datetime.utcnow()
        if commence_time < now or commence_time > now + timedelta(hours=max_hours):
            return None

        # Extract odds
        bookmakers = fixture.get('bookmakers', [])
        if not bookmakers:
            return None
        
        # Get best odds
        best_home = max([m['markets'][0]['outcomes'][0]['price'] 
                        for m in bookmakers if m['markets']], default=2.0)
        best_away = max([m['markets'][0]['outcomes'][1]['price'] 
                        for m in bookmakers if m['markets']], default=2.0)
        best_draw = max([m['markets'][0]['outcomes'][2]['price'] 
                        for m in bookmakers if m['markets'] 
                        and len(m['markets'][0]['outcomes']) > 2], default=3.0)
        
        # Mock sentiment data (in production, fetch from database)
        # For now, use odds to infer sentiment
        if best_home < best_away:
            sentiment_score = 0.3 + (best_away - best_home) * 0.1
        else:
            sentiment_score = -0.3 - (best_home - best_away) * 0.1
        
        # Prepare data for ML
        match_data = {
            'sentiment_score': sentiment_score,
            'positive_pct': 50 + (sentiment_score * 30),
            'negative_pct': 50 - (sentiment_score * 30),
            'neutral_pct': 20,
            'sample_count': 75,  # Mock
            'home_odds': best_home,
            'away_odds': best_away,
            'draw_odds': best_draw,
        }
        
        # Get ML prediction
        prediction = predictor.predict(match_data)
        
        # Only return if confidence meets threshold
        if prediction['confidence'] < 0.60:
            return None
        
        # Calculate expected value
        prob = prediction['probabilities'][prediction['predicted_outcome']]
        if prediction['predicted_outcome'] == 'home':
            odds = best_home
        elif prediction['predicted_outcome'] == 'away':
            odds = best_away
        else:
            odds = best_draw
        
        ev = (prob * odds) - 1
        
        # Determine tier
        if prediction['confidence'] >= 0.80 and ev >= 0.10:
            tier = 1
        elif prediction['confidence'] >= 0.70 and ev >= 0.05:
            tier = 2
        else:
            tier = 3
        
        return {
            'fixture_id': fixture['id'],
            'league': fixture['league'],
            'home_team': fixture['home_team'],
            'away_team': fixture['away_team'],
            'commence_time': fixture['commence_time'],
            'prediction': prediction['predicted_outcome'],
            'confidence': prediction['confidence'],
            'odds': odds,
            'probabilities': prediction['probabilities'],
            'expected_value': ev,
            'tier': tier,
            'reason': f"ML model predicts {prediction['predicted_outcome']} with {prediction['confidence']:.0%} confidence (EV: {ev:+.1%})"
        }
        
    except Exception as e:
        logger.error(f"Error analyzing fixture: {e}")
        return None


def generate_daily_report(recommendations):
    """Generate formatted daily report."""
    if not recommendations:
        return "❌ No recommendations found today"
    
    # Sort by tier and confidence
    recommendations.sort(key=lambda x: (x['tier'], -x['confidence']))
    
    # Group by tier
    tier1 = [r for r in recommendations if r['tier'] == 1]
    tier2 = [r for r in recommendations if r['tier'] == 2]
    tier3 = [r for r in recommendations if r['tier'] == 3]
    
    report = []
    report.append("=" * 70)
    report.append(f"📊 DAILY BETTING OPPORTUNITIES - {datetime.now().strftime('%B %d, %Y')}")
    report.append("=" * 70)
    report.append("")
    
    if tier1:
        report.append(f"🎯 TIER 1 - HIGHEST QUALITY ({len(tier1)} opportunities)")
        report.append("-" * 70)
        for i, rec in enumerate(tier1, 1):
            report.append(f"{i}. {rec['home_team']} vs {rec['away_team']}")
            report.append(f"   League: {rec['league']}")
            report.append(f"   Prediction: {rec['prediction'].upper()} @ {rec['odds']:.2f}")
            report.append(f"   Confidence: {rec['confidence']:.0%} | EV: {rec['expected_value']:+.1%}")
            report.append(f"   Time: {rec['commence_time']}")
            report.append("")
    
    if tier2:
        report.append(f"⭐ TIER 2 - HIGH QUALITY ({len(tier2)} opportunities)")
        report.append("-" * 70)
        for i, rec in enumerate(tier2, 1):
            report.append(f"{i}. {rec['home_team']} vs {rec['away_team']}")
            report.append(f"   Prediction: {rec['prediction'].upper()} @ {rec['odds']:.2f}")
            report.append(f"   Confidence: {rec['confidence']:.0%} | EV: {rec['expected_value']:+.1%}")
            report.append("")
    
    if tier3:
        report.append(f"💡 TIER 3 - GOOD QUALITY ({len(tier3)} opportunities)")
        report.append("-" * 70)
        for i, rec in enumerate(tier3, 1):
            report.append(f"{i}. {rec['home_team']} vs {rec['away_team']}")
            report.append(f"   Prediction: {rec['prediction'].upper()} @ {rec['odds']:.2f}")
            report.append(f"   Confidence: {rec['confidence']:.0%}")
            report.append("")
    
    report.append("=" * 70)
    report.append(f"📈 TOTAL: {len(recommendations)} opportunities")
    report.append(f"🎯 TARGET: 5+ opportunities (Status: {'✅ MET' if len(recommendations) >= 5 else '⚠️ BELOW TARGET'})")
    report.append("=" * 70)
    
    return "\n".join(report)


def main():
    """Main execution."""
    print("=" * 70)
    print("  DAILY ODDS GENERATOR")
    print("=" * 70)
    print()
    
    # Load ML predictor
    print("🤖 Loading ML predictor...")
    predictor = get_predictor()
    print()
    
    # Fetch fixtures
    print(f"📊 Fetching fixtures from {len(LEAGUES)} leagues...")
    fixtures = fetch_all_fixtures()
    print(f"✓ Found {len(fixtures)} total fixtures")
    print()
    
    # Analyze fixtures
    print("🔍 Analyzing fixtures with ML model...")
    recommendations = []
    
    for fixture in fixtures:
        rec = analyze_fixture(fixture, predictor)
        if rec:
            recommendations.append(rec)
    
    print(f"✓ Generated {len(recommendations)} recommendations")
    print()
    
    # Save to analytics
    print("💾 Saving to analytics...")
    analytics.save_recommendations(recommendations)
    
    # Calculate stats
    stats = analytics.calculate_stats(recommendations)
    
    # Generate report
    report = generate_daily_report(recommendations)
    print(report)
    
    # Save to file
    report_file = f"daily_odds_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print()
    print(f"📄 Report saved to: {report_file}")
    print()
    
    # Send Telegram notifications
    if recommendations:
        print("📱 Sending Telegram alerts...")
        if send_odds_alert(recommendations):
            print("✅ Instant alert sent to Telegram")
        
        if send_daily_report(stats):
            print("✅ Daily report sent to Telegram")
    print()
    
    # Return exit code based on target
    if len(recommendations) >= 5:
        print("✅ SUCCESS: Target of 5+ opportunities met!")
        return 0
    else:
        print(f"⚠️  WARNING: Only {len(recommendations)} opportunities found (target: 5+)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
