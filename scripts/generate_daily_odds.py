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
from src.social.aggregator import get_match_sentiment

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

API_KEY = os.getenv('THEODDS_API_KEY')
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
    """Analyze a fixture and generate recommendations for multiple markets."""
    try:
        # Check time window
        commence_time = datetime.strptime(fixture['commence_time'], '%Y-%m-%dT%H:%M:%SZ')
        now = datetime.utcnow()
        if commence_time < now or commence_time > now + timedelta(hours=max_hours):
            return []

        # Extract all odds
        bookmakers = fixture.get('bookmakers', [])
        if not bookmakers:
            return []
        
        home_team = fixture['home_team']
        away_team = fixture['away_team']
        
        # We'll collect multiple recommendations per fixture
        recommendations = []
        
        # 1. H2H Market Analysis
        best_home = 0.0
        best_away = 0.0
        best_draw = 0.0
        
        for bookmaker in bookmakers:
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'h2h':
                    for outcome in market.get('outcomes', []):
                        if outcome['name'] == home_team:
                            best_home = max(best_home, outcome['price'])
                        elif outcome['name'] == away_team:
                            best_away = max(best_away, outcome['price'])
                        elif outcome['name'].lower() == 'draw':
                            best_draw = max(best_draw, outcome['price'])
        
        if best_home > 0 and best_away > 0:
            # Get H2H sentiment (mock for now if no real one)
            real_sentiment = get_match_sentiment(fixture['id'])
            if real_sentiment:
                sentiment_score = real_sentiment['aggregate_score']
                sample_count = real_sentiment['sample_count']
            else:
                odds_diff = (1.0/best_home) - (1.0/best_away)
                sentiment_score = odds_diff * 0.5
                sample_count = 10
                
            prediction = predictor.predict({
                'market_type': 'h2h',
                'sentiment_score': sentiment_score,
                'home_odds': best_home,
                'away_odds': best_away,
                'draw_odds': best_draw or 3.0,
                'sample_count': sample_count
            })
            
            if prediction['confidence'] >= 0.60:
                res = prediction['predicted_outcome']
                odds = best_home if res == 'home' else best_away if res == 'away' else best_draw
                prob = prediction['confidence'] # Use sentiment-adjusted confidence as prob
                ev = (prob * odds) - 1
                if ev > 0.01:
                    recommendations.append({
                        'market': 'Match Winner',
                        'prediction': res.upper(),
                        'odds': odds,
                        'confidence': prediction['confidence'],
                        'ev': ev,
                        'tier': 1 if ev > 0.1 else 2
                    })

        # 2. Over/Under Analysis (if available)
        best_over = 0.0
        for bookmaker in bookmakers:
            for market in bookmaker.get('markets', []):
                if market.get('key') in ['totals', 'over_under']:
                    for outcome in market.get('outcomes', []):
                        if outcome['name'].lower().startswith('over'):
                            best_over = max(best_over, outcome['price'])
        
        if best_over > 1.1:
            prediction = predictor.predict({
                'market_type': 'totals',
                'sentiment_score': sentiment_score if 'sentiment_score' in locals() else 0.0
            })
            if prediction['confidence'] >= 0.60:
                recommendations.append({
                    'market': 'Over/Under 2.5',
                    'prediction': prediction['predicted_outcome'].upper(),
                    'odds': best_over, # Simplified
                    'confidence': prediction['confidence'],
                    'ev': 0.05, # Conservative estimate
                    'tier': 2
                })

        # Finalize recommendations with fixture info
        results = []
        for rec in recommendations:
            results.append({
                'fixture_id': fixture['id'],
                'league': fixture['league'],
                'home_team': home_team,
                'away_team': away_team,
                'commence_time': fixture['commence_time'],
                **rec
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing fixture: {e}")
        return []


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
            report.append(f"   Market: {rec['market']} | League: {rec['league']}")
            report.append(f"   Prediction: {rec['prediction'].upper()} @ {rec['odds']:.2f}")
            report.append(f"   Confidence: {rec['confidence']:.0%} | EV: {rec['ev']:+.1%}")
            report.append(f"   Time: {rec['commence_time']}")
            report.append("")
    
    if tier2:
        report.append(f"⭐ TIER 2 - HIGH QUALITY ({len(tier2)} opportunities)")
        report.append("-" * 70)
        for i, rec in enumerate(tier2, 1):
            report.append(f"{i}. {rec['home_team']} vs {rec['away_team']}")
            report.append(f"   Market: {rec['market']}")
            report.append(f"   Prediction: {rec['prediction'].upper()} @ {rec['odds']:.2f}")
            report.append(f"   Confidence: {rec['confidence']:.0%} | EV: {rec['ev']:+.1%}")
            report.append("")
    
    if tier3:
        report.append(f"💡 TIER 3 - GOOD QUALITY ({len(tier3)} opportunities)")
        report.append("-" * 70)
        for i, rec in enumerate(tier3, 1):
            report.append(f"{i}. {rec['home_team']} vs {rec['away_team']}")
            report.append(f"   Market: {rec['market']}")
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
        recs = analyze_fixture(fixture, predictor)
        if recs:
            recommendations.extend(recs)
    
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
