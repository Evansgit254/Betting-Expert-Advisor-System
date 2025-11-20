"""ML-powered betting suggestion engine."""
from datetime import datetime
from typing import List, Dict, Any
from src.logging_config import get_logger
from .schemas import BettingSuggestion

logger = get_logger(__name__)

class SuggestionEngine:
    """Generates ML-powered betting suggestions."""
    
    def generate_suggestions(self, fixtures: List[Dict[str, Any]], min_confidence: float = 0.6, limit: int = 20) -> List[BettingSuggestion]:
        suggestions = []
        
        for fixture in fixtures:
            try:
                ml_confidence = fixture.get('ml_confidence', 0)
                ev_score = fixture.get('ev_score', 0)
                
                if ml_confidence < min_confidence or ev_score < 0:
                    continue
                
                predicted_outcome = fixture.get('predicted_outcome', 'home')
                
                if predicted_outcome == 'home':
                    odds = fixture.get('home_odds', 2.0)
                elif predicted_outcome == 'away':
                    odds = fixture.get('away_odds', 2.0)
                else:
                    odds = fixture.get('draw_odds', 3.0)
                
                ml_probs = {
                    'home': fixture.get('ml_home_prob', 0.33),
                    'away': fixture.get('ml_away_prob', 0.33),
                    'draw': fixture.get('ml_draw_prob', 0.34)
                }
                
                arb_index = fixture.get('arbitrage_profit', 0.0) / 100.0
                risk_score = self._calculate_risk_score(fixture)
                strategy_alignment = self._calculate_strategy_alignment(fixture)
                
                confidence_factors = self._get_confidence_factors(fixture)
                risk_factors = self._get_risk_factors(fixture)
                reason = self._generate_reason(fixture, predicted_outcome, ml_confidence, ev_score)
                
                suggestion = BettingSuggestion(
                    fixture_id=fixture.get('id', ''),
                    home_team=fixture.get('home_team', 'Unknown'),
                    away_team=fixture.get('away_team', 'Unknown'),
                    league=fixture.get('league', 'Unknown'),
                    commence_time=fixture.get('commence_time', datetime.now()),
                    suggested_selection=predicted_outcome,
                    suggested_odds=odds,
                    ml_confidence=ml_confidence,
                    ml_probabilities=ml_probs,
                    ev_score=ev_score,
                    sentiment_score=fixture.get('sentiment_score'),
                    arbitrage_index=arb_index,
                    risk_score=risk_score,
                    strategy_alignment=strategy_alignment,
                    reason=reason,
                    confidence_factors=confidence_factors,
                    risk_factors=risk_factors
                )
                
                suggestions.append(suggestion)
                
            except Exception as e:
                logger.error(f"Error generating suggestion for {fixture.get('id')}: {e}")
                continue
        
        suggestions.sort(key=lambda x: (x.ev_score * x.ml_confidence), reverse=True)
        
        logger.info(f"Generated {len(suggestions[:limit])} betting suggestions")
        return suggestions[:limit]
    
    def _calculate_risk_score(self, fixture: Dict[str, Any]) -> float:
        volatility = fixture.get('volatility_index', 0.5)
        confidence = fixture.get('ml_confidence', 0.5)
        return volatility * (1 - confidence)
    
    def _calculate_strategy_alignment(self, fixture: Dict[str, Any]) -> float:
        ev_score = fixture.get('ev_score', 0)
        confidence = fixture.get('ml_confidence', 0)
        sentiment = abs(fixture.get('sentiment_score', 0))
        
        alignment = (ev_score * 0.4) + (confidence * 0.4) + (sentiment * 0.2)
        return min(max(alignment, 0.0), 1.0)
    
    def _get_confidence_factors(self, fixture: Dict[str, Any]) -> List[str]:
        factors = []
        
        if fixture.get('ml_confidence', 0) > 0.8:
            factors.append('high_ml_confidence')
        if fixture.get('ev_score', 0) > 0.1:
            factors.append('positive_expected_value')
        if abs(fixture.get('sentiment_score', 0)) > 0.3:
            factors.append('strong_sentiment_signal')
        if fixture.get('arbitrage_opportunity', False):
            factors.append('arbitrage_detected')
        if fixture.get('sharp_money_indicator', False):
            factors.append('sharp_money_movement')
        
        return factors
    
    def _get_risk_factors(self, fixture: Dict[str, Any]) -> List[str]:
        factors = []
        
        if fixture.get('volatility_index', 0) > 0.5:
            factors.append('high_volatility')
        if fixture.get('risk_category') == 'high':
            factors.append('high_risk_category')
        if fixture.get('sentiment_sample_count', 0) < 10:
            factors.append('low_sentiment_sample')
        if fixture.get('market_efficiency', 1.0) < 0.7:
            factors.append('inefficient_market')
        
        return factors
    
    def _generate_reason(self, fixture: Dict[str, Any], outcome: str, confidence: float, ev: float) -> str:
        parts = [f"ML model predicts {outcome} with {confidence*100:.0f}% confidence"]
        
        if ev > 0.1:
            parts.append(f"EV: +{ev*100:.1f}%")
        
        sentiment = fixture.get('sentiment_score', 0)
        if abs(sentiment) > 0.3:
            direction = "positive" if sentiment > 0 else "negative"
            parts.append(f"{direction} sentiment")
        
        if fixture.get('arbitrage_opportunity', False):
            parts.append(f"arbitrage opportunity")
        
        return ". ".join(parts) + "."
