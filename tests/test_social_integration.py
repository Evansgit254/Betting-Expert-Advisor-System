"""Integration tests for social signals module."""
import pytest
from datetime import datetime, timedelta

from src.social.sentiment import analyze_text
from src.social.matcher import link_post_to_fixture
from src.social.aggregator import (
    calculate_recency_weight,
    calculate_author_influence,
    aggregate_match_sentiment,
)
from src.social.arbitrage import detect_arbitrage


class TestSentimentAnalysis:
    """Test sentiment analysis."""
    
    def test_positive_sentiment(self):
        """Test positive sentiment detection."""
        result = analyze_text("This team is playing amazing! Great performance!")
        assert result["label"] == "positive"
        assert result["score"] > 0
    
    def test_negative_sentiment(self):
        """Test negative sentiment detection."""
        result = analyze_text("Terrible performance, worst game ever")
        assert result["label"] == "negative"
        assert result["score"] < 0
    
    def test_neutral_sentiment(self):
        """Test neutral sentiment detection."""
        result = analyze_text("The match starts at 3pm")
        assert result["label"] == "neutral"
        assert -0.1 <= result["score"] <= 0.1


class TestPostMatching:
    """Test post to fixture matching."""
    
    def test_link_post_to_fixture(self):
        """Test linking post to fixture."""
        post = {
            "text": "Manchester United vs Liverpool is going to be epic!",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        
        fixtures = [
            {
                "id": "match_123",
                "home_team": "Manchester United",
                "away_team": "Liverpool",
                "commence_time": (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z",
            }
        ]
        
        result = link_post_to_fixture(post, fixtures)
        assert result is not None
        match_id, confidence = result
        assert match_id == "match_123"
        assert confidence > 0.5


class TestAggregation:
    """Test sentiment aggregation."""
    
    def test_recency_weight(self):
        """Test recency weight calculation."""
        # Recent post should have high weight
        weight_recent = calculate_recency_weight(1.0)  # 1 hour old
        assert weight_recent > 0.9
        
        # Old post should have low weight
        weight_old = calculate_recency_weight(24.0)  # 24 hours old
        assert weight_old < 0.1
    
    def test_author_influence(self):
        """Test author influence calculation."""
        # High engagement
        influence = calculate_author_influence("user1", {"like_count": 150, "retweet_count": 50})
        assert influence > 1.0
        
        # Low engagement
        influence = calculate_author_influence("user2", {"like_count": 5, "retweet_count": 0})
        assert influence == 1.0


class TestArbitrage:
    """Test arbitrage detection."""
    
    def test_no_arbitrage(self):
        """Test normal odds with no arbitrage."""
        odds_data = [
            {"bookmaker": "Bet365", "selection": "home", "odds": 2.0},
            {"bookmaker": "Bet365", "selection": "away", "odds": 2.0},
        ]
        
        result = detect_arbitrage(odds_data)
        assert result is None or not result["is_arbitrage"]
    
    def test_arbitrage_detected(self):
        """Test arbitrage opportunity detection."""
        odds_data = [
            {"bookmaker": "Bet365", "selection": "home", "odds": 2.2},
            {"bookmaker": "Pinnacle", "selection": "away", "odds": 2.2},
        ]
        
        result = detect_arbitrage(odds_data)
        assert result is not None
        assert result["is_arbitrage"]
        assert result["profit_margin"] > 0
    



class TestEndToEnd:
    """End-to-end integration tests."""
    
    def test_full_pipeline_mock(self):
        """Test full pipeline with mock data."""
        # This would test the complete flow:
        # 1. Scrape posts (mocked)
        # 2. Analyze sentiment
        # 3. Match to fixtures
        # 4. Aggregate sentiment
        # 5. Generate suggestions
        
        # Mock post
        post = {
            "id": "post_123",
            "source": "twitter",
            "text": "Manchester United looking strong today! #MUFC",
            "author": "fan123",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        
        # Analyze sentiment
        sentiment = analyze_text(post["text"])
        assert sentiment["label"] in ["positive", "negative", "neutral"]
        
        # Mock fixture
        fixture = {
            "id": "match_123",
            "home_team": "Manchester United",
            "away_team": "Liverpool",
            "commence_time": (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z",
        }
        
        # Match post to fixture
        result = link_post_to_fixture(post, [fixture])
        assert result is not None
        match_id, confidence = result
        assert match_id == "match_123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
