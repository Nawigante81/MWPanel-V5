"""
Listing Management Service - Zarządzanie Komisem

Kompleksowy system zarządzania portfelem nieruchomości biura.
Śledzenie statusów, właścicieli, ekskluzywności, kluczy, dokumentów.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import uuid

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, 
    Integer, Float, Boolean, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session
from sqlalchemy import func

from app.db.base import Base
from app.core.logging import get_logger

logger = get_logger(__name__)


class ListingStatus(str, Enum):
    """Statusy oferty w biurze"""
    # Aktywne
    ACTIVE = "active"                          # Dostępna, widoczna na portalach
    RESERVED = "reserved"                      # Zarezerwowana (czeka na podpis)
    PRELIMINARY_RESERVED = "preliminary_reserved"  # Wstępna rezerwacja (ustna)
    
    # Negocjacje
    UNDER_NEGOTIATION = "under_negotiation"    # W trakcie negocjacji
    OFFER_SUBMITTED = "offer_submitted"        # Złożono ofertę kupna
    
    # Zamknięte
    SOLD = "sold"                              # Sprzedana
    RENTED = "rented"                          # Wynajęta
    WITHDRAWN = "withdrawn"                    # Wycofana przez właściciela
    EXPIRED = "expired"                        # Umowa wygasła
    EXCLUSIVE_ENDED = "exclusive_ended"        # Koniec wyłączności
    
    # Specjalne
    PRIVATE = "private"                        # Prywatna (nie na portalach, tylko dla klientów biura)
    COMING_SOON = "coming_soon"                # Wkrótce w ofercie (przygotowanie)


class ExclusiveType(str, Enum):
    """Typ umowy pośrednictwa"""
    OPEN = "open"                              # Otwarta (wiele biur)
    EXCLUSIVE = "exclusive"                    # Wyłączność (tylko to biuro)
    EXCLUSIVE_WITH_MARKETING = "exclusive_with_marketing"  # Wyłączność z marketingiem
    SOLE_MANDATE = "sole_mandate"              # Jedyny pełnomocnik


class KeyStatus(str, Enum):
    """Status kluczy"""
    WITH_OWNER = "with_owner"                  # U właściciela
    WITH_OFFICE = "with_office"                # W biurze
    WITH_AGENT = "with_agent"                  # U agenta
    AT_PROPERTY = "at_property"                # W skrzynce na miejscu
    LOST = "lost"                              # Zagubione


class Listing(Base):
    """Oferta nieruchomości w biurze (komis)"""
    __tablename__ = 'listings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Podstawowe informacje
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Status
    status = Column(SQLEnum(ListingStatus), default=ListingStatus.COMING_SOON, index=True)
    status_changed_at = Column(DateTime(timezone=True), nullable=True)
    status_changed_by = Column(String(100), nullable=True)
    status_change_reason = Column(Text, nullable=True)
    
    # Własność i ekskluzywność
    owner_id = Column(UUID(as_uuid=True), ForeignKey('property_owners.id'), nullable=False)
    exclusive_type = Column(SQLEnum(ExclusiveType), default=ExclusiveType.OPEN)
    exclusive_until = Column(DateTime(timezone=True), nullable=True)  # Koniec wyłączności
    commission_percent = Column(Float, default=3.0)  # Prowizja biura (%)
    minimum_commission = Column(Float, nullable=True)  # Minimalna prowizja (PLN)
    
    # Przypisanie
    assigned_agent_id = Column(String(100), ForeignKey('users.id'), nullable=True)
    co_agent_id = Column(String(100), ForeignKey('users.id'), nullable=True)  # Drugi agent
    commission_split = Column(Float, default=50.0)  # Podział prowizji (% dla głównego agenta)
    
    # Dane nieruchomości (denormalizacja dla wygody)
    property_type = Column(String(50), nullable=False)  # apartment, house, etc.
    offer_type = Column(String(20), default="sale")  # sale, rent
    
    # Lokalizacja
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=True, index=True)
    zip_code = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Parametry
    price = Column(Float, nullable=False)
    price_negotiable = Column(Boolean, default=True)
    area_sqm = Column(Float, nullable=True)
    rooms = Column(Integer, nullable=True)
    floor = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    build_year = Column(Integer, nullable=True)
    condition = Column(String(50), nullable=True)  # excellent, good, average, poor
    
    # Dodatkowe parametry
    has_balcony = Column(Boolean, default=False)
    has_garden = Column(Boolean, default=False)
    has_parking = Column(Boolean, default=False)
    has_elevator = Column(Boolean, default=False)
    has_air_conditioning = Column(Boolean, default=False)
    is_furnished = Column(Boolean, default=False)
    pets_allowed = Column(Boolean, nullable=True)
    
    # Media i opłaty
    rent_amount = Column(Float, nullable=True)  # Czynsz przy sprzedaży
    utility_costs = Column(Float, nullable=True)  # Koszty eksploatacji
    heating_type = Column(String(50), nullable=True)
    
    # Klucze
    key_status = Column(SQLEnum(KeyStatus), default=KeyStatus.WITH_OWNER)
    key_location = Column(String(255), nullable=True)  # Gdzie dokładnie są klucze
    key_code = Column(String(50), nullable=True)  # Kod do skrzynki
    
    # Statystyki aktywności
    view_count = Column(Integer, default=0)
    inquiry_count = Column(Integer, default=0)
    presentation_count = Column(Integer, default=0);
    last_presentation_at = Column(DateTime(timezone=True), nullable=True)
    
    # Portale
    published_on_otodom = Column(Boolean, default=False)
    published_on_olx = Column(Boolean, default=False)
    published_on_facebook = Column(Boolean, default=False)
    published_on_allegro = Column(Boolean, default=False)
    published_on_website = Column(Boolean, default=False)
    
    # Daty ważności
    available_from = Column(DateTime(timezone=True), nullable=True)
    available_immediately = Column(Boolean, default=True)
    
    # Organizacja
    organization_id = Column(String(100), nullable=True, index=True)
    
    # Metadane
    tags = Column(JSONB, default=list)
    custom_fields = Column(JSONB, default=dict)
    internal_notes = Column(Text, nullable=True)  # Notatki wewnętrzne (nie dla klientów)
    
    # Relacje
    owner = relationship("PropertyOwner", back_populates="listings")
    images = relationship("ListingImage", back_populates="listing", cascade="all, delete-orphan")
    documents = relationship("ListingDocument", back_populates="listing", cascade="all, delete-orphan")
    status_history = relationship("ListingStatusHistory", back_populates="listing", cascade="all, delete-orphan")
    presentations = relationship("PropertyPresentation", back_populates="listing")
    
    __table_args__ = (
        Index('idx_listings_status_city', 'status', 'city'),
        Index('idx_listings_agent_status', 'assigned_agent_id', 'status'),
        Index('idx_listings_org_status', 'organization_id', 'status'),
        Index('idx_listings_price', 'price'),
    )


class PropertyOwner(Base):
    """Właściciel nieruchomości (osobna baza od leadów kupujących)"""
    __tablename__ = 'property_owners'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Dane osobowe
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=False)
    phone_secondary = Column(String(50), nullable=True)
    
    # Adres
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    
    # Preferencje kontaktu
    preferred_contact_method = Column(String(20), default="phone")  # phone, email
    best_time_to_contact = Column(String(50), nullable=True)
    
    # Historia współpracy
    total_listings = Column(Integer, default=0)
    total_sold = Column(Integer, default=0)
    total_rented = Column(Integer, default=0)
    first_cooperation_date = Column(DateTime(timezone=True), nullable=True)
    last_cooperation_date = Column(DateTime(timezone=True), nullable=True)
    
    # Ocena współpracy
    cooperation_rating = Column(Integer, nullable=True)  # 1-5 gwiazdek
    notes = Column(Text, nullable=True)
    
    # Organizacja
    organization_id = Column(String(100), nullable=True, index=True)
    
    # Relacje
    listings = relationship("Listing", back_populates="owner")
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ListingImage(Base):
    """Zdjęcia oferty"""
    __tablename__ = 'listing_images'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=False)
    
    url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    
    # Metadane
    order = Column(Integer, default=0)  # Kolejność wyświetlania
    room_type = Column(String(50), nullable=True)  # salon, sypialnia, kuchnia, itp.
    description = Column(String(255), nullable=True)
    is_main = Column(Boolean, default=False)  # Główne zdjęcie
    
    # Status
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    uploaded_by = Column(String(100), nullable=True)
    
    listing = relationship("Listing", back_populates="images")


class ListingDocument(Base):
    """Dokumenty oferty (umowy, załączniki)"""
    __tablename__ = 'listing_documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=False)
    
    name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)  # pdf, doc, jpg
    file_size_bytes = Column(Integer, nullable=True)
    
    # Typ dokumentu
    document_type = Column(String(50), nullable=True)  # 
    # agreement - umowa pośrednictwa
    # power_of_attorney - pełnomocnictwo
    # property_deed - księga wieczysta
    # energy_certificate - świadectwo energetyczne
    # other - inne
    
    # Status
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    uploaded_by = Column(String(100), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Data ważności
    
    listing = relationship("Listing", back_populates="documents")


class ListingStatusHistory(Base):
    """Historia zmian statusu oferty"""
    __tablename__ = 'listing_status_history'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=False)
    
    changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    changed_by = Column(String(100), nullable=False)
    
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    reason = Column(Text, nullable=True)
    
    listing = relationship("Listing", back_populates="status_history")


class PropertyPresentation(Base):
    """Prezentacja nieruchomości klientowi"""
    __tablename__ = 'property_presentations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=False)
    
    # Klient
    client_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=True)
    client_name = Column(String(200), nullable=True)  # Dla niezarejestrowanych
    client_phone = Column(String(50), nullable=True)
    
    # Agent i termin
    agent_id = Column(String(100), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    
    # Status
    status = Column(String(20), default="scheduled")  # scheduled, completed, cancelled, no_show
    
    # Wynik
    client_interested = Column(Boolean, nullable=True)  # Klient zainteresowany
    client_feedback = Column(Text, nullable=True)  # Opinia klienta
    agent_notes = Column(Text, nullable=True)  # Notatki agenta
    
    # Powiązane oferty (klient oglądał też...)
    related_listings_viewed = Column(JSONB, default=list)
    
    # Potencjalna oferta
    offer_submitted_after = Column(Boolean, default=False)
    offer_amount = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    listing = relationship("Listing", back_populates="presentations")


class ListingManagementService:
    """
    Serwis zarządzania komisem biura nieruchomości.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    # ===== LISTING CRUD =====
    
    async def create_listing(
        self,
        title: str,
        owner_id: uuid.UUID,
        price: float,
        address: str,
        city: str,
        assigned_agent_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        **kwargs
    ) -> Listing:
        """Dodaj nową ofertę do komisu"""
        listing = Listing(
            title=title,
            owner_id=owner_id,
            price=price,
            address=address,
            city=city,
            assigned_agent_id=assigned_agent_id,
            organization_id=organization_id,
            status=ListingStatus.COMING_SOON,
            **kwargs
        )
        
        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)
        
        # Aktualizuj statystyki właściciela
        await self._update_owner_stats(owner_id)
        
        logger.info(f"Created listing {listing.id}: {title}")
        return listing
    
    async def get_listing(self, listing_id: uuid.UUID) -> Optional[Listing]:
        """Pobierz szczegóły oferty"""
        return self.db.query(Listing).filter(Listing.id == listing_id).first()
    
    async def change_status(
        self,
        listing_id: uuid.UUID,
        new_status: ListingStatus,
        changed_by: str,
        reason: Optional[str] = None
    ) -> Optional[Listing]:
        """Zmień status oferty z historią"""
        listing = await self.get_listing(listing_id)
        if not listing:
            return None
        
        old_status = listing.status
        
        # Aktualizuj status
        listing.status = new_status
        listing.status_changed_at = datetime.utcnow()
        listing.status_changed_by = changed_by
        listing.status_change_reason = reason
        
        # Zapisz w historii
        history = ListingStatusHistory(
            listing_id=listing_id,
            changed_by=changed_by,
            old_status=old_status.value if old_status else None,
            new_status=new_status.value,
            reason=reason
        )
        self.db.add(history)
        
        self.db.commit()
        
        logger.info(f"Listing {listing_id}: {old_status.value} -> {new_status.value}")
        return listing
    
    async def update_listing(
        self,
        listing_id: uuid.UUID,
        updated_by: str,
        **kwargs
    ) -> Optional[Listing]:
        """Aktualizuj dane oferty"""
        listing = await self.get_listing(listing_id)
        if not listing:
            return None
        
        for key, value in kwargs.items():
            if hasattr(listing, key):
                setattr(listing, key, value)
        
        listing.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(listing)
        
        return listing
    
    # ===== WŁAŚCICIELE =====
    
    async def create_owner(
        self,
        first_name: str,
        last_name: str,
        phone: str,
        organization_id: Optional[str] = None,
        **kwargs
    ) -> PropertyOwner:
        """Dodaj właściciela do bazy"""
        owner = PropertyOwner(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            organization_id=organization_id,
            **kwargs
        )
        
        self.db.add(owner)
        self.db.commit()
        self.db.refresh(owner)
        
        logger.info(f"Created owner: {owner.full_name}")
        return owner
    
    async def find_owner_by_phone(self, phone: str) -> Optional[PropertyOwner]:
        """Znajdź właściciela po telefonie"""
        return self.db.query(PropertyOwner).filter(PropertyOwner.phone == phone).first()
    
    async def _update_owner_stats(self, owner_id: uuid.UUID):
        """Aktualizuj statystyki właściciela"""
        owner = self.db.query(PropertyOwner).filter(PropertyOwner.id == owner_id).first()
        if not owner:
            return
        
        listings = self.db.query(Listing).filter(Listing.owner_id == owner_id).all()
        
        owner.total_listings = len(listings)
        owner.total_sold = sum(1 for l in listings if l.status == ListingStatus.SOLD)
        owner.total_rented = sum(1 for l in listings if l.status == ListingStatus.RENTED)
        
        if listings and not owner.first_cooperation_date:
            owner.first_cooperation_date = min(l.created_at for l in listings)
        
        if listings:
            owner.last_cooperation_date = max(l.created_at for l in listings)
        
        self.db.commit()
    
    # ===== PREZENTACJE =====
    
    async def schedule_presentation(
        self,
        listing_id: uuid.UUID,
        agent_id: str,
        scheduled_at: datetime,
        client_id: Optional[uuid.UUID] = None,
        client_name: Optional[str] = None,
        client_phone: Optional[str] = None,
        **kwargs
    ) -> PropertyPresentation:
        """Zaplanuj prezentację"""
        presentation = PropertyPresentation(
            listing_id=listing_id,
            agent_id=agent_id,
            scheduled_at=scheduled_at,
            client_id=client_id,
            client_name=client_name,
            client_phone=client_phone,
            **kwargs
        )
        
        self.db.add(presentation)
        
        # Aktualizuj licznik prezentacji oferty
        listing = await self.get_listing(listing_id)
        if listing:
            listing.presentation_count += 1
        
        self.db.commit()
        self.db.refresh(presentation)
        
        return presentation
    
    async def complete_presentation(
        self,
        presentation_id: uuid.UUID,
        client_interested: bool,
        agent_notes: Optional[str] = None,
        client_feedback: Optional[str] = None
    ) -> Optional[PropertyPresentation]:
        """Oznacz prezentację jako zakończoną"""
        presentation = self.db.query(PropertyPresentation).filter(
            PropertyPresentation.id == presentation_id
        ).first()
        
        if not presentation:
            return None
        
        presentation.status = "completed"
        presentation.client_interested = client_interested
        presentation.agent_notes = agent_notes
        presentation.client_feedback = client_feedback
        
        self.db.commit()
        
        return presentation
    
    # ===== KLUCZE =====
    
    async def update_key_status(
        self,
        listing_id: uuid.UUID,
        key_status: KeyStatus,
        key_location: Optional[str] = None,
        key_code: Optional[str] = None
    ) -> Optional[Listing]:
        """Aktualizuj status kluczy"""
        listing = await self.get_listing(listing_id)
        if not listing:
            return None
        
        listing.key_status = key_status
        if key_location:
            listing.key_location = key_location
        if key_code:
            listing.key_code = key_code
        
        self.db.commit()
        return listing
    
    # ===== STATYSTYKI =====
    
    async def get_listing_statistics(
        self,
        organization_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pobierz statystyki ofert"""
        query = self.db.query(Listing)
        
        if organization_id:
            query = query.filter(Listing.organization_id == organization_id)
        if agent_id:
            query = query.filter(Listing.assigned_agent_id == agent_id)
        
        total = query.count()
        
        # Statusy
        status_counts = query.with_entities(
            Listing.status,
            func.count(Listing.id)
        ).group_by(Listing.status).all()
        
        # Ekskluzywność
        exclusive_count = query.filter(
            Listing.exclusive_type.in_([ExclusiveType.EXCLUSIVE, ExclusiveType.EXCLUSIVE_WITH_MARKETING])
        ).count()
        
        # Średni czas sprzedaży (dla sprzedanych)
        sold_listings = query.filter(Listing.status == ListingStatus.SOLD).all()
        avg_days_on_market = 0
        if sold_listings:
            days = []
            for l in sold_listings:
                if l.status_changed_at and l.created_at:
                    days.append((l.status_changed_at - l.created_at).days)
            avg_days_on_market = sum(days) / len(days) if days else 0
        
        # Wartość portfela
        total_value = query.with_entities(func.sum(Listing.price)).scalar() or 0
        
        # Potencjalna prowizja
        potential_commission = query.with_entities(
            func.sum(Listing.price * Listing.commission_percent / 100)
        ).scalar() or 0
        
        return {
            'total_listings': total,
            'by_status': {status.value: count for status, count in status_counts},
            'exclusive_count': exclusive_count,
            'avg_days_on_market': round(avg_days_on_market, 1),
            'total_portfolio_value': round(total_value, 2),
            'potential_commission': round(potential_commission, 2),
        }
    
    async def get_agent_dashboard(
        self,
        agent_id: str,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dashboard dla agenta"""
        query = self.db.query(Listing).filter(Listing.assigned_agent_id == agent_id)
        
        if organization_id:
            query = query.filter(Listing.organization_id == organization_id)
        
        # Aktywne oferty
        active = query.filter(Listing.status == ListingStatus.ACTIVE).count()
        
        # Prezentacje dzisiaj
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        presentations_today = self.db.query(PropertyPresentation).filter(
            PropertyPresentation.agent_id == agent_id,
            PropertyPresentation.scheduled_at >= today_start
        ).count()
        
        # Sprzedane w tym miesiącu
        month_start = today_start.replace(day=1)
        sold_this_month = query.filter(
            Listing.status == ListingStatus.SOLD,
            Listing.status_changed_at >= month_start
        ).count()
        
        # Nadchodzące prezentacje
        upcoming = self.db.query(PropertyPresentation).filter(
            PropertyPresentation.agent_id == agent_id,
            PropertyPresentation.scheduled_at >= datetime.utcnow(),
            PropertyPresentation.status == "scheduled"
        ).order_by(PropertyPresentation.scheduled_at).limit(5).all()
        
        return {
            'active_listings': active,
            'presentations_today': presentations_today,
            'sold_this_month': sold_this_month,
            'upcoming_presentations': [
                {
                    'id': str(p.id),
                    'scheduled_at': p.scheduled_at.isoformat(),
                    'address': p.listing.address if p.listing else None,
                    'client_name': p.client_name,
                }
                for p in upcoming
            ]
        }
