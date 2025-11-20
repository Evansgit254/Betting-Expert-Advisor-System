"""API routes for analytics and dashboard."""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime, timedelta
from src.analytics.stats import analytics
from src.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard() -> Dict[str, Any]:
    """Get complete dashboard data."""
    try:
        data = analytics.get_dashboard_data()
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities")
async def get_current_opportunities() -> Dict[str, Any]:
    """Get current betting opportunities."""
    try:
        recommendations = analytics.load_recent_recommendations(days=1)
        
        # Sort by tier and confidence
        recommendations.sort(key=lambda x: (x['tier'], -x['confidence']))
        
        return {
            "success": True,
            "count": len(recommendations),
            "opportunities": recommendations,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get statistics summary."""
    try:
        stats = analytics.calculate_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error calculating stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance(days: int = 30) -> Dict[str, Any]:
    """Get performance metrics."""
    try:
        results = analytics.load_results(days=days)
        
        if not results:
            return {
                "success": True,
                "message": "No results available yet",
                "performance": {
                    "win_rate": 0,
                    "roi": 0,
                    "profit_loss": 0,
                    "total_bets": 0
                }
            }
        
        total_bets = len(results)
        wins = len([r for r in results if r['won']])
        total_stake = sum(r['stake'] for r in results)
        total_profit = sum(r['profit_loss'] for r in results)
        
        return {
            "success": True,
            "performance": {
                "win_rate": wins / total_bets if total_bets > 0 else 0,
                "roi": total_profit / total_stake if total_stake > 0 else 0,
                "profit_loss": total_profit,
                "total_bets": total_bets,
                "total_wins": wins,
                "total_losses": total_bets - wins,
                "avg_odds": sum(r['odds'] for r in results) / total_bets,
                "period_days": days
            },
            "results": results
        }
    except Exception as e:
        logger.error(f"Error fetching performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
async def get_trends(days: int = 30) -> Dict[str, Any]:
    """Get trend data for charts."""
    try:
        results = analytics.load_results(days=days)
        recommendations = analytics.load_recent_recommendations(days=days)
        
        # Daily profit trend
        daily_profit = {}
        for result in results:
            date = result['timestamp'][:10]
            daily_profit[date] = daily_profit.get(date, 0) + result['profit_loss']
        
        # Daily opportunities trend
        daily_opps = {}
        for rec in recommendations:
            date = rec['saved_at'][:10]
            daily_opps[date] = daily_opps.get(date, 0) + 1
        
        # Confidence distribution
        confidence_buckets = {
            '60-70%': 0,
            '70-80%': 0,
            '80-90%': 0,
            '90-100%': 0
        }
        
        for rec in recommendations:
            conf = rec['confidence']
            if conf < 0.7:
                confidence_buckets['60-70%'] += 1
            elif conf < 0.8:
                confidence_buckets['70-80%'] += 1
            elif conf < 0.9:
                confidence_buckets['80-90%'] += 1
            else:
                confidence_buckets['90-100%'] += 1
        
        return {
            "success": True,
            "trends": {
                "daily_profit": [
                    {"date": date, "profit": profit}
                    for date, profit in sorted(daily_profit.items())
                ],
                "daily_opportunities": [
                    {"date": date, "count": count}
                    for date, count in sorted(daily_opps.items())
                ],
                "confidence_distribution": confidence_buckets,
                "tier_distribution": {
                    "tier1": len([r for r in recommendations if r['tier'] == 1]),
                    "tier2": len([r for r in recommendations if r['tier'] == 2]),
                    "tier3": len([r for r in recommendations if r['tier'] == 3])
                }
            }
        }
    except Exception as e:
        logger.error(f"Error fetching trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/result")
async def save_result(
    fixture_id: str,
    actual_outcome: str,
    predicted_outcome: str,
    odds: float,
    stake: float = 0
) -> Dict[str, Any]:
    """Save a bet result."""
    try:
        analytics.save_result(fixture_id, actual_outcome, predicted_outcome, odds, stake)
        return {
            "success": True,
            "message": "Result saved successfully"
        }
    except Exception as e:
        logger.error(f"Error saving result: {e}")
        raise HTTPException(status_code=500, detail=str(e))
