"""Live in-play prediction model."""
import numpy as np
from typing import Dict, Optional
from datetime import datetime

from src.logging_config import get_logger

logger = get_logger(__name__)


class LivePredictor:
    """Make predictions during live matches with dynamic adjustments."""
    
    def __init__(self):
        """Initialize live predictor."""
        logger.info("LivePredictor initialized")
    
    def predict_live(
        self,
        match_state: Dict,
        pre_match_probs: Optional[Dict] = None
    ) -> Dict[str, float]:
        """Make live prediction based on current match state.
        
        Args:
            match_state: {
                'score_home': 1,
                'score_away': 0,
                'minute': 65,
                'red_cards_home': 0,
                'red_cards_away': 0,
                'momentum': 0.2  # -1 to 1, positive = home momentum
            }
            pre_match_probs: Pre-match probabilities (if available)
            
        Returns:
            Updated win probabilities
        """
        score_home = match_state.get('score_home', 0)
        score_away = match_state.get('score_away', 0)
        minute = match_state.get('minute', 0)
        red_cards_home = match_state.get('red_cards_home', 0)
        red_cards_away = match_state.get('red_cards_away', 0)
        momentum = match_state.get('momentum', 0.0)
        
        # Time remaining factor (more certain as time progresses)
        time_remaining = max(0, 90 - minute)
        certainty_factor = 1 - (time_remaining / 90)
        
        # Base probabilities from current score
        if score_home > score_away:
            base_home = 0.7 + (0.2 * certainty_factor)
            base_draw = 0.2 - (0.1 * certainty_factor)
            base_away = 0.1 - (0.1 * certainty_factor)
        elif score_away > score_home:
            base_home = 0.1 - (0.1 * certainty_factor)
            base_draw = 0.2 - (0.1 * certainty_factor)
            base_away = 0.7 + (0.2 * certainty_factor)
        else:  #Draw
            base_home = 0.35
            base_draw = 0.35
            base_away = 0.35
        
        # Red card adjustments
        if red_cards_home > red_cards_away:
            # Home disadvantage
            base_home *= 0.6
            base_away *= 1.4
        elif red_cards_away > red_cards_home:
            # Away disadvantage
            base_home *= 1.4
            base_away *= 0.6
        
        # Momentum adjustments (subtle)
        if momentum > 0:
            base_home *= (1 + momentum * 0.1)
            base_away *= (1 - momentum * 0.1)
        else:
            base_home *= (1 + momentum * 0.1)
            base_away *= (1 - momentum * 0.1)
        
        # Normalize
        total = base_home + base_draw + base_away
        prob_home = base_home / total
        prob_draw = base_draw / total
        prob_away = base_away / total
        
        return {
            'home': prob_home,
            'draw': prob_draw,
            'away': prob_away,
            'confidence': certainty_factor,
            'time_remaining': time_remaining
        }
    
    def should_bet_live(
        self,
        prediction: Dict,
        odds: Dict[str, float],
        min_edge: float = 0.10
    ) -> Optional[Dict]:
        """Determine if there's value in live betting.
        
        Args:
            prediction: Live prediction probabilities
            odds: Current live odds
            min_edge: Minimum edge for live betting (10% default, higher than pre-match)
            
        Returns:
            Bet recommendation or None
        """
        for selection in ['home', 'draw', 'away']:
            if selection not in odds:
                continue
            
            prob = prediction[selection]
            market_odds = odds[selection]
            implied_prob = 1 / market_odds
            edge = prob - implied_prob
            
            if edge >= min_edge:
                # Calculate EV
                ev = (prob * market_odds) - 1
                
                # Conservative Kelly for live betting (50% of Kelly)
                kelly_fraction = (prob * market_odds - 1) / (market_odds - 1)
                stake_fraction = max(0, min(kelly_fraction * 0.5, 0.05))  # Max 5% even for live
                
                return {
                    'selection': selection,
                    'odds': market_odds,
                    'probability': prob,
                    'edge': edge,
                    'ev': ev,
                    'stake_fraction': stake_fraction,
                    'confidence': prediction['confidence'],
                    'time_remaining': prediction['time_remaining']
                }
        
        return None
