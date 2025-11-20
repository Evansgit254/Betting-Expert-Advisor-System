"""Tests for Market Intelligence Engine."""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime, timezone

from src.market_intelligence import MarketIntelligenceEngine, get_engine


class TestCompositeScoreCalculation:
    """Test composite score calculation logic."""
    
    def test_composite_score_basic(self):
        """Test basic composite score without sentiment or arbitrage."""
        engine = MarketIntelligenceEngine()
        
        score = engine.calculate_composite_score(
            ml_probability=0.55,
            expected_value=0.155,
            sentiment_score=0.0,
            has_arbitrage=False
        )
        
        # base_score = 0.55 * 0.155 = 0.08525
        # sentiment_boost = 0.0 * 0.15 = 0.0
        # arbitrage_boost = 0.0
        # total = 0.08525
        assert score == pytest.approx(0.0853, abs=0.001)
    
    def test_composite_score_with_sentiment(self):
        """Test composite score with positive sentiment."""
        engine = MarketIntelligenceEngine()
        
        score = engine.calculate_composite_score(
            ml_probability=0.55,
            expected_value=0.155,
            sentiment_score=0.3,  # Positive sentiment
            has_arbitrage=False
        )
        
        # base_score = 0.55 * 0.155 = 0.08525
        # sentiment_boost = 0.3 * 0.15 = 0.045
        # total = 0.08525 + 0.045 = 0.13025
        assert score == pytest.approx(0.1303, abs=0.001)
    
    def test_arbitrage_ranks_highest(self):
        """Test that arbitrage opportunities always rank highest."""
        engine = MarketIntelligenceEngine()
        
        # Regular value bet
        regular_score = engine.calculate_composite_score(
            ml_probability=0.60,
            expected_value=0.20,
            sentiment_score=0.5,
            has_arbitrage=False
        )
        
        # Arbitrage opportunity (low base score but guaranteed profit)
        arbitrage_score = engine.calculate_composite_score(
            ml_probability=0.48,
            expected_value=0.05,
            sentiment_score=0.0,
            has_arbitrage=True,
            arbitrage_profit_margin=0.069  # 6.9% guaranteed profit
        )
        
        # Arbitrage should rank higher due to 10x multiplier
        # arbitrage_boost = 0.069 * 10.0 = 0.69
        assert arbitrage_score > regular_score
        assert arbitrage_score >= 0.6
    
    def test_sentiment_boost_limited(self):
        """Test that sentiment influence is limited to 15%."""
        engine = MarketIntelligenceEngine()
        
        # Maximum sentiment (1.0) should add 0.15 to score
        score_max_sentiment = engine.calculate_composite_score(
            ml_probability=0.50,
            expected_value=0.10,
            sentiment_score=1.0,
            has_arbitrage=False
        )
        
        score_no_sentiment = engine.calculate_composite_score(
            ml_probability=0.50,
            expected_value=0.10,
            sentiment_score=0.0,
            has_arbitrage=False
        )
        
        difference = score_max_sentiment - score_no_sentiment
        assert difference == pytest.approx(0.15, abs=0.001)


class TestMarketIntelligenceEngine:
    """Test Market Intelligence Engine functionality."""
    
    @patch('src.market_intelligence.DataFetcher')
    @patch('src.market_intelligence.MLPipeline')
    def test_generate_suggestions_empty_fixtures(self, mock_ml, mock_fetcher):
        """Test gracefully handles no fixtures."""
        # Mock empty fixtures
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.get_fixtures.return_value = pd.DataFrame()
        mock_fetcher.return_value = mock_fetcher_instance
        
        engine = MarketIntelligenceEngine()
        result = engine.generate_suggestions(max_suggestions=10)
        
        assert result['headline'].startswith('🔥 Real-Time Market Highlights')
        assert result['suggestions'] == []
        assert len(result['suggestions']) == 0
    
    @patch('src.market_intelligence.DataFetcher')
    @patch('src.market_intelligence.MLPipeline')
    @patch('src.market_intelligence.find_value_bets')
    def test_filter_by_league(self, mock_find_bets, mock_ml, mock_fetcher):
        """Test league filtering works correctly."""
        # Mock fixtures
        fixtures_df = pd.DataFrame([
            {'market_id': 'match1', 'home': 'Team A', 'away': 'Team B', 'league': 'Premier League'},
            {'market_id': 'match2', 'home': 'Team C', 'away': 'Team D', 'league': 'La Liga'},
        ])
        
        odds_df = pd.DataFrame([
            {'market_id': 'match1', 'home_odds': 2.10},
            {'market_id': 'match2', 'home_odds': 1.90},
        ])
        
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.get_fixtures.return_value = fixtures_df
        mock_fetcher_instance.get_odds.return_value = odds_df
        mock_fetcher.return_value = mock_fetcher_instance
        
        # Mock value bets
        mock_find_bets.return_value = [
            {'market_id': 'match1', 'odds': 2.10, 'ev': 0.15, 'probability': 0.55, 'stake': 100},
            {'market_id': 'match2', 'odds': 1.90, 'ev': 0.10, 'probability': 0.58, 'stake': 120},
        ]
        
        engine = MarketIntelligenceEngine()
        result = engine.generate_suggestions(
            max_suggestions=10,
            leagues=['Premier League']  # Filter for EPL only
        )
        
        # Should only include match1 (Premier League)
        assert len(result['suggestions']) == 1
        assert result['suggestions'][0]['league'] == 'Premier League'
    
    def test_singleton_pattern(self):
        """Test get_engine returns singleton."""
        engine1 = get_engine()
        engine2 = get_engine()
        
        assert engine1 is engine2


class TestSentimentIntegration:
    """Test sentiment analysis integration."""
    
    @patch('src.market_intelligence.SENTIMENT_AVAILABLE', True)
    @patch('src.market_intelligence.get_match_sentiment')
    def test_sentiment_enrichment(self, mock_get_sentiment):
        """Test sentiment data is properly enriched."""
        mock_get_sentiment.return_value = {
            'aggregate_score': 0.4,
            'post_count': 523
        }
       
        engine = MarketIntelligenceEngine()
        
        sentiment = engine._get_sentiment(
            market_id='match1',
            fixture={'home': 'Team A', 'away': 'Team B'}
        )
        
        assert sentiment['score'] == 0.4
        assert sentiment['label'] == 'positive'
        assert sentiment['post_count'] == 523
        assert sentiment['sentiment_strength'] == 'moderate'
    
    def test_classify_sentiment_strength(self):
        """Test sentiment strength classification."""
        engine = MarketIntelligenceEngine()
        
        assert engine._classify_sentiment_strength(0.7) == 'strong'
        assert engine._classify_sentiment_strength(0.4) == 'moderate'
        assert engine._classify_sentiment_strength(0.15) == 'weak'
        assert engine._classify_sentiment_strength(0.05) == 'neutral'
        assert engine._classify_sentiment_strength(-0.5) == 'moderate'  # Absolute value


class TestArbitrageIntegration:
    """Test arbitrage detection integration."""
    
    @patch('src.market_intelligence.ArbitrageDetector')
    def test_arbitrage_detection(self, mock_detector):
        """Test arbitrage opportunities are properly detected."""
        mock_detector_instance = MagicMock()
        mock_detector_instance.detect_opportunities.return_value = [
            {
                'market_id': 'match1',
                'profit_margin': 0.069,
                'guaranteed_profit': 69.0,
                'total_stake': 1000.0,
                'bookmakers': {'home': 'Bet365', 'away': 'Pinnacle'},
                'best_odds': {'home': 2.10, 'away': 2.20},
                'optimal_stakes': {'home': 511, 'away': 489}
            }
        ]
        mock_detector.return_value = mock_detector_instance
        
        engine = MarketIntelligenceEngine()
        odds_df = pd.DataFrame([
            {'market_id': 'match1', 'bookmaker': 'Bet365', 'home_odds': 2.10},
            {'market_id': 'match1', 'bookmaker': 'Pinnacle', 'away_odds': 2.20},
        ])
        
        arbitrage = engine._check_arbitrage('match1', odds_df)
        
        assert arbitrage is not None
        assert arbitrage['profit_margin'] == 0.069
        assert arbitrage['guaranteed_profit'] == 69.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
