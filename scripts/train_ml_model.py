#!/usr/bin/env python3
"""Train ML model for social signals predictions."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.social.ml_predictor import SocialMLPredictor
from src.logging_config import get_logger

logger = get_logger(__name__)

# Sample historical data for initial training
# In production, this would come from your database of past matches
HISTORICAL_MATCHES = [
    # Home wins (positive sentiment, home odds lower)
    {'sentiment_score': 0.65, 'positive_pct': 70, 'negative_pct': 20, 'neutral_pct': 10, 'sample_count': 150, 'home_odds': 1.8, 'away_odds': 2.5, 'draw_odds': 3.2, 'outcome': 'home'},
    {'sentiment_score': 0.55, 'positive_pct': 65, 'negative_pct': 25, 'neutral_pct': 10, 'sample_count': 120, 'home_odds': 1.9, 'away_odds': 2.3, 'draw_odds': 3.0, 'outcome': 'home'},
    {'sentiment_score': 0.45, 'positive_pct': 60, 'negative_pct': 30, 'neutral_pct': 10, 'sample_count': 100, 'home_odds': 2.0, 'away_odds': 2.2, 'draw_odds': 3.1, 'outcome': 'home'},
    {'sentiment_score': 0.70, 'positive_pct': 75, 'negative_pct': 15, 'neutral_pct': 10, 'sample_count': 180, 'home_odds': 1.7, 'away_odds': 2.8, 'draw_odds': 3.5, 'outcome': 'home'},
    {'sentiment_score': 0.50, 'positive_pct': 62, 'negative_pct': 28, 'neutral_pct': 10, 'sample_count': 110, 'home_odds': 1.95, 'away_odds': 2.4, 'draw_odds': 3.0, 'outcome': 'home'},
    {'sentiment_score': 0.60, 'positive_pct': 68, 'negative_pct': 22, 'neutral_pct': 10, 'sample_count': 140, 'home_odds': 1.85, 'away_odds': 2.6, 'draw_odds': 3.3, 'outcome': 'home'},
    {'sentiment_score': 0.40, 'positive_pct': 58, 'negative_pct': 32, 'neutral_pct': 10, 'sample_count': 95, 'home_odds': 2.1, 'away_odds': 2.1, 'draw_odds': 2.9, 'outcome': 'home'},
    {'sentiment_score': 0.75, 'positive_pct': 78, 'negative_pct': 12, 'neutral_pct': 10, 'sample_count': 200, 'home_odds': 1.6, 'away_odds': 3.0, 'draw_odds': 3.8, 'outcome': 'home'},
    
    # Away wins (negative sentiment, away odds lower)
    {'sentiment_score': -0.55, 'positive_pct': 25, 'negative_pct': 65, 'neutral_pct': 10, 'sample_count': 130, 'home_odds': 2.6, 'away_odds': 1.9, 'draw_odds': 3.1, 'outcome': 'away'},
    {'sentiment_score': -0.45, 'positive_pct': 30, 'negative_pct': 60, 'neutral_pct': 10, 'sample_count': 110, 'home_odds': 2.4, 'away_odds': 2.0, 'draw_odds': 3.0, 'outcome': 'away'},
    {'sentiment_score': -0.65, 'positive_pct': 20, 'negative_pct': 70, 'neutral_pct': 10, 'sample_count': 160, 'home_odds': 2.8, 'away_odds': 1.8, 'draw_odds': 3.3, 'outcome': 'away'},
    {'sentiment_score': -0.50, 'positive_pct': 28, 'negative_pct': 62, 'neutral_pct': 10, 'sample_count': 120, 'home_odds': 2.5, 'away_odds': 1.95, 'draw_odds': 3.0, 'outcome': 'away'},
    {'sentiment_score': -0.40, 'positive_pct': 32, 'negative_pct': 58, 'neutral_pct': 10, 'sample_count': 100, 'home_odds': 2.3, 'away_odds': 2.1, 'draw_odds': 2.9, 'outcome': 'away'},
    {'sentiment_score': -0.70, 'positive_pct': 18, 'negative_pct': 72, 'neutral_pct': 10, 'sample_count': 180, 'home_odds': 3.0, 'away_odds': 1.7, 'draw_odds': 3.5, 'outcome': 'away'},
    {'sentiment_score': -0.60, 'positive_pct': 22, 'negative_pct': 68, 'neutral_pct': 10, 'sample_count': 150, 'home_odds': 2.7, 'away_odds': 1.85, 'draw_odds': 3.2, 'outcome': 'away'},
    
    # Draws (neutral sentiment, similar odds)
    {'sentiment_score': 0.05, 'positive_pct': 40, 'negative_pct': 45, 'neutral_pct': 15, 'sample_count': 80, 'home_odds': 2.2, 'away_odds': 2.3, 'draw_odds': 2.8, 'outcome': 'draw'},
    {'sentiment_score': -0.05, 'positive_pct': 38, 'negative_pct': 42, 'neutral_pct': 20, 'sample_count': 75, 'home_odds': 2.3, 'away_odds': 2.2, 'draw_odds': 2.9, 'outcome': 'draw'},
    {'sentiment_score': 0.10, 'positive_pct': 42, 'negative_pct': 43, 'neutral_pct': 15, 'sample_count': 85, 'home_odds': 2.1, 'away_odds': 2.4, 'draw_odds': 2.7, 'outcome': 'draw'},
    {'sentiment_score': 0.00, 'positive_pct': 40, 'negative_pct': 40, 'neutral_pct': 20, 'sample_count': 70, 'home_odds': 2.2, 'away_odds': 2.2, 'draw_odds': 2.8, 'outcome': 'draw'},
    {'sentiment_score': -0.10, 'positive_pct': 35, 'negative_pct': 45, 'neutral_pct': 20, 'sample_count': 65, 'home_odds': 2.4, 'away_odds': 2.1, 'draw_odds': 2.9, 'outcome': 'draw'},
    {'sentiment_score': 0.08, 'positive_pct': 41, 'negative_pct': 44, 'neutral_pct': 15, 'sample_count': 78, 'home_odds': 2.2, 'away_odds': 2.3, 'draw_odds': 2.8, 'outcome': 'draw'},
    
    # More varied examples
    {'sentiment_score': 0.35, 'positive_pct': 55, 'negative_pct': 35, 'neutral_pct': 10, 'sample_count': 90, 'home_odds': 2.0, 'away_odds': 2.3, 'draw_odds': 3.0, 'outcome': 'home'},
    {'sentiment_score': -0.35, 'positive_pct': 35, 'negative_pct': 55, 'neutral_pct': 10, 'sample_count': 95, 'home_odds': 2.4, 'away_odds': 2.0, 'draw_odds': 3.0, 'outcome': 'away'},
    {'sentiment_score': 0.15, 'positive_pct': 45, 'negative_pct': 40, 'neutral_pct': 15, 'sample_count': 82, 'home_odds': 2.1, 'away_odds': 2.2, 'draw_odds': 2.9, 'outcome': 'draw'},
    {'sentiment_score': 0.80, 'positive_pct': 82, 'negative_pct': 10, 'neutral_pct': 8, 'sample_count': 220, 'home_odds': 1.5, 'away_odds': 3.5, 'draw_odds': 4.0, 'outcome': 'home'},
    {'sentiment_score': -0.75, 'positive_pct': 15, 'negative_pct': 75, 'neutral_pct': 10, 'sample_count': 190, 'home_odds': 3.2, 'away_odds': 1.6, 'draw_odds': 3.6, 'outcome': 'away'},
]


def main():
    """Train the ML model."""
    print("=" * 70)
    print("  ML Model Training - Social Signals Predictor")
    print("=" * 70)
    print()
    
    print(f"📊 Training data: {len(HISTORICAL_MATCHES)} historical matches")
    print()
    
    # Count outcomes
    outcomes = {}
    for match in HISTORICAL_MATCHES:
        outcome = match['outcome']
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    
    print("Distribution:")
    for outcome, count in outcomes.items():
        print(f"  {outcome.capitalize()}: {count} ({count/len(HISTORICAL_MATCHES)*100:.1f}%)")
    print()
    
    # Initialize predictor
    predictor = SocialMLPredictor()
    
    # Train model
    print("🤖 Training ML model...")
    print()
    predictor.train(HISTORICAL_MATCHES, test_size=0.25)
    
    print()
    print("=" * 70)
    print("✅ Model training complete!")
    print("=" * 70)
    print()
    print("The ML model is now ready to use.")
    print("All API endpoints will use ML predictions automatically.")
    print()
    print("Test the model:")
    print("  curl http://localhost:5000/social/suggestions")
    print()
    print("To retrain with more data:")
    print("  python scripts/train_ml_model.py")
    print()


if __name__ == "__main__":
    main()
