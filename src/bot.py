
import time
import threading
import requests
from src.logging_config import get_logger
from src.safety import SafetyManager
from src.config import settings

logger = get_logger(__name__)

class TelegramBot:
    """Telegram Bot for handling admin commands."""
    
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.safety_manager = SafetyManager()
        self.last_update_id = None
        self.running = False
        self.thread = None

    def start(self):
        """Start the bot in a background thread."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram Bot not started: Missing token or chat_id")
            return

        self.running = True
        self.thread = threading.Thread(target=self._poll_updates, daemon=True)
        self.thread.start()
        logger.info("Telegram Bot started")

    def stop(self):
        """Stop the bot."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _poll_updates(self):
        """Poll for updates from Telegram API."""
        while self.running:
            try:
                params = {"timeout": 10}
                if self.last_update_id:
                    params["offset"] = self.last_update_id + 1
                
                resp = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    for result in data.get("result", []):
                        self.last_update_id = result["update_id"]
                        self._handle_message(result.get("message", {}))
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                time.sleep(5)

    def _handle_message(self, message):
        """Handle incoming message."""
        text = message.get("text", "").strip().lower()
        chat_id = str(message.get("chat", {}).get("id"))
        
        # Security check: only allow configured chat_id
        if chat_id != str(self.chat_id):
            logger.warning(f"Ignored command from unauthorized chat: {chat_id}")
            return

        if text in ["/stop", "/kill"]:
            self.safety_manager.activate_kill_switch("Telegram Command")
            self._send_message("🚨 System HALTED by Telegram command.")
        elif text in ["/resume", "/start"]:
            self.safety_manager.deactivate_kill_switch("Telegram Command")
            self._send_message("✅ System RESUMED by Telegram command.")
        elif text == "/status":
            is_killed = self.safety_manager.is_kill_switch_active()
            status = "HALTED 🛑" if is_killed else "RUNNING 🟢"
            self._send_message(f"System Status: {status}")

    def _send_message(self, text):
        """Send a reply message."""
        try:
            url = f"{self.base_url}/sendMessage"
            requests.post(url, json={"chat_id": self.chat_id, "text": text})
        except Exception as e:
            logger.error(f"Failed to send Telegram reply: {e}")
