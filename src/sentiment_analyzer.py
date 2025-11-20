"""Enhanced sentiment analysis for betting predictions."""
import re
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

from src.logging_config import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """Analyze sentiment for teams and matches."""
    
    def __init__(self, model_type: str = 'vader'):
        """Initialize sentiment analyzer.
        
        Args:
            model_type: 'vader' or 'synthetic' (transformer models can be added later)
        """
        self.model_type = model_type
        
        if model_type == 'vader' and VADER_AVAILABLE:
            self.vader = SentimentIntensityAnalyzer()
            logger.info("SentimentAnalyzer initialized with VADER")
        else:
            self.vader = None
            logger.info("SentimentAnalyzer initialized with synthetic mode")
        
        # Domain-specific keywords for sports betting
        self.positive_keywords = {
            'form', 'momentum', 'confident', 'strong', 'winning', 'dominant',
            'impressive', 'clinical', 'solid', 'resilient', 'unstoppable'
        }
        
        self.negative_keywords = {
            'struggling', 'poor', 'weak', 'lose', 'defeat', 'terrible',
            'collapse', 'injury', 'crisis', 'disappointing', 'embarrassing'
        }
    
    def analyze_text(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with sentiment scores (positive, negative, neutral, compound)
        """
        if not text:
            return {
                'positive': 0.0,
                'negative': 0.0,
                'neutral': 1.0,
                'compound': 0.0,
                'confidence': 0.0
            }
        
        if self.vader:
            scores = self.vader.polarity_scores(text)
            # Add confidence based on how decisive the sentiment is
            confidence = abs(scores['compound'])
            scores['confidence'] = confidence
            return scores
        else:
            # Fallback to keyword-based sentiment
            return self._keyword_sentiment(text)
    
    def _keyword_sentiment(self, text: str) -> Dict[str, float]:
        """Simple keyword-based sentiment analysis."""
        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)
        
        pos_count = sum(1 for w in words if w in self.positive_keywords)
        neg_count = sum(1 for w in words if w in self.negative_keywords)
        total = len(words)
        
        if total == 0:
            return {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0, 'compound': 0.0, 'confidence': 0.0}
        
        pos_score = pos_count / total
        neg_score = neg_count / total
        neutral_score = 1.0 - (pos_score + neg_score)
        
        # Compound score: -1 to 1
        compound = (pos_count - neg_count) / max(total, 1)
        compound = max(-1.0, min(1.0, compound))
        
        confidence = abs(compound)
        
        return {
            'positive': pos_score,
            'negative': neg_score,
            'neutral': neutral_score,
            'compound': compound,
            'confidence': confidence
        }
    
    def get_match_sentiment(
        self,
        home_team: str,
        away_team: str,
        synthetic: bool = True
    ) -> Dict[str, float]:
        """Get aggregated sentiment for a match.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            synthetic: Use synthetic data (True) or real sources (False)
            
        Returns:
            Dict with sentiment metrics for both teams
        """
        if synthetic:
            return self._generate_synthetic_sentiment(home_team, away_team)
        
        # Real sentiment would fetch from social media here
        # For now, return neutral
        return {
            'sentiment_home': 0.0,
            'sentiment_away': 0.0,
            'sentiment_differential': 0.0,
            'sentiment_confidence': 0.0,
            'social_volume': 0
        }
    
    def _generate_synthetic_sentiment(
        self,
        home_team: str,
        away_team: str
    ) -> Dict[str, float]:
        """Generate synthetic sentiment for demonstration.
        
        Uses team name hashing for deterministic but realistic sentiment.
        """
        # Use team names to seed random generator (deterministic)
        home_seed = hash(home_team) % 100000
        away_seed = hash(away_team) % 100000
        
        np.random.seed(home_seed)
        home_sentiment = np.random.normal(0.0, 0.3)  # Mean 0, std 0.3
        home_sentiment = max(-1.0, min(1.0, home_sentiment))
        
        np.random.seed(away_seed)
        away_sentiment = np.random.normal(0.0, 0.3)
        away_sentiment = max(-1.0, min(1.0, away_sentiment))
        
        # Sentiment confidence (0 to 1)
        home_confidence = abs(home_sentiment)
        away_confidence = abs(away_sentiment)
        avg_confidence = (home_confidence + away_confidence) / 2
        
        # Social volume (synthetic: 10-1000 mentions)
        np.random.seed(home_seed + away_seed)
        social_volume = int(np.random.uniform(10, 1000))
        
        # Sentiment momentum (recent change)
        np.random.seed(home_seed + 1)
        home_momentum = np.random.normal(0.0, 0.1)
        home_momentum = max(-0.5, min(0.5, home_momentum))
        
        return {
            'sentiment_home': home_sentiment,
            'sentiment_away': away_sentiment,
            'sentiment_differential': home_sentiment - away_sentiment,
            'sentiment_confidence': avg_confidence,
            'social_volume': social_volume,
            'sentiment_momentum_home': home_momentum
        }
    
    def batch_analyze(self, texts: List[str]) -> List[Dict[str, float]]:
        """Analyze multiple texts in batch.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of sentiment scores
        """
        return [self.analyze_text(text) for text in texts]
    
    def aggregate_sentiments(self, sentiments: List[Dict[str, float]]) -> Dict[str, float]:
        """Aggregate multiple sentiment readings.
        
        Args:
            sentiments: List of sentiment dicts
            
        Returns:
            Aggregated sentiment scores
        """
        if not sentiments:
            return {'compound': 0.0, 'confidence': 0.0}
        
        compounds = [s.get('compound', 0.0) for s in sentiments]
        confidences = [s.get('confidence', 0.0) for s in sentiments]
        
        # Weighted average by confidence
        total_confidence = sum(confidences)
        if total_confidence > 0:
            weighted_compound = sum(c * conf for c, conf in zip(compounds, confidences)) / total_confidence
        else:
            weighted_compound = np.mean(compounds)
        
        return {
            'compound': weighted_compound,
            'confidence': np.mean(confidences),
            'volume': len(sentiments)
        }
