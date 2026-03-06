"""
Pydantic v2 schemas for data validation and serialization.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Base Schemas
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# =============================================================================
# Offer Schemas
# =============================================================================

class OfferNormalized(BaseSchema):
    """
    Normalized offer schema - output contract for all connectors.
    Every connector must return data in this format.
    """
    source: str = Field(..., description="Source name (e.g., 'otodom', 'olx')")
    url: str = Field(..., description="Canonical URL of the offer")
    title: str = Field(..., description="Offer title")
    price: Optional[Decimal] = Field(None, description="Price as decimal")
    currency: Optional[str] = Field(None, description="Currency code (e.g., 'PLN')")
    city: Optional[str] = Field(None, description="City name")
    region: Optional[str] = Field(None, description="Region/voivodeship")
    area_m2: Optional[float] = Field(None, description="Property area in square meters")
    rooms: Optional[int] = Field(None, description="Number of rooms")
    lat: Optional[float] = Field(None, description="Latitude")
    lng: Optional[float] = Field(None, description="Longitude")
    raw_json: Optional[Dict[str, Any]] = Field(
        None, description="Raw extracted data for debugging"
    )
    source_created_at: Optional[datetime] = Field(
        None, description="Publication date on source portal"
    )
    
    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v):
        """Normalize price from various formats."""
        if v is None:
            return None
        if isinstance(v, str):
            # Remove currency symbols, spaces, and convert
            cleaned = v.replace(" ", "").replace(",", ".")
            cleaned = "".join(c for c in cleaned if c.isdigit() or c == ".")
            try:
                return Decimal(cleaned) if cleaned else None
            except Exception:
                return None
        return Decimal(str(v)) if v else None
    
    @field_validator("area_m2", mode="before")
    @classmethod
    def normalize_area(cls, v):
        """Normalize area from various formats."""
        if v is None:
            return None
        if isinstance(v, str):
            # Extract number from strings like "45.5 m²"
            cleaned = v.replace(" ", "").replace("m²", "").replace("m2", "")
            cleaned = cleaned.replace(",", ".")
            try:
                return float(cleaned) if cleaned else None
            except Exception:
                return None
        return float(v) if v else None
    
    @field_validator("rooms", mode="before")
    @classmethod
    def normalize_rooms(cls, v):
        """Normalize rooms from various formats."""
        if v is None:
            return None
        if isinstance(v, str):
            # Extract number from strings like "3 pokoje"
            cleaned = "".join(c for c in v if c.isdigit())
            try:
                return int(cleaned) if cleaned else None
            except Exception:
                return None
        return int(v) if v else None

    @field_validator("source_created_at", mode="before")
    @classmethod
    def normalize_source_created_at(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            try:
                return datetime.utcfromtimestamp(v)
            except Exception:
                return None

        text = str(v).strip()
        if not text:
            return None

        lower = text.lower()
        now = datetime.utcnow()
        if "dzis" in lower:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if "wczoraj" in lower:
            d = now - timedelta(days=1)
            return d.replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass

        # dd.mm.yyyy / dd-mm-yyyy / dd/mm/yyyy
        import re
        m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", text)
        if m:
            d, mo, y = m.groups()
            year = int(y)
            if year < 100:
                year += 2000
            try:
                return datetime(year, int(mo), int(d))
            except Exception:
                return None

        return None


class OfferCreate(BaseSchema):
    """Schema for creating a new offer."""
    source_id: UUID
    fingerprint: str
    url: str
    title: str
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    area_m2: Optional[float] = None
    rooms: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    raw_json: Optional[Dict[str, Any]] = None
    source_created_at: Optional[datetime] = None
    imported_at: Optional[datetime] = None


class OfferResponse(BaseSchema):
    """Schema for offer API responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    source_id: UUID
    fingerprint: str
    url: str
    title: str
    price: Optional[Decimal]
    currency: Optional[str]
    city: Optional[str]
    region: Optional[str]
    area_m2: Optional[float]
    rooms: Optional[int]
    lat: Optional[float]
    lng: Optional[float]
    raw_json: Optional[Dict[str, Any]] = None
    source_created_at: Optional[datetime] = None
    imported_at: Optional[datetime] = None
    first_seen: datetime
    last_seen: datetime


class OfferListResponse(BaseSchema):
    """Schema for paginated offer list."""
    items: list[OfferResponse]
    data: list[OfferResponse] = Field(default_factory=list)
    total: int
    page: int = 1
    pages: int = 1
    limit: int
    offset: int
    source: Optional[str] = None
    status: Optional[str] = None


# =============================================================================
# Source Schemas
# =============================================================================

class SourceResponse(BaseSchema):
    """Schema for source API responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    enabled: bool
    fetch_mode: str
    base_url: str
    interval_seconds: int
    rate_limit_rps: Decimal
    created_at: datetime


class SourceCreate(BaseSchema):
    """Schema for creating a new source."""
    name: str
    enabled: bool = True
    fetch_mode: str = "playwright"
    base_url: str
    interval_seconds: int = 60
    rate_limit_rps: float = 1.0


# =============================================================================
# Notification Schemas
# =============================================================================

class NotificationResponse(BaseSchema):
    """Schema for notification API responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    offer_id: UUID
    channel: str
    status: str
    tries: int
    last_error: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]


class NotificationCreate(BaseSchema):
    """Schema for creating a notification."""
    offer_id: UUID
    channel: str = "whatsapp"


# =============================================================================
# Scrape Run Schemas
# =============================================================================

class ScrapeRunResponse(BaseSchema):
    """Schema for scrape run API responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    source_id: UUID
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    error: Optional[str]
    offers_found: int
    offers_new: int


class ScrapeRunCreate(BaseSchema):
    """Schema for creating a scrape run."""
    source_id: UUID
    status: str = "running"


# =============================================================================
# Failure Schemas (for debug panel)
# =============================================================================

class FailureResponse(BaseSchema):
    """Schema for failure API responses."""
    type: str = Field(..., description="Type of failure: 'scrape' or 'notify'")
    id: UUID
    source_id: Optional[UUID] = None
    source_name: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    tries: Optional[int] = None
    status: Optional[str] = None


# =============================================================================
# Health Check Schemas
# =============================================================================

class HealthCheckComponent(BaseSchema):
    """Schema for individual component health."""
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthCheckResponse(BaseSchema):
    """Schema for health check endpoint."""
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    components: Dict[str, HealthCheckComponent]
    queue_lag_seconds: Optional[float] = None
