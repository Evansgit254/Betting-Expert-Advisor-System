"""ML-powered predictions for social signals."""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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
        features['odds_favorite'] = 1.0 if features['home_odds'] < features['away_odds'] else 0.0
        features['odds_spread'] = abs(features['home_odds'] - features['away_odds'])
        
        # Interaction features
        features['sentiment_x_volume'] = features['sentiment_score'] * np.log1p(features['sample_count'])
        features['sentiment_x_odds'] = features['sentiment_score'] * (1.0 / features['home_odds'])
        
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
        """Predict match outcome using ML model.
        
        Args:
            match_data: Match data with sentiment and odds
            
        Returns:
            Dict with predictions and probabilities
        """
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
            'features_used': len(features)
        }
        
        logger.info(f"ML Prediction: {predicted_outcome} (confidence: {result['confidence']:.2%})")
        
        return result
    
    def _fallback_prediction(self, match_data: Dict) -> Dict[str, float]:
        """Fallback to rule-based prediction if ML model not available."""
        sentiment = match_data.get('sentiment_score', 0.0)
        
        if sentiment > 0.3:
            outcome = 'home'
            confidence = 0.6 + (sentiment * 0.2)
        elif sentiment < -0.3:
            outcome = 'away'
            confidence = 0.6 + (abs(sentiment) * 0.2)
        else:
            outcome = 'draw'
            confidence = 0.5
        
        return {
            'predicted_outcome': outcome,
            'confidence': min(confidence, 0.95),
            'probabilities': {'home': 0.33, 'draw': 0.34, 'away': 0.33},
            'model': 'rule_based_fallback',
            'features_used': 1
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
