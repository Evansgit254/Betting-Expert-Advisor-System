"""Telegram notification service for instant alerts."""
import os
import requests
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from src.logging_config import get_logger

logger = get_logger(__name__)

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.warning("Telegram credentials not configured")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text: str, parse_mode: str = 'HTML') -> bool:
    """Send a message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured, skipping notification")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': int(TELEGRAM_CHAT_ID),
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Telegram message sent successfully")
            return True
        else:
            logger.error(f"❌ Telegram error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram message: {e}")
        return False


def send_odds_alert(recommendations: List[Dict[str, Any]]) -> bool:
    """Send instant alert when new odds are generated."""
    if not recommendations:
        return False
    
    # Group by tier
    tier1 = [r for r in recommendations if r['tier'] == 1]
    tier2 = [r for r in recommendations if r['tier'] == 2]
    tier3 = [r for r in recommendations if r['tier'] == 3]
    
    # Build message
    lines = []
    lines.append("🚨 <b>NEW BETTING OPPORTUNITIES DETECTED!</b> 🚨")
    lines.append("")
    lines.append(f"📅 {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    lines.append(f"📊 Total: <b>{len(recommendations)}</b> opportunities")
    lines.append("")
    
    if tier1:
        lines.append(f"🎯 <b>TIER 1 - HIGHEST QUALITY ({len(tier1)})</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        for i, rec in enumerate(tier1[:3], 1):  # Top 3
            lines.append(f"{i}. <b>{rec['home_team']} vs {rec['away_team']}</b>")
            lines.append(f"   🎲 Market: {rec['market']}")
            lines.append(f"   Bet: <b>{rec['prediction'].upper()}</b> @ {rec['odds']:.2f}")
            lines.append(f"   📈 Confidence: {rec['confidence']:.0%} | EV: {rec.get('ev', 0):+.1%}")
            lines.append(f"   ⏰ {rec['commence_time'][:16]}")
            lines.append("")
    
    if tier2:
        lines.append(f"⭐ <b>TIER 2 - HIGH QUALITY ({len(tier2)})</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        for i, rec in enumerate(tier2[:2], 1):  # Top 2
            lines.append(f"{i}. {rec['home_team']} vs {rec['away_team']}")
            lines.append(f"   🎲 {rec['market']}: <b>{rec['prediction'].upper()}</b> @ {rec['odds']:.2f} ({rec['confidence']:.0%})")
            lines.append("")
    
    if tier3 and len(tier1) + len(tier2) < 5:
        lines.append(f"💡 <b>TIER 3 ({len(tier3)} more)</b>")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🌐 View full report on dashboard")
    lines.append("⚡ Updated in real-time")
    
    message = "\n".join(lines)
    return send_message(message)


def send_daily_report(stats: Dict[str, Any]) -> bool:
    """Send comprehensive daily report."""
    lines = []
    lines.append("📊 <b>DAILY BETTING REPORT</b> 📊")
    lines.append("")
    lines.append(f"📅 {datetime.now().strftime('%B %d, %Y')}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # Summary stats
    lines.append("<b>📈 SUMMARY</b>")
    lines.append(f"• Total Opportunities: <b>{stats.get('total_opportunities', 0)}</b>")
    lines.append(f"• Tier 1 (Premium): <b>{stats.get('tier1_count', 0)}</b>")
    lines.append(f"• Tier 2 (High): <b>{stats.get('tier2_count', 0)}</b>")
    lines.append(f"• Tier 3 (Good): <b>{stats.get('tier3_count', 0)}</b>")
    lines.append(f"• Avg Confidence: <b>{stats.get('avg_confidence', 0):.1%}</b>")
    lines.append(f"• Avg Expected Value: <b>{stats.get('avg_ev', 0):+.1%}</b>")
    lines.append("")
    
    # Performance
    if stats.get('win_rate'):
        lines.append("<b>🏆 PERFORMANCE</b>")
        lines.append(f"• Win Rate: <b>{stats.get('win_rate', 0):.1%}</b>")
        lines.append(f"• ROI: <b>{stats.get('roi', 0):+.1%}</b>")
        lines.append(f"• Profit/Loss: <b>${stats.get('profit_loss', 0):,.2f}</b>")
        lines.append("")
    
    # Top leagues
    if stats.get('top_leagues'):
        lines.append("<b>⚽ TOP LEAGUES</b>")
        for league, count in stats['top_leagues'][:3]:
            lines.append(f"• {league}: {count} opportunities")
        lines.append("")
    
    # Best opportunities
    if stats.get('best_opportunities'):
        lines.append("<b>🎯 TOP 3 OPPORTUNITIES TODAY</b>")
        for i, opp in enumerate(stats['best_opportunities'][:3], 1):
            lines.append(f"{i}. {opp['match']}")
            lines.append(f"   {opp['prediction']} @ {opp['odds']:.2f} ({opp['confidence']:.0%})")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🌐 Full analytics on dashboard")
    lines.append("⚡ Real-time updates enabled")
    
    message = "\n".join(lines)
    return send_message(message)


def send_alert(title: str, message: str, emoji: str = "🔔") -> bool:
    """Send a generic alert."""
    text = f"{emoji} <b>{title}</b>\n\n{message}"
    return send_message(text)
