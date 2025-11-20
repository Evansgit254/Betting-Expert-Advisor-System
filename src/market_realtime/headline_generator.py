"""Generate real-time market headlines from ML analysis."""
from datetime import datetime
from typing import List, Dict, Any
from collections import Counter
from src.logging_config import get_logger
from .schemas import MarketHeadline

logger = get_logger(__name__)

class HeadlineGenerator:
    """Generates human-readable market headlines from ML analysis."""
    
    def generate_headlines(self, fixtures: List[Dict[str, Any]]) -> List[MarketHeadline]:
        headlines = []
        if not fixtures:
            return headlines
        
        headlines.extend(self._generate_value_headlines(fixtures))
        headlines.extend(self._generate_arbitrage_headlines(fixtures))
        headlines.extend(self._generate_sentiment_headlines(fixtures))
        headlines.extend(self._generate_confidence_headlines(fixtures))
        
        priority_order = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
        headlines.sort(key=lambda x: (priority_order.get(x.priority, 2), -x.confidence))
        
        logger.info(f"Generated {len(headlines)} market headlines")
        return headlines
    
    def _generate_value_headlines(self, fixtures: List[Dict[str, Any]]) -> List[MarketHeadline]:
        headlines = []
        high_ev = [f for f in fixtures if f.get('ev_score', 0) > 0.15]
        
        if len(high_ev) >= 5:
            fixture_ids = [f.get('id', '') for f in high_ev[:10]]
            avg_ev = sum(f.get('ev_score', 0) for f in high_ev) / len(high_ev)
            
            headline = MarketHeadline(
                timestamp=datetime.now(),
                headline=f"⚽ {len(high_ev)} high-value fixtures detected with average EV of {avg_ev*100:.1f}%",
                confidence=min(sum(f.get('ml_confidence', 0) for f in high_ev[:5]) / 5, 1.0),
                drivers=['high_ev', 'ml_confidence'],
                fixtures=fixture_ids,
                priority='high'
            )
            headlines.append(headline)
        
        return headlines
    
    def _generate_arbitrage_headlines(self, fixtures: List[Dict[str, Any]]) -> List[MarketHeadline]:
        headlines = []
        arb_opps = [f for f in fixtures if f.get('arbitrage_opportunity', False)]
        
        if arb_opps:
            fixture_ids = [f.get('id', '') for f in arb_opps[:5]]
            max_profit = max(f.get('arbitrage_profit', 0) for f in arb_opps)
            
            headline = MarketHeadline(
                timestamp=datetime.now(),
                headline=f"💰 {len(arb_opps)} arbitrage opportunities with up to {max_profit:.2f}% profit",
                confidence=1.0,
                drivers=['arbitrage', 'market_inefficiency'],
                fixtures=fixture_ids,
                priority='critical'
            )
            headlines.append(headline)
        
        return headlines
    
    def _generate_sentiment_headlines(self, fixtures: List[Dict[str, Any]]) -> List[MarketHeadline]:
        headlines = []
        sentiment_plays = [f for f in fixtures if abs(f.get('sentiment_score', 0)) > 0.4 and f.get('ml_confidence', 0) > 0.7]
        
        if len(sentiment_plays) >= 3:
            fixture_ids = [f.get('id', '') for f in sentiment_plays[:5]]
            avg_conf = sum(f.get('ml_confidence', 0) for f in sentiment_plays) / len(sentiment_plays)
            
            headline = MarketHeadline(
                timestamp=datetime.now(),
                headline=f"📊 {len(sentiment_plays)} fixtures show strong sentiment-ML alignment",
                confidence=avg_conf,
                drivers=['sentiment', 'ml_alignment'],
                fixtures=fixture_ids,
                priority='normal'
            )
            headlines.append(headline)
        
        return headlines
    
    def _generate_confidence_headlines(self, fixtures: List[Dict[str, Any]]) -> List[MarketHeadline]:
        headlines = []
        high_conf = [f for f in fixtures if f.get('ml_confidence', 0) > 0.9]
        
        if len(high_conf) >= 3:
            fixture_ids = [f.get('id', '') for f in high_conf[:5]]
            
            headline = MarketHeadline(
                timestamp=datetime.now(),
                headline=f"🎯 {len(high_conf)} fixtures with ML confidence above 90%",
                confidence=sum(f.get('ml_confidence', 0) for f in high_conf[:5]) / min(5, len(high_conf)),
                drivers=['ml_confidence', 'strong_signal'],
                fixtures=fixture_ids,
                priority='high'
            )
            headlines.append(headline)
        
        return headlines
