#!/usr/bin/env python3
"""Train ensemble ML models for betting predictions."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from src.model_ensemble import EnsembleModel
from src.logging_config import get_logger
from src.feature import build_features

logger = get_logger(__name__)


def generate_synthetic_data(n_samples=1000):
    """Generate synthetic training data for demonstration.
    
    In production, this would load real historical match data.
    """
    np.random.seed(42)
    
    data = []
    for _ in range(n_samples):
        # Generate odds (lower odds = higher implied probability)
        home_odds = np.random.uniform(1.5, 4.0)
        away_odds = np.random.uniform(1.5, 4.0)
        draw_odds = np.random.uniform(2.5, 4.5)
        
        # Calculate implied probabilities
        total_prob = 1/home_odds + 1/away_odds + 1/draw_odds
        prob_home = (1/home_odds) / total_prob
        prob_away = (1/away_odds) / total_prob
        prob_draw = (1/draw_odds) / total_prob
        
        # Generate outcome based on probabilities
        outcome = np.random.choice(['home', 'draw', 'away'], p=[prob_home, prob_draw, prob_away])
        
        # Add noise to features to simulate real-world variance
        data.append({
            'home_odds': home_odds + np.random.normal(0, 0.1),
            'away_odds': away_odds + np.random.normal(0, 0.1),
            'draw_odds': draw_odds + np.random.normal(0, 0.1),
            'prob_home': prob_home + np.random.normal(0, 0.05),
            'prob_away': prob_away + np.random.normal(0, 0.05),
            'prob_draw': prob_draw + np.random.normal(0, 0.05),
            'home_form': np.random.uniform(0, 1),
            'away_form': np.random.uniform(0, 1),
            'h2h_home_wins': np.random.randint(0, 5),
            'outcome': outcome
        })
    
    return pd.DataFrame(data)


def main():
    """Train the ensemble model."""
    print("=" * 70)
    print("  Ensemble Model Training - LightGBM + XGBoost + Neural Network")
    print("=" * 70)
    print()
    
    # Generate or load training data
    print("📊 Loading training data...")
    df = generate_synthetic_data(n_samples=5000)
    
    print(f"   Samples: {len(df)}")
    print(f"   Features: {df.columns.tolist()}")
    print()
    
    # Prepare features and labels
    feature_cols = [col for col in df.columns if col != 'outcome']
    X = df[feature_cols].values
    
    # Encode labels: home=0, draw=1, away=2
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df['outcome'])
    
    print("Class distribution:")
    for i, label in enumerate(label_encoder.classes_):
        count = (y == i).sum()
        print(f"  {label.capitalize()}: {count} ({count/len(y)*100:.1f}%)")
    print()
    
    # Initialize and train ensemble
    print("🤖 Training ensemble models...")
    print("   This may take several minutes...")
    print()
    
    ensemble = EnsembleModel(
        weights={'lgb': 0.33, 'xgb': 0.33, 'nn': 0.34}
    )
    
    ensemble.train(X, y, verbose=True)
    
    print()
    print("=" * 70)
    print("✅ Ensemble model training complete!")
    print("=" * 70)
    print()
    print("Models saved to: models/ensemble/")
    print("  - lgb_model.txt")
    print("  - xgb_model.json")
    print("  - nn_model.keras")
    print("  - metadata.pkl")
    print()
    print("The ensemble will automatically be used by the live tracker.")
    print()


if __name__ == "__main__":
    main()
