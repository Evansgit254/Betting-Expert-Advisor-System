"""Notification services."""
from .telegram import send_message, send_odds_alert, send_daily_report, send_alert

__all__ = ['send_message', 'send_odds_alert', 'send_daily_report', 'send_alert']
