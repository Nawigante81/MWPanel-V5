"""
Proxy rotation and anti-detection service.
Manages a pool of proxies with health checks and rotation.
"""
import random
from dataclasses import dataclass
from typing import List, Optional
import asyncio
import aiohttp
from datetime import datetime, timedelta

from app.logging_config import get_logger
from app.settings import settings

logger = get_logger("proxy_manager")


@dataclass
class Proxy:
    """Proxy configuration."""
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    country: str = "PL"
    last_used: Optional[datetime] = None
    fail_count: int = 0
    success_count: int = 0
    is_active: bool = True
    
    @property
    def formatted_url(self) -> str:
        """Format proxy URL with auth."""
        if self.username and self.password:
            protocol = self.url.split("://")[0]
            host = self.url.split("://")[1]
            return f"{protocol}://{self.username}:{self.password}@{host}"
        return self.url
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.fail_count
        if total == 0:
            return 1.0
        return self.success_count / total


class ProxyManager:
    """
    Manages proxy rotation with health checks.
    
    Features:
    - Rotating proxy selection
    - Health monitoring
    - Automatic failover
    - Country-based selection
    """
    
    def __init__(self):
        self.proxies: List[Proxy] = []
        self._current_index = 0
        self._lock = asyncio.Lock()
        self._load_proxies_from_env()
    
    def _load_proxies_from_env(self):
        """Load proxies from environment variable."""
        proxy_list = getattr(settings, 'PROXY_LIST', [])
        
        if isinstance(proxy_list, str):
            # Parse from comma-separated string
            proxy_list = [p.strip() for p in proxy_list.split(',') if p.strip()]
        
        for proxy_url in proxy_list:
            self.proxies.append(Proxy(url=proxy_url))
        
        if self.proxies:
            logger.info(f"Loaded {len(self.proxies)} proxies")
        else:
            logger.warning("No proxies configured, using direct connection")
    
    async def get_proxy(self, source: Optional[str] = None) -> Optional[Proxy]:
        """
        Get next available proxy using round-robin.
        
        Args:
            source: Source name for source-specific proxy selection
        
        Returns:
            Proxy or None if no proxies available
        """
        if not self.proxies:
            return None
        
        async with self._lock:
            # Filter active proxies with good success rate
            active_proxies = [
                p for p in self.proxies 
                if p.is_active and p.success_rate > 0.3
            ]
            
            if not active_proxies:
                # Fallback to any proxy
                active_proxies = self.proxies
            
            # Round-robin selection
            proxy = active_proxies[self._current_index % len(active_proxies)]
            self._current_index = (self._current_index + 1) % len(active_proxies)
            
            proxy.last_used = datetime.utcnow()
            
            return proxy
    
    async def report_success(self, proxy: Proxy):
        """Report successful proxy usage."""
        proxy.success_count += 1
        proxy.fail_count = max(0, proxy.fail_count - 1)
    
    async def report_failure(self, proxy: Proxy):
        """Report failed proxy usage."""
        proxy.fail_count += 1
        
        # Disable proxy after 5 consecutive failures
        if proxy.fail_count >= 5:
            proxy.is_active = False
            logger.warning(f"Disabled proxy due to failures: {proxy.url}")
    
    async def health_check(self) -> dict:
        """Run health check on all proxies."""
        results = {
            "total": len(self.proxies),
            "active": 0,
            "failed": 0,
            "details": []
        }
        
        for proxy in self.proxies:
            is_healthy = await self._check_proxy(proxy)
            
            if is_healthy:
                proxy.is_active = True
                proxy.fail_count = 0
                results["active"] += 1
            else:
                proxy.fail_count += 1
                if proxy.fail_count >= 3:
                    proxy.is_active = False
                results["failed"] += 1
            
            results["details"].append({
                "url": proxy.url,
                "active": proxy.is_active,
                "success_rate": proxy.success_rate,
            })
        
        return results
    
    async def _check_proxy(self, proxy: Proxy) -> bool:
        """Check if proxy is working."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://httpbin.org/ip",
                    proxy=proxy.formatted_url
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.debug(f"Proxy check failed for {proxy.url}: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get proxy statistics."""
        return {
            "total": len(self.proxies),
            "active": sum(1 for p in self.proxies if p.is_active),
            "avg_success_rate": (
                sum(p.success_rate for p in self.proxies) / len(self.proxies)
                if self.proxies else 0
            ),
        }


# Global instance
_proxy_manager: Optional[ProxyManager] = None


def get_proxy_manager() -> ProxyManager:
    """Get or create proxy manager instance."""
    global _proxy_manager
    
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    
    return _proxy_manager
