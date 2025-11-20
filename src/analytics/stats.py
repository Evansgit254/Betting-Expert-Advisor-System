"""Analytics and statistics for betting opportunities."""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter
import json
from pathlib import Path


class BettingAnalytics:
    """Analytics engine for betting data."""
    
    def __init__(self, data_dir: str = "data/analytics"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "recommendations_history.jsonl"
        self.results_file = self.data_dir / "bet_results.jsonl"
    
    def save_recommendations(self, recommendations: List[Dict[str, Any]]):
        """Save recommendations to history."""
        timestamp = datetime.now().isoformat()
        
        with open(self.history_file, 'a') as f:
            for rec in recommendations:
                rec['saved_at'] = timestamp
                f.write(json.dumps(rec) + '\n')
    
    def load_recent_recommendations(self, days: int = 7) -> List[Dict[str, Any]]:
        """Load recommendations from last N days."""
        if not self.history_file.exists():
            return []
        
        cutoff = datetime.now() - timedelta(days=days)
        recommendations = []
        
        with open(self.history_file, 'r') as f:
            for line in f:
                rec = json.loads(line)
                saved_at = datetime.fromisoformat(rec['saved_at'])
                if saved_at >= cutoff:
                    recommendations.append(rec)
        
        return recommendations
    
    def save_result(self, fixture_id: str, actual_outcome: str, 
                   predicted_outcome: str, odds: float, stake: float = 0):
        """Save bet result."""
        result = {
            'fixture_id': fixture_id,
            'actual_outcome': actual_outcome,
            'predicted_outcome': predicted_outcome,
            'odds': odds,
            'stake': stake,
            'won': actual_outcome == predicted_outcome,
            'profit_loss': stake * (odds - 1) if actual_outcome == predicted_outcome else -stake,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(self.results_file, 'a') as f:
            f.write(json.dumps(result) + '\n')
    
    def load_results(self, days: int = 30) -> List[Dict[str, Any]]:
        """Load bet results from last N days."""
        if not self.results_file.exists():
            return []
        
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        
        with open(self.results_file, 'r') as f:
            for line in f:
                result = json.loads(line)
                timestamp = datetime.fromisoformat(result['timestamp'])
                if timestamp >= cutoff:
                    results.append(result)
        
        return results
    
    def calculate_stats(self, recommendations: List[Dict[str, Any]] = None,
                       results: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate comprehensive statistics."""
        if recommendations is None:
            recommendations = self.load_recent_recommendations(days=1)
        
        if results is None:
            results = self.load_results(days=30)
        
        stats = {}
        
        # Current opportunities
        stats['total_opportunities'] = len(recommendations)
        stats['tier1_count'] = len([r for r in recommendations if r['tier'] == 1])
        stats['tier2_count'] = len([r for r in recommendations if r['tier'] == 2])
        stats['tier3_count'] = len([r for r in recommendations if r['tier'] == 3])
        
        if recommendations:
            stats['avg_confidence'] = sum(r['confidence'] for r in recommendations) / len(recommendations)
            stats['avg_ev'] = sum(r['expected_value'] for r in recommendations) / len(recommendations)
            stats['avg_odds'] = sum(r['odds'] for r in recommendations) / len(recommendations)
            
            # Top leagues
            league_counter = Counter(r['league'] for r in recommendations)
            stats['top_leagues'] = league_counter.most_common(5)
            
            # Best opportunities
            best = sorted(recommendations, key=lambda x: (x['tier'], -x['confidence']))[:3]
            stats['best_opportunities'] = [
                {
                    'match': f"{r['home_team']} vs {r['away_team']}",
                    'prediction': r['prediction'],
                    'odds': r['odds'],
                    'confidence': r['confidence'],
                    'ev': r['expected_value']
                }
                for r in best
            ]
        else:
            stats['avg_confidence'] = 0
            stats['avg_ev'] = 0
            stats['avg_odds'] = 0
            stats['top_leagues'] = []
            stats['best_opportunities'] = []
        
        # Historical performance
        if results:
            total_bets = len(results)
            wins = len([r for r in results if r['won']])
            stats['win_rate'] = wins / total_bets if total_bets > 0 else 0
            
            total_stake = sum(r['stake'] for r in results)
            total_profit = sum(r['profit_loss'] for r in results)
            stats['roi'] = total_profit / total_stake if total_stake > 0 else 0
            stats['profit_loss'] = total_profit
            stats['total_bets'] = total_bets
            stats['total_wins'] = wins
            stats['total_losses'] = total_bets - wins
            
            # Performance by tier
            tier_stats = {}
            for tier in [1, 2, 3]:
                tier_results = [r for r in results 
                               if any(rec['fixture_id'] == r['fixture_id'] and rec['tier'] == tier 
                                     for rec in self.load_recent_recommendations(days=30))]
                if tier_results:
                    tier_wins = len([r for r in tier_results if r['won']])
                    tier_stats[f'tier{tier}_win_rate'] = tier_wins / len(tier_results)
                else:
                    tier_stats[f'tier{tier}_win_rate'] = 0
            
            stats.update(tier_stats)
            
            # Daily performance trend
            daily_profit = {}
            for result in results:
                date = result['timestamp'][:10]
                daily_profit[date] = daily_profit.get(date, 0) + result['profit_loss']
            
            stats['daily_profit_trend'] = [
                {'date': date, 'profit': profit}
                for date, profit in sorted(daily_profit.items())
            ]
        else:
            stats['win_rate'] = 0
            stats['roi'] = 0
            stats['profit_loss'] = 0
            stats['total_bets'] = 0
            stats['total_wins'] = 0
            stats['total_losses'] = 0
            stats['tier1_win_rate'] = 0
            stats['tier2_win_rate'] = 0
            stats['tier3_win_rate'] = 0
            stats['daily_profit_trend'] = []
        
        # Time-based stats
        stats['last_updated'] = datetime.now().isoformat()
        stats['data_period_days'] = 30
        
        return stats
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all data needed for dashboard."""
        recommendations = self.load_recent_recommendations(days=1)
        results = self.load_results(days=30)
        stats = self.calculate_stats(recommendations, results)
        
        return {
            'stats': stats,
            'current_opportunities': recommendations,
            'recent_results': results[-20:],  # Last 20 results
            'generated_at': datetime.now().isoformat()
        }


# Global instance
analytics = BettingAnalytics()
