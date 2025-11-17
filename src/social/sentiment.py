"""Sentiment analysis for social media posts."""
from typing import Dict, Optional

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """Sentiment analysis with pluggable models."""

    def __init__(self, model_name: Optional[str] = None):
        """Initialize sentiment analyzer.

        Args:
            model_name: Model to use (vader, hf-distilbert). Defaults to config.
        """
        self.model_name = model_name or settings.SENTIMENT_MODEL
        self._analyzer = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the sentiment model."""
        if self.model_name == "vader":
            self._initialize_vader()
        elif self.model_name == "hf-distilbert":
            self._initialize_huggingface()
        else:
            logger.warning(f"Unknown sentiment model: {self.model_name}, falling back to vader")
            self.model_name = "vader"
            self._initialize_vader()

    def _initialize_vader(self):
        """Initialize VADER sentiment analyzer."""
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self._analyzer = SentimentIntensityAnalyzer()
            logger.info("VADER sentiment analyzer initialized")
        except ImportError:
            logger.error("vaderSentiment not installed. Install with: pip install vaderSentiment")
            raise

    def _initialize_huggingface(self):
        """Initialize HuggingFace transformer model."""
        try:
            from transformers import pipeline

            self._analyzer = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1,  # CPU
            )
            logger.info("HuggingFace DistilBERT sentiment analyzer initialized")
        except ImportError:
            logger.error("transformers not installed. Install with: pip install transformers torch")
            raise

    def analyze_text(self, text: str) -> Dict[str, any]:
        """Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Dict with keys:
                - score: float (-1.0 to 1.0, negative to positive)
                - label: str (positive, negative, neutral)
                - confidence: float (0.0 to 1.0, model confidence)
                - model: str (model name used)
        """
        if not text or not text.strip():
            return {
                "score": 0.0,
                "label": "neutral",
                "confidence": 0.0,
                "model": self.model_name,
            }

        if self.model_name == "vader":
            return self._analyze_vader(text)
        elif self.model_name == "hf-distilbert":
            return self._analyze_huggingface(text)
        else:
            raise ValueError(f"Unknown model: {self.model_name}")

    def _analyze_vader(self, text: str) -> Dict[str, any]:
        """Analyze with VADER.

        Returns:
            Sentiment dict with score, label, confidence, model
        """
        scores = self._analyzer.polarity_scores(text)
        compound = scores["compound"]

        # Determine label based on compound score
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        # Confidence is the absolute value of compound score
        confidence = abs(compound)

        return {
            "score": compound,  # -1.0 to 1.0
            "label": label,
            "confidence": confidence,
            "model": "vader",
            "raw_scores": scores,  # Include pos, neg, neu for debugging
        }

    def _analyze_huggingface(self, text: str) -> Dict[str, any]:
        """Analyze with HuggingFace model.

        Returns:
            Sentiment dict with score, label, confidence, model
        """
        # Truncate text to model's max length
        text = text[:512]

        result = self._analyzer(text)[0]
        hf_label = result["label"].lower()  # POSITIVE, NEGATIVE
        hf_score = result["score"]  # Confidence

        # Map to our format
        if hf_label == "positive":
            score = hf_score  # 0.5 to 1.0
            label = "positive"
        elif hf_label == "negative":
            score = -hf_score  # -1.0 to -0.5
            label = "negative"
        else:
            score = 0.0
            label = "neutral"

        return {
            "score": score,
            "label": label,
            "confidence": hf_score,
            "model": "hf-distilbert",
        }


# Global analyzer instance (lazy-loaded)
_analyzer: Optional[SentimentAnalyzer] = None


def get_analyzer() -> SentimentAnalyzer:
    """Get or create global sentiment analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer


def analyze_text(text: str) -> Dict[str, any]:
    """Convenience function to analyze text sentiment.

    Args:
        text: Text to analyze

    Returns:
        Sentiment dict with score, label, confidence, model
    """
    analyzer = get_analyzer()
    return analyzer.analyze_text(text)
