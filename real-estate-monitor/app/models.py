"""
SQLAlchemy 2.0 models for the real estate monitoring system.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class SourceFetchMode(str, PyEnum):
    """Fetch mode for sources."""
    PLAYWRIGHT = "playwright"
    HTTP = "http"


class NotificationStatus(str, PyEnum):
    """Notification status values."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationChannel(str, PyEnum):
    """Notification channel types."""
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WEBHOOK = "webhook"


class OfferStatus(str, PyEnum):
    """Offer status values."""
    ACTIVE = "active"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PRICE_CHANGED = "price_changed"
    INVALID_PARSE = "invalid_parse"


class AlertOperator(str, PyEnum):
    """Alert rule operators."""
    LESS_THAN = "lt"
    LESS_EQUAL = "le"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "ge"
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    CONTAINS = "contains"
    IN = "in"


class ScrapeRunStatus(str, PyEnum):
    """Scrape run status values."""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Source(Base):
    """Source configuration table."""
    
    __tablename__ = "sources"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    fetch_mode: Mapped[SourceFetchMode] = mapped_column(
        String(20),
        default=SourceFetchMode.PLAYWRIGHT,
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(default=60, nullable=False)
    rate_limit_rps: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    offers: Mapped[list["Offer"]] = relationship("Offer", back_populates="source")
    scrape_runs: Mapped[list["ScrapeRun"]] = relationship("ScrapeRun", back_populates="source")
    
    def __repr__(self) -> str:
        return f"<Source(id={self.id}, name={self.name}, enabled={self.enabled})>"


class Offer(Base):
    """Offers table with deduplication via fingerprint."""
    
    __tablename__ = "offers"
    
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_offers_fingerprint"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    area_m2: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    rooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Status tracking
    status: Mapped[OfferStatus] = mapped_column(
        String(20),
        default=OfferStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Full-text search vector
    search_vector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Publication/import timestamps
    source_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )
    
    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="offers")
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="offer"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="offer", order_by="PriceHistory.recorded_at.desc()"
    )
    image_analysis: Mapped[list["ImageAnalysis"]] = relationship(
        "ImageAnalysis", back_populates="offer"
    )
    notes: Mapped[list["OfferNote"]] = relationship(
        "OfferNote", back_populates="offer", order_by="OfferNote.created_at.desc()"
    )
    tags: Mapped[list["OfferTag"]] = relationship(
        "OfferTag", back_populates="offer"
    )
    
    def __repr__(self) -> str:
        return f"<Offer(id={self.id}, title={self.title[:50]}, price={self.price}, status={self.status})>"


class Notification(Base):
    """Notifications table for tracking multi-channel sends."""
    
    __tablename__ = "notifications"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        String(50),
        default=NotificationChannel.WHATSAPP,
        nullable=False,
    )
    recipient: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(
        String(20),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    tries: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=8, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    offer: Mapped["Offer"] = relationship("Offer", back_populates="notifications")
    
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, channel={self.channel}, status={self.status})>"


class ScrapeRun(Base):
    """Scrape run tracking for observability."""
    
    __tablename__ = "scrape_runs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ScrapeRunStatus] = mapped_column(
        String(20),
        default=ScrapeRunStatus.RUNNING,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    offers_found: Mapped[int] = mapped_column(default=0, nullable=False)
    offers_new: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="scrape_runs")
    
    def __repr__(self) -> str:
        return f"<ScrapeRun(id={self.id}, status={self.status}, started_at={self.started_at})>"


class PriceHistory(Base):
    """Price history tracking for offers."""
    
    __tablename__ = "price_history"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="PLN", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    price_change_percent: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # Relationships
    offer: Mapped["Offer"] = relationship("Offer", back_populates="price_history")
    
    def __repr__(self) -> str:
        return f"<PriceHistory(offer_id={self.offer_id}, price={self.price})>"


class Webhook(Base):
    """Webhook subscriptions for external integrations."""
    
    __tablename__ = "webhooks"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    secret: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_triggered: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    fail_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    def __repr__(self) -> str:
        return f"<Webhook(id={self.id}, url={self.url[:50]})>"


class UserPreference(Base):
    """User preferences for smart filtering."""
    
    __tablename__ = "user_preferences"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
    # Location preferences
    preferred_cities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    preferred_regions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    max_distance_km: Mapped[Optional[float]] = mapped_column(nullable=True)
    reference_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    reference_lng: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    
    # Price preferences
    min_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    max_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    
    # Property preferences
    min_area: Mapped[Optional[float]] = mapped_column(nullable=True)
    max_area: Mapped[Optional[float]] = mapped_column(nullable=True)
    preferred_rooms: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # ML scoring weights (learned)
    price_weight: Mapped[float] = mapped_column(default=0.3, nullable=False)
    location_weight: Mapped[float] = mapped_column(default=0.3, nullable=False)
    size_weight: Mapped[float] = mapped_column(default=0.2, nullable=False)
    rooms_weight: Mapped[float] = mapped_column(default=0.2, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<UserPreference(user_id={self.user_id})>"


class ImageAnalysis(Base):
    """Image analysis results for offers."""
    
    __tablename__ = "image_analysis"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    # Analysis results
    room_count_estimate: Mapped[Optional[int]] = mapped_column(nullable=True)
    has_furniture: Mapped[Optional[bool]] = mapped_column(nullable=True)
    condition_score: Mapped[Optional[float]] = mapped_column(nullable=True)  # 0-10
    brightness_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # Perceptual hash for duplicate detection
    perceptual_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    offer: Mapped["Offer"] = relationship("Offer", back_populates="image_analysis")
    
    def __repr__(self) -> str:
        return f"<ImageAnalysis(offer_id={self.offer_id}, rooms={self.room_count_estimate})>"


class FailedScrape(Base):
    """Failed scrape attempts for retry queue."""
    
    __tablename__ = "failed_scrapes"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    filter_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=5, nullable=False)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    def __repr__(self) -> str:
        return f"<FailedScrape(source={self.source_name}, retries={self.retry_count})>"


class OfferNote(Base):
    """User notes for offers."""
    
    __tablename__ = "offer_notes"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    offer: Mapped["Offer"] = relationship("Offer", back_populates="notes")
    
    def __repr__(self) -> str:
        return f"<OfferNote(offer_id={self.offer_id}, user_id={self.user_id})>"


class UserFavorite(Base):
    """User favorite offers."""
    
    __tablename__ = "user_favorites"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    __table_args__ = (
        sa.UniqueConstraint("offer_id", "user_id", name="uq_user_favorite"),
    )
    
    def __repr__(self) -> str:
        return f"<UserFavorite(offer_id={self.offer_id}, user_id={self.user_id})>"


class OfferTag(Base):
    """Tags for offers."""
    
    __tablename__ = "offer_tags"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    __table_args__ = (
        sa.UniqueConstraint("offer_id", "tag", name="uq_offer_tag"),
    )

    # Relationships
    offer: Mapped["Offer"] = relationship("Offer", back_populates="tags")
    
    def __repr__(self) -> str:
        return f"<OfferTag(offer_id={self.offer_id}, tag={self.tag})>"


class AlertRule(Base):
    """User alert rules for notifications."""
    
    __tablename__ = "alert_rules"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # Rule conditions (JSON array of conditions)
    # Example: [{"field": "price", "operator": "lt", "value": 500000}]
    conditions: Mapped[list] = mapped_column(JSON, nullable=False)
    
    # Notification settings
    channels: Mapped[list] = mapped_column(JSON, nullable=False)  # ["whatsapp", "email"]
    
    # Cooldown between alerts (minutes)
    cooldown_minutes: Mapped[int] = mapped_column(default=60, nullable=False)
    
    last_triggered: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trigger_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<AlertRule(name={self.name}, user_id={self.user_id})>"


class WeeklyReport(Base):
    """Weekly summary reports."""
    
    __tablename__ = "weekly_reports"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Report period
    week_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    week_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Statistics
    total_new_offers: Mapped[int] = mapped_column(default=0, nullable=False)
    total_price_drops: Mapped[int] = mapped_column(default=0, nullable=False)
    avg_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    top_cities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Report content
    report_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Delivery status
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_to: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<WeeklyReport(week_start={self.week_start}, user_id={self.user_id})>"


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    offer_type: Mapped[str] = mapped_column(String(32), nullable=False)
    property_type: Mapped[str] = mapped_column(String(32), nullable=False)
    market_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    rooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plot_area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_built: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    heating: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ownership: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    street: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    crm_status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PropertyImage(Base):
    __tablename__ = "property_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_cover: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PropertyPublication(Base):
    __tablename__ = "property_publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    portal: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_listing_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    publication_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PublicationJob(Base):
    __tablename__ = "publication_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    portal: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    job_status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=5, nullable=False)
    run_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
