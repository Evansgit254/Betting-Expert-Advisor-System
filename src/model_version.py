"""Model versioning and backup management."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict

from src.logging_config import get_logger

logger = get_logger(__name__)

MODELS_DIR = Path("./models")
BACKUPS_DIR = MODELS_DIR / "backups"
VERSION_METADATA_FILE = BACKUPS_DIR / "versions.json"


class ModelVersionManager:
    """Manage model versions, backups, and rollbacks."""
    
    def __init__(self):
        """Initialize version manager."""
        # Ensure directories exist
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load version history
        self.versions = self._load_versions()
    
    def _load_versions(self) -> List[Dict]:
        """Load version metadata from file."""
        if VERSION_METADATA_FILE.exists():
            try:
                with open(VERSION_METADATA_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load version metadata: {e}")
                return []
        return []
    
    def _save_versions(self):
        """Save version metadata to file."""
        try:
            with open(VERSION_METADATA_FILE, 'w') as f:
                json.dump(self.versions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save version metadata: {e}")
    
    def backup_current_model(
        self,
        model_type: str = "ensemble",
        metrics: Optional[Dict] = None
    ) -> str:
        """Backup current model before replacing it.
        
        Args:
            model_type: Type of model ('ensemble' or 'random_forest')
            metrics: Performance metrics (accuracy, precision, recall)
            
        Returns:
            Version ID (timestamp-based)
        """
        timestamp = datetime.now(timezone.utc)
        version_id = timestamp.strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Backing up current {model_type} model as version {version_id}")
        
        # Create version directory
        version_dir = BACKUPS_DIR / version_id
        version_dir.mkdir(exist_ok=True)
        
        # Backup based on model type
        if model_type == "ensemble":
            ensemble_dir = MODELS_DIR / "ensemble"
            if ensemble_dir.exists():
                backup_ensemble_dir = version_dir / "ensemble"
                shutil.copytree(ensemble_dir, backup_ensemble_dir, dirs_exist_ok=True)
                logger.info(f"Backed up ensemble models to {backup_ensemble_dir}")
        
        elif model_type == "random_forest":
            model_file = MODELS_DIR / "model.pkl"
            if model_file.exists():
                shutil.copy2(model_file, version_dir / "model.pkl")
                logger.info(f"Backed up RandomForest to {version_dir / 'model.pkl'}")
        
        # Save version metadata
        version_metadata = {
            "version_id": version_id,
            "timestamp": timestamp.isoformat(),
            "model_type": model_type,
            "metrics": metrics or {},
            "backed_up_from": "current"
        }
        
        with open(version_dir / "metadata.json", 'w') as f:
            json.dump(version_metadata, f, indent=2)
        
        # Add to version history
        self.versions.append(version_metadata)
        self._save_versions()
        
        return version_id
    
    def restore_version(self, version_id: str) -> bool:
        """Restore a previous model version.
        
        Args:
            version_id: Version ID to restore
            
        Returns:
            True if successful
        """
        version_dir = BACKUPS_DIR / version_id
        
        if not version_dir.exists():
            logger.error(f"Version {version_id} not found")
            return False
        
        # Load version metadata
        metadata_file = version_dir / "metadata.json"
        if not metadata_file.exists():
            logger.error(f"Version metadata not found for {version_id}")
            return False
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        model_type = metadata.get("model_type", "ensemble")
        
        logger.info(f"Restoring {model_type} model from version {version_id}")
        
        # Restore based on model type
        if model_type == "ensemble":
            backup_ensemble_dir = version_dir / "ensemble"
            if backup_ensemble_dir.exists():
                ensemble_dir = MODELS_DIR / "ensemble"
                # Backup current before restoring
                if ensemble_dir.exists():
                    self.backup_current_model("ensemble", {"note": "pre-rollback backup"})
                    shutil.rmtree(ensemble_dir)
                shutil.copytree(backup_ensemble_dir, ensemble_dir)
                logger.info(f"Restored ensemble from {version_id}")
        
        elif model_type == "random_forest":
            backup_model = version_dir / "model.pkl"
            if backup_model.exists():
                current_model = MODELS_DIR / "model.pkl"
                if current_model.exists():
                    self.backup_current_model("random_forest", {"note": "pre-rollback backup"})
                shutil.copy2(backup_model, current_model)
                logger.info(f"Restored RandomForest from {version_id}")
        
        return True
    
    def list_versions(self) -> List[Dict]:
        """List all available model versions.
        
        Returns:
            List of version metadata dicts
        """
        return self.versions
    
    def cleanup_old_versions(self, retention_days: int = 30):
        """Remove old backups beyond retention period.
        
        Args:
            retention_days: Keep backups for this many days
        """
        cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
        
        versions_to_keep = []
        for version in self.versions:
            version_time = datetime.fromisoformat(version["timestamp"]).timestamp()
            
            if version_time >= cutoff:
                versions_to_keep.append(version)
            else:
                # Remove old version directory
                version_dir = BACKUPS_DIR / version["version_id"]
                if version_dir.exists():
                    shutil.rmtree(version_dir)
                    logger.info(f"Removed old backup: {version['version_id']}")
        
        self.versions = versions_to_keep
        self._save_versions()
        
        logger.info(f"Cleaned up old versions. Kept {len(versions_to_keep)} recent backups.")
    
    def get_latest_version(self) -> Optional[Dict]:
        """Get the most recent model version.
        
        Returns:
            Latest version metadata or None
        """
        if not self.versions:
            return None
        return self.versions[-1]
