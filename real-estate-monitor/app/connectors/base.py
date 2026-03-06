"""
Base connector interface for all real estate sources.
All connectors must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass

from app.schemas import OfferNormalized


@dataclass
class FilterConfig:
    """Configuration for scraping filters."""
    region: Optional[str] = None
    city: Optional[str] = None
    property_type: Optional[str] = None  # apartment, house, land, etc.
    transaction_type: str = "sale"  # sale, rent
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_area: Optional[int] = None
    max_area: Optional[int] = None
    rooms: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            k: v for k, v in {
                "region": self.region,
                "city": self.city,
                "property_type": self.property_type,
                "transaction_type": self.transaction_type,
                "min_price": self.min_price,
                "max_price": self.max_price,
                "min_area": self.min_area,
                "max_area": self.max_area,
                "rooms": self.rooms,
            }.items() if v is not None
        }


class BaseConnector(ABC):
    """
    Base class for all real estate source connectors.
    
    Implementations must provide:
    - Source name identification
    - URL building for filters
    - Offer extraction from pages
    - Data normalization
    """
    
    # Override in subclasses
    name: str = "base"
    base_url: str = ""
    fetch_mode: str = "playwright"  # or "http"
    
    # User agent pool for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    
    def __init__(self):
        self._current_ua_index = 0
    
    @property
    def user_agent(self) -> str:
        """Get next user agent from rotation."""
        ua = self.USER_AGENTS[self._current_ua_index]
        self._current_ua_index = (self._current_ua_index + 1) % len(self.USER_AGENTS)
        return ua
    
    @abstractmethod
    def build_search_url(self, filter_config: FilterConfig) -> str:
        """
        Build search URL from filter configuration.
        
        Args:
            filter_config: Search filters
        
        Returns:
            Complete search URL
        """
        pass
    
    @abstractmethod
    async def extract_offers(self, page_content: str) -> List[OfferNormalized]:
        """
        Extract offers from page content.
        
        Args:
            page_content: HTML or JSON content of the page
        
        Returns:
            List of normalized offers
        """
        pass
    
    @abstractmethod
    def canonicalize_url(self, url: str) -> str:
        """
        Convert URL to canonical form for deduplication.
        
        Args:
            url: Raw URL from the source
        
        Returns:
            Canonical URL suitable for fingerprinting
        """
        pass
    
    async def fetch_with_playwright(
        self,
        url: str,
        context=None,
    ) -> str:
        """
        Fetch page content using Playwright.
        
        Args:
            url: URL to fetch
            context: Optional Playwright browser context
        
        Returns:
            Page HTML content
        """
        # Implementation in specific connectors
        raise NotImplementedError("Subclasses must implement fetch_with_playwright")
    
    async def fetch_with_http(self, url: str) -> str:
        """
        Fetch page content using HTTP client.
        
        Args:
            url: URL to fetch
        
        Returns:
            Page content
        """
        import httpx
        
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
        }
        
        async with httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    
    def normalize_offer(self, raw_data: Dict) -> OfferNormalized:
        """
        Normalize raw offer data to standard format.
        
        Args:
            raw_data: Raw extracted data
        
        Returns:
            Normalized offer
        """
        from app.services.normalize import (
            PriceNormalizer,
            AreaNormalizer,
            RoomsNormalizer,
            LocationNormalizer,
            CoordinateNormalizer,
        )
        
        # Extract price and currency
        price, currency = PriceNormalizer.normalize(raw_data.get("price_text"))
        
        # Extract area
        area = AreaNormalizer.normalize(raw_data.get("area_text"))
        
        # Extract rooms
        rooms = RoomsNormalizer.normalize(raw_data.get("rooms_text"))
        
        # Extract location
        city, region = LocationNormalizer.extract_city_region(
            raw_data.get("location_text")
        )
        
        # Normalize coordinates
        lat, lng = CoordinateNormalizer.normalize(
            raw_data.get("lat"),
            raw_data.get("lng"),
        )

        source_created_at = (
            raw_data.get("source_created_at")
            or raw_data.get("published_at")
            or raw_data.get("publishedAt")
            or raw_data.get("created_at")
            or raw_data.get("createdAt")
            or raw_data.get("date_published")
            or raw_data.get("datePublished")
            or raw_data.get("listing_date")
        )
        
        return OfferNormalized(
            source=self.name,
            url=raw_data.get("url", ""),
            title=raw_data.get("title", ""),
            price=price,
            currency=currency,
            city=city,
            region=region,
            area_m2=area,
            rooms=rooms,
            lat=lat,
            lng=lng,
            raw_json=raw_data,
            source_created_at=source_created_at,
        )


class ConnectorRegistry:
    """Registry for managing all available connectors."""
    
    _connectors: Dict[str, BaseConnector] = {}
    
    @classmethod
    def register(cls, connector_class: type) -> type:
        """Decorator to register a connector class."""
        instance = connector_class()
        cls._connectors[instance.name] = instance
        return connector_class
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseConnector]:
        """Get connector by name."""
        return cls._connectors.get(name)
    
    @classmethod
    def list_connectors(cls) -> List[str]:
        """List all registered connector names."""
        return list(cls._connectors.keys())
    
    @classmethod
    def get_all(cls) -> Dict[str, BaseConnector]:
        """Get all registered connectors."""
        return cls._connectors.copy()


def register_connector(connector_class: type) -> type:
    """Decorator to register a connector."""
    return ConnectorRegistry.register(connector_class)
