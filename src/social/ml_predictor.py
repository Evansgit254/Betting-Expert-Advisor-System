"""ML-powered predictions for social signals."""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import joblib
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

from src.logging_config import get_logger
from src.db import handle_db_errors
from src.social.models import SocialPost, SocialSentiment, SentimentAggregate, SuggestedBet

logger = get_logger(__name__)

MODEL_DIR = Path("./models/social")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class SocialMLPredictor:
    """ML-powered predictor using social signals and sentiment data."""
    
    def __init__(self, model_path: Path = MODEL_DIR / "social_predictor.pkl"):
        """Initialize ML predictor."""
        self.model_path = model_path
        self.model = None
        self.feature_names = []
        
    def extract_features(self, match_data: Dict) -> Dict[str, float]:
        """Extract ML features from match data.
        
        Features include:
        - Sentiment scores (aggregate, positive%, negative%)
        - Post volume and recency
        - Author influence metrics
        - Odds-based features
        - Time-based features
        """
        features = {}
        
        # Sentiment features
        features['sentiment_score'] = match_data.get('sentiment_score', 0.0)
        features['positive_pct'] = match_data.get('positive_pct', 0.0)
        features['negative_pct'] = match_data.get('negative_pct', 0.0)
        features['neutral_pct'] = match_data.get('neutral_pct', 0.0)
        features['sample_count'] = match_data.get('sample_count', 0)
        
        # Volume features
        features['posts_per_hour'] = match_data.get('sample_count', 0) / 24.0
        features['sentiment_volatility'] = abs(features['positive_pct'] - features['negative_pct'])
        
        # Odds features (if available)
        features['home_odds'] = match_data.get('home_odds', 2.0)
        features['away_odds'] = match_data.get('away_odds', 2.0)
        features['draw_odds'] = match_data.get('draw_odds', 3.0)
        
        # Derived features
        features['sentiment_strength'] = abs(features['sentiment_score'])
        features['sentiment_confidence'] = max(features['positive_pct'], features['negative_pct'])
        
        # Symmetrical favorite flags
        features['home_favorite'] = 1.0 if features['home_odds'] < features['away_odds'] else 0.0
        features['away_favorite'] = 1.0 if features['away_odds'] < features['home_odds'] else 0.0
        features['odds_spread'] = abs(features['home_odds'] - features['away_odds'])
        
        # Interaction features (Symmetric)
        features['sentiment_x_volume'] = features['sentiment_score'] * np.log1p(features['sample_count'])
        features['sentiment_x_home_odds'] = features['sentiment_score'] * (1.0 / features['home_odds'])
        features['sentiment_x_away_odds'] = -features['sentiment_score'] * (1.0 / features['away_odds'])
        
        return features
    
    def prepare_training_data(self, historical_matches: List[Dict]) -> tuple:
        """Prepare training data from historical matches.
        
        Args:
            historical_matches: List of dicts with match data and outcomes
            
        Returns:
            X (features), y (labels)
        """
        X_list = []
        y_list = []
        
        for match in historical_matches:
            features = self.extract_features(match)
            X_list.append(list(features.values()))
            
            # Label: 0=away win, 1=draw, 2=home win
            outcome = match.get('outcome', 'unknown')
            if outcome == 'home':
                y_list.append(2)
            elif outcome == 'draw':
                y_list.append(1)
            elif outcome == 'away':
                y_list.append(0)
            else:
                continue  # Skip unknown outcomes
        
        self.feature_names = list(features.keys())
        X = np.array(X_list)
        y = np.array(y_list)
        
        return X, y
    
    def train(self, historical_matches: List[Dict], test_size: float = 0.2):
        """Train the ML model on historical data.
        
        Args:
            historical_matches: List of historical match data with outcomes
            test_size: Fraction of data to use for testing
        """
        logger.info(f"Training ML model on {len(historical_matches)} historical matches")
        
        # Prepare data
        X, y = self.prepare_training_data(historical_matches)
        
        if len(X) < 10:
            logger.warning("Not enough training data (need at least 10 samples)")
            return
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Train model (using Gradient Boosting for better performance)
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"Model trained! Test accuracy: {accuracy:.2%}")
        logger.info(f"Classification report:\n{classification_report(y_test, y_pred, target_names=['Away', 'Draw', 'Home'])}")
        
        # Feature importance
        importances = self.model.feature_importances_
        feature_importance = sorted(
            zip(self.feature_names, importances),
            key=lambda x: x[1],
            reverse=True
        )
        logger.info("Top 5 important features:")
        for feat, imp in feature_importance[:5]:
            logger.info(f"  {feat}: {imp:.4f}")
        
        # Save model
        self.save_model()
    
    def predict(self, match_data: Dict) -> Dict[str, float]:
        """Predict match outcome using ML model."""
        market_type = match_data.get('market_type', 'h2h')
        
        if market_type != 'h2h':
            # Currently ML model is only trained for h2h
            # Fallback to specialized logic for other markets
            return self._fallback_prediction(match_data)

        if self.model is None:
            logger.warning("Model not trained, loading from disk...")
            self.load_model()
            
            if self.model is None:
                logger.error("No trained model available")
                return self._fallback_prediction(match_data)
        
        # Extract features
        features = self.extract_features(match_data)
        X = np.array([list(features.values())])
        
        # Predict
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        
        # Map to outcomes
        outcomes = ['away', 'draw', 'home']
        predicted_outcome = outcomes[prediction]
        
        result = {
            'predicted_outcome': predicted_outcome,
            'confidence': float(probabilities[prediction]),
            'probabilities': {
                'home': float(probabilities[2]),
                'draw': float(probabilities[1]),
                'away': float(probabilities[0])
            },
            'model': 'gradient_boosting',
            'features_used': len(features),
            'market_type': 'h2h'
        }
        
        logger.info(f"ML Prediction (H2H): {predicted_outcome} (confidence: {result['confidence']:.2%})")
        return result
    
    def _fallback_prediction(self, match_data: Dict) -> Dict[str, float]:
        """Fallback prediction logic for different market types."""
        market_type = match_data.get('market_type', 'h2h')
        sentiment = match_data.get('sentiment_score', 0.0)
        
        if market_type == 'totals':
            return self._predict_totals(match_data)
        elif market_type == 'corners':
            return self._predict_corners(match_data)
        
        # Default H2H fallback
        home_odds = match_data.get('home_odds', 2.0)
        away_odds = match_data.get('away_odds', 2.0)
        
        home_prob = 1.0 / home_odds if home_odds > 0 else 0.0
        away_prob = 1.0 / away_odds if away_odds > 0 else 0.0
        draw_prob = 1.0 - home_prob - away_prob
        
        if home_prob > 0.5 or (home_prob > away_prob + 0.1):
            outcome = 'home'
            confidence = home_prob + (sentiment * 0.1 if sentiment > 0 else 0)
        elif away_prob > 0.5 or (away_prob > home_prob + 0.1):
            outcome = 'away'
            confidence = away_prob + (abs(sentiment) * 0.1 if sentiment < 0 else 0)
        else:
            if sentiment > 0.1:
                outcome = 'home'
                confidence = 0.5 + (sentiment * 0.2)
            elif sentiment < -0.1:
                outcome = 'away'
                confidence = 0.5 + (abs(sentiment) * 0.2)
            else:
                outcome = 'draw'
                confidence = max(0.34, draw_prob)
        
        return {
            'predicted_outcome': outcome,
            'confidence': min(max(confidence, 0.34), 0.98),
            'probabilities': {'home': home_prob, 'draw': draw_prob, 'away': away_prob},
            'model': 'odds_fallback',
            'market_type': 'h2h'
        }

    def _predict_totals(self, match_data: Dict) -> Dict[str, Any]:
        """Specialized prediction for Over/Under goals."""
        sentiment = match_data.get('sentiment_score', 0.0)
        # Higher positive sentiment often correlates with attacking football/over expectations
        confidence = 0.5 + (abs(sentiment) * 0.3)
        outcome = 'over' if sentiment > 0.1 else 'under' if sentiment < -0.1 else 'over'
        
        return {
            'predicted_outcome': f"{outcome} 2.5",
            'confidence': min(confidence, 0.90),
            'model': 'sentiment_heuristic',
            'market_type': 'totals'
        }

    def _predict_corners(self, match_data: Dict) -> Dict[str, Any]:
        """Specialized prediction for Corner markets."""
        sentiment = match_data.get('sentiment_score', 0.0)
        confidence = 0.5 + (abs(sentiment) * 0.2)
        outcome = 'over' if sentiment > 0.1 else 'under'
        
        return {
            'predicted_outcome': f"{outcome} 9.5",
            'confidence': min(confidence, 0.85),
            'model': 'sentiment_heuristic',
            'market_type': 'corners'
        }
    
    def save_model(self):
        """Save trained model to disk."""
        if self.model is not None:
            joblib.dump({
                'model': self.model,
                'feature_names': self.feature_names
            }, self.model_path)
            logger.info(f"Model saved to {self.model_path}")
    
    def load_model(self):
        """Load trained model from disk."""
        if self.model_path.exists():
            data = joblib.load(self.model_path)
            self.model = data['model']
            self.feature_names = data['feature_names']
            logger.info(f"Model loaded from {self.model_path}")
        else:
            logger.warning(f"No model found at {self.model_path}")


# Global predictor instance
_predictor = None

def get_predictor() -> SocialMLPredictor:
    """Get global ML predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = SocialMLPredictor()
        try:
            _predictor.load_model()
        except Exception as e:
            logger.warning(f"Could not load model: {e}")
    return _predictor
