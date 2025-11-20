"""Sentiment analysis using lightweight NLP."""
import re
from typing import Dict, List

from src.logging_config import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """Lightweight sentiment analyzer using keyword-based approach.
    
    For production, replace with transformer model like:
    - cardiffnlp/twitter-roberta-base-sentiment-latest
    - distilbert-base-uncased-finetuned-sst-2-english
    """
    
    def __init__(self):
        # Positive keywords
        self.positive_keywords = {
            'strong', 'excellent', 'great', 'good', 'win', 'winning', 'confident',
            'solid', 'impressive', 'dominant', 'fire', 'unstoppable', 'momentum',
            'form', 'quality', 'clinical', 'sharp', 'ready', 'motivated',
        }
        
        # Negative keywords
        self.negative_keywords = {
            'weak', 'poor', 'bad', 'lose', 'losing', 'worried', 'concern',
            'injury', 'injured', 'doubt', 'struggle', 'struggling', 'crisis',
            'problem', 'issue', 'missing', 'suspended', 'tired', 'exhausted',
        }
        
        # Neutral keywords
        self.neutral_keywords = {
            'match', 'game', 'play', 'team', 'player', 'season', 'league',
        }
        
        logger.info("SentimentAnalyzer initialized (keyword-based)")
    
    def analyze_text(self, text: str) -> Dict:
        """Analyze sentiment of text.
        
        Returns:
            {
                'score': float (-1.0 to 1.0),
                'label': str (positive/negative/neutral),
                'keywords': List[str]
            }
        """
        text_lower = text.lower()
        
        # Extract keywords
        words = re.findall(r'\b\w+\b', text_lower)
        
        # Count sentiment words
        positive_count = sum(1 for word in words if word in self.positive_keywords)
        negative_count = sum(1 for word in words if word in self.negative_keywords)
        
        # Calculate score
        total_sentiment_words = positive_count + negative_count
        if total_sentiment_words == 0:
            score = 0.0
            label = 'neutral'
        else:
            score = (positive_count - negative_count) / total_sentiment_words
            if score > 0.2:
                label = 'positive'
            elif score < -0.2:
                label = 'negative'
            else:
                label = 'neutral'
        
        # Extract relevant keywords
        keywords = [
            word for word in words
            if word in self.positive_keywords or word in self.negative_keywords
        ]
        
        return {
            'score': score,
            'label': label,
            'keywords': keywords[:10],  # Limit to 10 keywords
        }
    
    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """Analyze multiple texts."""
        return [self.analyze_text(text) for text in texts]


# For production, use transformer-based model:
"""
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class TransformerSentimentAnalyzer:
    def __init__(self, model_name="cardiffnlp/twitter-roberta-base-sentiment-latest"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()
    
    def analyze_text(self, text: str) -> Dict:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            scores = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        # Map to sentiment
        labels = ['negative', 'neutral', 'positive']
        scores_dict = {labels[i]: scores[0][i].item() for i in range(3)}
        
        predicted_label = labels[torch.argmax(scores).item()]
        score = scores_dict['positive'] - scores_dict['negative']
        
        return {
            'score': score,
            'label': predicted_label,
            'confidence': max(scores_dict.values()),
            'keywords': []  # Extract with NER if needed
        }
"""
