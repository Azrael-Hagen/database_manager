"""Enhanced backup management with multiple paths and automatic scheduling."""

import logging
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class BackupManager:
    """Manage multiple backup paths and automatic scheduling."""
    
    BACKUP_PATHS_KEY = "BACKUP_PATHS"
    ACTIVE_BACKUP_KEY = "ACTIVE_BACKUP_PATH"
    AUTO_BACKUP_ENABLED = "AUTO_BACKUP_ENABLED"
    AUTO_BACKUP_HOUR = "AUTO_BACKUP_HOUR"
    AUTO_BACKUP_RETENTION = "AUTO_BACKUP_RETENTION_DAYS"
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_config(self, key: str) -> Optional[str]:
        """Get configuration value."""
        from app.models import ConfigSistema
        config = self.db.query(ConfigSistema).filter(
            ConfigSistema.clave == key
        ).first()
        return config.valor if config else None
    
    def _set_config(self, key: str, value: str):
        """Set configuration value."""
        from app.models import ConfigSistema
        config = self.db.query(ConfigSistema).filter(
            ConfigSistema.clave == key
        ).first()
        
        if config:
            config.valor = value
        else:
            config = ConfigSistema(clave=key, valor=value)
            self.db.add(config)
        
        self.db.commit()
    
    def add_backup_path(self, path: str, is_active: bool = False) -> bool:
        """
        Add a new backup path.
        
        Returns:
            True if successful
        """
        try:
            # Normalize path
            normalized = Path(path).expanduser().as_posix()
            
            # Create if doesn't exist
            Path(normalized).mkdir(parents=True, exist_ok=True)
            
            # Load existing paths
            paths_json = self._get_config(self.BACKUP_PATHS_KEY) or "[]"
            try:
                paths = json.loads(paths_json)
            except:
                paths = []
            
            # Check if already exists
            if normalized in paths:
                if is_active:
                    self._set_config(self.ACTIVE_BACKUP_KEY, normalized)
                return True
            
            # Add new path
            paths.append(normalized)
            self._set_config(self.BACKUP_PATHS_KEY, json.dumps(paths))
            
            # Set as active if requested or first path
            if is_active or len(paths) == 1:
                self._set_config(self.ACTIVE_BACKUP_KEY, normalized)
            
            logger.info(f"Added backup path: {normalized}")
            return True
        
        except Exception as e:
            logger.error(f"Error adding backup path: {e}")
            return False
    
    def remove_backup_path(self, path: str, remove_files: bool = False) -> bool:
        """
        Remove a backup path.
        
        Args:
            path: Path to remove
            remove_files: Also delete backup files
        
        Returns:
            True if successful
        """
        try:
            normalized = Path(path).expanduser().as_posix()
            
            # Load paths
            paths_json = self._get_config(self.BACKUP_PATHS_KEY) or "[]"
            paths = json.loads(paths_json)
            
            if normalized not in paths:
                return False
            
            # Remove from list
            paths.remove(normalized)
            self._set_config(self.BACKUP_PATHS_KEY, json.dumps(paths))
            
            # Update active path if needed
            active = self._get_config(self.ACTIVE_BACKUP_KEY)
            if active == normalized and paths:
                self._set_config(self.ACTIVE_BACKUP_KEY, paths[0])
            
            # Delete files if requested
            if remove_files:
                try:
                    shutil.rmtree(normalized)
                except:
                    pass
            
            logger.info(f"Removed backup path: {normalized}")
            return True
        
        except Exception as e:
            logger.error(f"Error removing backup path: {e}")
            return False
    
    def get_backup_paths(self) -> List[Dict]:
        """Get all configured backup paths with their info."""
        try:
            paths_json = self._get_config(self.BACKUP_PATHS_KEY) or "[]"
            paths = json.loads(paths_json)
            active = self._get_config(self.ACTIVE_BACKUP_KEY)
            
            result = []
            for p in paths:
                path_obj = Path(p)
                result.append({
                    "path": p,
                    "is_active": p == active,
                    "exists": path_obj.exists(),
                    "file_count": len(list(path_obj.glob("*.sql"))) if path_obj.exists() else 0,
                })
            
            return result
        
        except Exception as e:
            logger.error(f"Error getting backup paths: {e}")
            return []
    
    def set_active_path(self, path: str) -> bool:
        """Set the active backup path."""
        try:
            normalized = Path(path).expanduser().as_posix()
            
            # Verify it exists in paths
            paths_json = self._get_config(self.BACKUP_PATHS_KEY) or "[]"
            paths = json.loads(paths_json)
            
            if normalized not in paths:
                return False
            
            self._set_config(self.ACTIVE_BACKUP_KEY, normalized)
            logger.info(f"Set active backup path: {normalized}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting active backup path: {e}")
            return False
    
    def get_active_path(self) -> Optional[str]:
        """Get the currently active backup path."""
        return self._get_config(self.ACTIVE_BACKUP_KEY)
    
    def enable_auto_backup(self, hour: int = 2, retention_days: int = 30) -> bool:
        """
        Enable automatic daily backups.
        
        Args:
            hour: Hour of day to backup (0-23)
            retention_days: Days to keep backups
        
        Returns:
            True if successful
        """
        try:
            if hour < 0 or hour > 23:
                return False
            
            self._set_config(self.AUTO_BACKUP_ENABLED, "true")
            self._set_config(self.AUTO_BACKUP_HOUR, str(hour))
            self._set_config(self.AUTO_BACKUP_RETENTION, str(retention_days))
            
            logger.info(f"Enabled auto-backup at {hour:02d}:00 with {retention_days} day retention")
            return True
        
        except Exception as e:
            logger.error(f"Error enabling auto-backup: {e}")
            return False
    
    def disable_auto_backup(self) -> bool:
        """Disable automatic backups."""
        try:
            self._set_config(self.AUTO_BACKUP_ENABLED, "false")
            logger.info("Disabled auto-backup")
            return True
        except Exception as e:
            logger.error(f"Error disabling auto-backup: {e}")
            return False
    
    def get_auto_backup_config(self) -> Dict:
        """Get auto-backup configuration."""
        enabled = self._get_config(self.AUTO_BACKUP_ENABLED) == "true"
        hour = int(self._get_config(self.AUTO_BACKUP_HOUR) or "2")
        retention = int(self._get_config(self.AUTO_BACKUP_RETENTION) or "30")
        
        return {
            "enabled": enabled,
            "hour": hour,
            "retention_days": retention,
        }
    
    def cleanup_old_backups(self, days: int = 30, path: Optional[str] = None) -> Dict:
        """
        Remove backups older than N days.
        
        Returns:
            Dict with counts: {deleted, errors}
        """
        try:
            backup_path = path or self.get_active_path()
            if not backup_path:
                return {"deleted": 0, "errors": 1}
            
            backup_dir = Path(backup_path)
            if not backup_dir.exists():
                return {"deleted": 0, "errors": 1}
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            deleted = 0
            errors = 0
            
            for backup_file in backup_dir.glob("*.sql"):
                try:
                    timestamp = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if timestamp < cutoff_date:
                        backup_file.unlink()
                        deleted += 1
                        logger.info(f"Deleted old backup: {backup_file.name}")
                except Exception as e:
                    logger.error(f"Error deleting backup {backup_file}: {e}")
                    errors += 1
            
            return {"deleted": deleted, "errors": errors}
        
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            return {"deleted": 0, "errors": 1}
