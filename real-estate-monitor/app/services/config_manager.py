"""
Dynamic configuration manager.
Allows runtime changes to source configuration without restart.
"""
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import Source
from app.db import get_sync_session

logger = get_logger("config_manager")


class ConfigManager:
    """
    Manages dynamic configuration changes.
    
    Features:
    - Update source settings
    - Enable/disable sources
    - Change intervals
    - Hot-reload configuration
    """
    
    def __init__(self):
        self._callbacks = []
    
    def update_source(
        self,
        source_name: str,
        **kwargs
    ) -> bool:
        """
        Update source configuration.
        
        Args:
            source_name: Name of the source
            **kwargs: Fields to update (interval_seconds, enabled, rate_limit_rps, etc.)
        
        Returns:
            True if updated successfully
        """
        from app.db import SyncSessionLocal
        
        with SyncSessionLocal() as session:
            source = session.execute(
                select(Source).where(Source.name == source_name)
            ).scalar_one_or_none()
            
            if not source:
                logger.error(f"Source not found: {source_name}")
                return False
            
            # Track changes
            changes = []
            
            if 'interval_seconds' in kwargs:
                old = source.interval_seconds
                source.interval_seconds = kwargs['interval_seconds']
                changes.append(f"interval: {old}s -> {kwargs['interval_seconds']}s")
            
            if 'enabled' in kwargs:
                old = source.enabled
                source.enabled = kwargs['enabled']
                changes.append(f"enabled: {old} -> {kwargs['enabled']}")
            
            if 'rate_limit_rps' in kwargs:
                old = source.rate_limit_rps
                source.rate_limit_rps = kwargs['rate_limit_rps']
                changes.append(f"rate_limit: {old} -> {kwargs['rate_limit_rps']}")
            
            if 'fetch_mode' in kwargs:
                source.fetch_mode = kwargs['fetch_mode']
                changes.append(f"fetch_mode: {kwargs['fetch_mode']}")
            
            session.commit()
            
            logger.info(
                f"Updated source {source_name}",
                extra={"changes": changes}
            )
            
            # Notify callbacks
            self._notify_change(source_name, kwargs)
            
            return True
    
    def enable_source(self, source_name: str) -> bool:
        """Enable a source."""
        return self.update_source(source_name, enabled=True)
    
    def disable_source(self, source_name: str) -> bool:
        """Disable a source."""
        return self.update_source(source_name, enabled=False)
    
    def set_interval(self, source_name: str, seconds: int) -> bool:
        """Set scrape interval for a source."""
        return self.update_source(source_name, interval_seconds=seconds)
    
    def set_rate_limit(self, source_name: str, rps: float) -> bool:
        """Set rate limit for a source."""
        return self.update_source(source_name, rate_limit_rps=rps)
    
    def get_source_config(self, source_name: str) -> Optional[dict]:
        """Get current configuration for a source."""
        from app.db import SyncSessionLocal
        
        with SyncSessionLocal() as session:
            source = session.execute(
                select(Source).where(Source.name == source_name)
            ).scalar_one_or_none()
            
            if not source:
                return None
            
            return {
                "id": str(source.id),
                "name": source.name,
                "enabled": source.enabled,
                "fetch_mode": source.fetch_mode,
                "base_url": source.base_url,
                "interval_seconds": source.interval_seconds,
                "rate_limit_rps": float(source.rate_limit_rps),
                "created_at": source.created_at.isoformat() if source.created_at else None,
            }
    
    def get_all_configs(self) -> Dict[str, dict]:
        """Get configurations for all sources."""
        from app.db import SyncSessionLocal
        
        with SyncSessionLocal() as session:
            sources = session.execute(select(Source)).scalars().all()
            
            return {
                source.name: {
                    "id": str(source.id),
                    "enabled": source.enabled,
                    "interval_seconds": source.interval_seconds,
                    "rate_limit_rps": float(source.rate_limit_rps),
                }
                for source in sources
            }
    
    def register_change_callback(self, callback):
        """Register a callback for configuration changes."""
        self._callbacks.append(callback)
    
    def _notify_change(self, source_name: str, changes: dict):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(source_name, changes)
            except Exception as e:
                logger.error(f"Callback error: {e}")


class ConfigValidator:
    """Validates configuration changes."""
    
    @staticmethod
    def validate_interval(seconds: int) -> tuple[bool, str]:
        """Validate interval value."""
        if seconds < 10:
            return False, "Interval must be at least 10 seconds"
        if seconds > 86400:
            return False, "Interval must be less than 24 hours"
        return True, ""
    
    @staticmethod
    def validate_rate_limit(rps: float) -> tuple[bool, str]:
        """Validate rate limit value."""
        if rps <= 0:
            return False, "Rate limit must be positive"
        if rps > 10:
            return False, "Rate limit must be less than 10 rps"
        return True, ""
    
    @staticmethod
    def validate_source_name(name: str) -> tuple[bool, str]:
        """Validate source name."""
        if not name:
            return False, "Source name is required"
        if len(name) > 100:
            return False, "Source name too long"
        return True, ""


# Global instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create config manager."""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager()
    
    return _config_manager
