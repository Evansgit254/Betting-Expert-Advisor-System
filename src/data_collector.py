"""Data collection for model retraining."""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from src.logging_config import get_logger

logger = get_logger(__name__)


class DataCollector:
    """Collect historical match results for model training."""
    
    def __init__(self):
        """Initialize data collector."""
        pass
    
    def collect_recent_results(self, days: int = 7) -> pd.DataFrame:
        """Collect match results from the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            DataFrame with match results
        """
        logger.info(f"Collecting match results from last {days} days...")
        
        # For now, generate synthetic data
        # In production, this would call an API to get real results
        results = self._generate_synthetic_results(days)
        
        logger.info(f"Collected {len(results)} match results")
        return results
    
    def _generate_synthetic_results(self, days: int) -> pd.DataFrame:
        """Generate synthetic match results for demonstration.
        
        Args:
            days: Number of days worth of data
            
        Returns:
            DataFrame with synthetic results
        """
        np.random.seed(int(datetime.now().timestamp()) % 100000)
        
        # Generate ~10 matches per day
        num_matches = days * 10
        
        data = []
        for i in range(num_matches):
            # Random teams
            home_team = f"Team {np.random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'])}{np.random.randint(1, 10)}"
            away_team = f"Team {np.random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'])}{np.random.randint(1, 10)}"
            
            # Ensure home != away
            while away_team == home_team:
                away_team = f"Team {np.random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'])}{np.random.randint(1, 10)}"
            
            # Generate odds
            home_odds = np.random.uniform(1.5, 4.0)
            away_odds = np.random.uniform(1.5, 4.0)
            draw_odds = np.random.uniform(2.5, 4.5)
            
            # Calculate implied probabilities
            total_prob = 1/home_odds + 1/away_odds + 1/draw_odds
            prob_home = (1/home_odds) / total_prob
            prob_away = (1/away_odds) / total_prob
            prob_draw = (1/draw_odds) / total_prob
            
            # Generate outcome based on probabilities (+/- variance)
            outcome = np.random.choice(
                ['home', 'draw', 'away'],
                p=[
                    max(0.1, min(0.8, prob_home)),
                    max(0.1, min(0.8, prob_draw)),
                    max(0.1, min(0.8, prob_away))
                ]
            )
            
            # Match date (within last N days)
            days_ago = np.random.randint(0, days)
            match_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
            
            data.append({
                'market_id': f"m_{i}",
                'home': home_team,
                'away': away_team,
                'home_odds': home_odds,
                'away_odds': away_odds,
                'draw_odds': draw_odds,
                'outcome': outcome,
                'match_date': match_date,
                'league': np.random.choice(['EPL', 'La Liga', 'Bundesliga', 'Serie A'])
            })
        
        return pd.DataFrame(data)
    
    def validate_results(self, df: pd.DataFrame) -> bool:
        """Validate collected results data.
        
        Args:
            df: DataFrame with match results
            
        Returns:
            True if valid
        """
        required_cols = ['home', 'away', 'outcome', 'home_odds', 'away_odds', 'draw_odds']
        
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"Missing required column: {col}")
                return False
        
        # Check for valid outcomes
        valid_outcomes = {'home', 'draw', 'away'}
        invalid = df[~df['outcome'].isin(valid_outcomes)]
        if len(invalid) > 0:
            logger.error(f"Found {len(invalid)} matches with invalid outcomes")
            return False
        
        # Check for valid odds
        for odds_col in ['home_odds', 'away_odds', 'draw_odds']:
            if (df[odds_col] < 1.0).any():
                logger.error(f"Found invalid odds in {odds_col}")
                return False
        
        logger.info("Data validation passed")
        return True
    
    def merge_with_existing_data(
        self,
        new_data: pd.DataFrame,
        existing_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Merge new results with existing training data.
        
        Args:
            new_data: New match results
            existing_data: Existing training data
            
        Returns:
            Combined DataFrame
        """
        if existing_data is None or existing_data.empty:
            return new_data
        
        # Combine and remove duplicates
        combined = pd.concat([existing_data, new_data], ignore_index=True)
        
        # Remove duplicates based on market_id if available
        if 'market_id' in combined.columns:
            combined = combined.drop_duplicates(subset=['market_id'], keep='last')
        
        logger.info(f"Merged data: {len(existing_data)} existing + {len(new_data)} new = {len(combined)} total")
        
        return combined
