
import os
import json
import redis
from typing import Optional
from src.logging_config import get_logger

logger = get_logger(__name__)

class SafetyManager:
    """Manages system safety features including the Emergency Kill Switch."""

    def __init__(self, redis_host: str = "redis", redis_port: int = 6379, backup_file: str = "data/safety_state.json"):
        self.redis_client = None
        self.backup_file = backup_file
        self.kill_switch_key = "safety:kill_switch"
        
        # Initialize Redis
        try:
            self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
            self.redis_client.ping()
            logger.info("SafetyManager connected to Redis")
        except Exception as e:
            logger.warning(f"SafetyManager could not connect to Redis: {e}. Using local file only.")

        # Ensure backup directory exists
        os.makedirs(os.path.dirname(self.backup_file), exist_ok=True)

    def activate_kill_switch(self, reason: str = "Manual activation") -> bool:
        """Activate the kill switch to stop all betting."""
        try:
            # 1. Update Redis
            if self.redis_client:
                self.redis_client.set(self.kill_switch_key, "true")
            
            # 2. Update Backup File
            self._save_local_state(active=True, reason=reason)
            
            logger.warning(f"🚨 KILL SWITCH ACTIVATED: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to activate kill switch: {e}")
            return False

    def deactivate_kill_switch(self, reason: str = "Manual resumption") -> bool:
        """Deactivate the kill switch to resume betting."""
        try:
            # 1. Update Redis
            if self.redis_client:
                self.redis_client.set(self.kill_switch_key, "false")
            
            # 2. Update Backup File
            self._save_local_state(active=False, reason=reason)
            
            logger.info(f"✅ Kill switch deactivated: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate kill switch: {e}")
            return False

    def is_kill_switch_active(self) -> bool:
        """Check if the kill switch is currently active."""
        # Priority 1: Redis
        if self.redis_client:
            try:
                val = self.redis_client.get(self.kill_switch_key)
                if val is not None:
                    return val.lower() == "true"
            except Exception as e:
                logger.error(f"Redis error checking kill switch: {e}")

        # Priority 2: Local File
        return self._load_local_state()

    def _save_local_state(self, active: bool, reason: str):
        """Save state to local JSON file."""
        try:
            data = {"kill_switch_active": active, "last_reason": reason}
            with open(self.backup_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save local safety state: {e}")

    def _load_local_state(self) -> bool:
        """Load state from local JSON file."""
        try:
            if os.path.exists(self.backup_file):
                with open(self.backup_file, "r") as f:
                    data = json.load(f)
                    return data.get("kill_switch_active", False)
        except Exception as e:
            logger.error(f"Failed to load local safety state: {e}")
        return False
