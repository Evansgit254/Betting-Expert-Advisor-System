"""Alert system for operator notifications."""
import logging
import os

import requests

logger = logging.getLogger(__name__)


def send_alert(message: str, level: str = "warning"):
    """Send alert to operator (supports Telegram, logs as fallback)."""

    logger.warning("ALERT (%s): %s", level, message)
    # Telegram config via env
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        try:
            telegram_api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": f"[BettingExpert][{level.upper()}]\n{message}"}
            resp = requests.post(telegram_api, data=payload, timeout=10)
            if not resp.ok:
                logger.warning("Telegram alert failed: %s", resp.text)
        except Exception as e:
            logger.warning("Telegram alert exception: %s", e)
