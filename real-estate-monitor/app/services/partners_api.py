"""
Partners API Service - API dla Partnerów

Integracja z zewnętrznymi biurami nieruchomości i deweloperami.
Wymiana ofert, synchronizacja, raporty.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import hashlib
import secrets

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class PartnerType(str, Enum):
    """Typ partnera"""
    AGENCY = "agency"              # Biuro nieruchomości
    DEVELOPER = "developer"        # Deweloper
    PORTAL = "portal"              # Portal ogłoszeniowy
    BANK = "bank"                  # Bank (kredyty)
    INSURANCE = "insurance"        # Ubezpieczenia
    OTHER = "other"                # Inne


class PartnerStatus(str, Enum):
    """Status partnerstwa"""
    PENDING = "pending"            # Oczekuje na akceptację
    ACTIVE = "active"              # Aktywny
    SUSPENDED = "suspended"        # Zawieszony
    TERMINATED = "terminated"      # Zakończony


class DataAccessLevel(str, Enum):
    """Poziom dostępu do danych"""
    READ_ONLY = "read_only"        # Tylko odczyt
    READ_WRITE = "read_write"      # Odczyt i zapis
    FULL = "full"                  # Pełny dostęp


@dataclass
class Partner:
    """Partner (zewnętrzne biuro/deweloper)"""
    id: str
    name: str
    partner_type: PartnerType
    status: PartnerStatus
    
    # Kontakt
    contact_name: str
    contact_email: str
    contact_phone: str
    
    # API
    api_key: str
    api_secret: str
    webhook_url: Optional[str]
    access_level: DataAccessLevel
    
    # Limity
    rate_limit_per_minute: int = 60
    daily_quota: int = 1000
    
    # Finanse
    commission_share_percent: float = 50.0  # Podział prowizji
    
    # Statystyki
    total_listings_shared: int = 0
    total_leads_received: int = 0
    total_transactions: int = 0
    
    # Daty
    created_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.partner_type.value,
            'status': self.status.value,
            'contact': {
                'name': self.contact_name,
                'email': self.contact_email,
                'phone': self.contact_phone,
            },
            'access_level': self.access_level.value,
            'commission_share': self.commission_share_percent,
            'stats': {
                'listings_shared': self.total_listings_shared,
                'leads_received': self.total_leads_received,
                'transactions': self.total_transactions,
            },
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class SharedListing:
    """Współdzielona oferta"""
    id: str
    partner_id: str
    
    # Nasza oferta
    internal_listing_id: str
    
    # Zewnętrzne ID
    partner_listing_id: Optional[str]
    
    # Status synchronizacji
    sync_status: str  # synced, pending, error
    last_sync_at: Optional[datetime]
    sync_error: Optional[str]
    
    # Statystyki
    partner_views: int = 0
    partner_inquiries: int = 0
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'partner_id': self.partner_id,
            'internal_listing_id': self.internal_listing_id,
            'partner_listing_id': self.partner_listing_id,
            'sync_status': self.sync_status,
            'last_sync': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'stats': {
                'views': self.partner_views,
                'inquiries': self.partner_inquiries,
            },
        }


@dataclass
class ApiRequestLog:
    """Log żądania API partnera"""
    id: str
    partner_id: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: int
    timestamp: datetime
    ip_address: Optional[str] = None
    error_message: Optional[str] = None


class PartnersAPIService:
    """
    Serwis API dla partnerów.
    
    Zarządza integracjami z zewnętrznymi biurami, deweloperami
    i innymi partnerami biznesowymi.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.partners: Dict[str, Partner] = {}
        self.api_keys: Dict[str, str] = {}  # api_key -> partner_id
    
    # ==========================================================================
    # Zarządzanie partnerami
    # ==========================================================================
    
    async def register_partner(
        self,
        name: str,
        partner_type: PartnerType,
        contact_name: str,
        contact_email: str,
        contact_phone: str,
        webhook_url: Optional[str] = None,
        access_level: DataAccessLevel = DataAccessLevel.READ_ONLY,
        commission_share: float = 50.0,
    ) -> Partner:
        """
        Zarejestruj nowego partnera.
        
        Returns:
            Partner z wygenerowanymi kluczami API
        """
        # Generuj klucze API
        api_key = self._generate_api_key()
        api_secret = self._generate_api_secret()
        
        partner = Partner(
            id=str(uuid.uuid4()),
            name=name,
            partner_type=partner_type,
            status=PartnerStatus.PENDING,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            api_key=api_key,
            api_secret=api_secret,
            webhook_url=webhook_url,
            access_level=access_level,
            commission_share_percent=commission_share,
        )
        
        # Zapisz
        self.partners[partner.id] = partner
        self.api_keys[api_key] = partner.id
        
        logger.info(f"Partner registered: {name} ({partner_type.value})")
        
        return partner
    
    async def activate_partner(self, partner_id: str) -> Optional[Partner]:
        """Aktywuj partnera"""
        partner = self.partners.get(partner_id)
        if not partner:
            return None
        
        partner.status = PartnerStatus.ACTIVE
        partner.activated_at = datetime.utcnow()
        
        logger.info(f"Partner activated: {partner.name}")
        
        return partner
    
    async def suspend_partner(
        self,
        partner_id: str,
        reason: str,
    ) -> Optional[Partner]:
        """Zawieś partnera"""
        partner = self.partners.get(partner_id)
        if not partner:
            return None
        
        partner.status = PartnerStatus.SUSPENDED
        
        logger.info(f"Partner suspended: {partner.name}, reason: {reason}")
        
        return partner
    
    async def revoke_partner(self, partner_id: str) -> bool:
        """Unieważnij dostęp partnera"""
        partner = self.partners.get(partner_id)
        if not partner:
            return False
        
        partner.status = PartnerStatus.TERMINATED
        
        # Unieważnij klucze
        if partner.api_key in self.api_keys:
            del self.api_keys[partner.api_key]
        
        logger.info(f"Partner access revoked: {partner.name}")
        
        return True
    
    async def regenerate_api_keys(self, partner_id: str) -> Optional[Partner]:
        """Wygeneruj nowe klucze API"""
        partner = self.partners.get(partner_id)
        if not partner:
            return None
        
        # Usuń stary klucz
        if partner.api_key in self.api_keys:
            del self.api_keys[partner.api_key]
        
        # Generuj nowe
        partner.api_key = self._generate_api_key()
        partner.api_secret = self._generate_api_secret()
        
        self.api_keys[partner.api_key] = partner_id
        
        logger.info(f"API keys regenerated for partner: {partner.name}")
        
        return partner
    
    async def get_partner(self, partner_id: str) -> Optional[Partner]:
        """Pobierz partnera po ID"""
        return self.partners.get(partner_id)
    
    async def get_partner_by_api_key(self, api_key: str) -> Optional[Partner]:
        """Pobierz partnera po kluczu API"""
        partner_id = self.api_keys.get(api_key)
        if partner_id:
            return self.partners.get(partner_id)
        return None
    
    async def list_partners(
        self,
        status: Optional[PartnerStatus] = None,
        partner_type: Optional[PartnerType] = None,
    ) -> List[Partner]:
        """Lista partnerów z filtrami"""
        partners = list(self.partners.values())
        
        if status:
            partners = [p for p in partners if p.status == status]
        
        if partner_type:
            partners = [p for p in partners if p.partner_type == partner_type]
        
        return partners
    
    # ==========================================================================
    # Współdzielenie ofert
    # ==========================================================================
    
    async def share_listing(
        self,
        partner_id: str,
        listing_id: str,
    ) -> Optional[SharedListing]:
        """
        Udostępnij ofertę partnerowi.
        
        Returns:
            SharedListing lub None jeśli partner nieaktywny
        """
        partner = self.partners.get(partner_id)
        if not partner or partner.status != PartnerStatus.ACTIVE:
            return None
        
        shared = SharedListing(
            id=str(uuid.uuid4()),
            partner_id=partner_id,
            internal_listing_id=listing_id,
            partner_listing_id=None,
            sync_status='pending',
            last_sync_at=None,
            sync_error=None,
        )
        
        # Wyślij webhook do partnera
        if partner.webhook_url:
            await self._send_webhook(partner, 'listing_shared', {
                'shared_id': shared.id,
                'listing_id': listing_id,
            })
        
        partner.total_listings_shared += 1
        
        logger.info(f"Listing {listing_id} shared with partner {partner.name}")
        
        return shared
    
    async def unshare_listing(
        self,
        partner_id: str,
        listing_id: str,
    ) -> bool:
        """Przestań udostępniać ofertę"""
        partner = self.partners.get(partner_id)
        if not partner:
            return False
        
        # Wyślij webhook
        if partner.webhook_url:
            await self._send_webhook(partner, 'listing_unshared', {
                'listing_id': listing_id,
            })
        
        logger.info(f"Listing {listing_id} unshared from partner {partner.name}")
        
        return True
    
    async def sync_listing(
        self,
        shared_id: str,
        partner_listing_id: Optional[str] = None,
    ) -> Optional[SharedListing]:
        """Zsynchronizuj ofertę z partnerem"""
        # W rzeczywistej implementacji
        return None
    
    async def get_shared_listings(
        self,
        partner_id: str,
        sync_status: Optional[str] = None,
    ) -> List[SharedListing]:
        """Pobierz oferty udostępnione partnerowi"""
        # W rzeczywistej implementacji
        return []
    
    # ==========================================================================
    # API dla partnerów
    # ==========================================================================
    
    async def authenticate_request(
        self,
        api_key: str,
        api_secret: str,
    ) -> Optional[Partner]:
        """Uwierzytelnij żądanie API"""
        partner = await self.get_partner_by_api_key(api_key)
        
        if not partner:
            return None
        
        if partner.status != PartnerStatus.ACTIVE:
            return None
        
        # Weryfikuj secret
        if not self._verify_secret(api_secret, partner.api_secret):
            return None
        
        partner.last_activity_at = datetime.utcnow()
        
        return partner
    
    async def check_rate_limit(self, partner_id: str) -> bool:
        """Sprawdź czy partner nie przekroczył limitu"""
        partner = self.partners.get(partner_id)
        if not partner:
            return False
        
        # W rzeczywistej implementacji: sprawdź w Redis/cache
        
        return True
    
    async def get_listings_for_partner(
        self,
        partner_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Pobierz oferty dla partnera (API endpoint).
        
        Returns:
            Lista ofert w formacie dla partnera
        """
        partner = self.partners.get(partner_id)
        if not partner:
            return []
        
        # Pobierz oferty z bazy
        listings = self._query_listings(filters, limit, offset)
        
        # Przekształć do formatu API
        result = []
        for listing in listings:
            result.append({
                'id': listing.get('id'),
                'external_id': listing.get('external_id'),
                'title': listing.get('title'),
                'description': listing.get('description'),
                'property_type': listing.get('property_type'),
                'transaction_type': listing.get('transaction_type'),
                'price': float(listing.get('price', 0)),
                'currency': listing.get('currency', 'PLN'),
                'area_sqm': listing.get('area_sqm'),
                'rooms': listing.get('rooms'),
                'city': listing.get('city'),
                'district': listing.get('district'),
                'street': listing.get('street'),
                'images': listing.get('images', []),
                'contact': {
                    'agency_name': 'Biuro Nieruchomości',
                    'phone': '+48 123 456 789',
                    'email': 'kontakt@biuro.pl',
                } if partner.access_level == DataAccessLevel.READ_ONLY else {
                    'agent_name': listing.get('agent_name'),
                    'agent_phone': listing.get('agent_phone'),
                    'agent_email': listing.get('agent_email'),
                },
                'updated_at': listing.get('updated_at'),
            })
        
        return result
    
    async def submit_lead(
        self,
        partner_id: str,
        listing_id: str,
        lead_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Przyjmij lead od partnera.
        
        Args:
            partner_id: ID partnera
            listing_id: ID oferty
            lead_data: Dane leadu (imię, telefon, email, wiadomość)
        
        Returns:
            Potwierdzenie przyjęcia leadu
        """
        partner = self.partners.get(partner_id)
        if not partner:
            return {'error': 'Partner not found'}
        
        # Zapisz lead
        lead_id = str(uuid.uuid4())
        
        partner.total_leads_received += 1
        
        logger.info(f"Lead received from partner {partner.name}: {lead_id}")
        
        return {
            'lead_id': lead_id,
            'status': 'received',
            'message': 'Dziękujemy za przesłanie leadu. Skontaktujemy się z klientem.',
        }
    
    async def report_transaction(
        self,
        partner_id: str,
        listing_id: str,
        transaction_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Zgłoś transakcję od partnera.
        
        Używane do rozliczeń prowizyjnych.
        """
        partner = self.partners.get(partner_id)
        if not partner:
            return {'error': 'Partner not found'}
        
        transaction_id = str(uuid.uuid4())
        
        # Oblicz prowizję
        sale_price = transaction_data.get('sale_price', 0)
        commission_percent = transaction_data.get('commission_percent', 2.0)
        total_commission = sale_price * (commission_percent / 100)
        partner_share = total_commission * (partner.commission_share_percent / 100)
        
        partner.total_transactions += 1
        
        logger.info(f"Transaction reported by partner {partner.name}: {transaction_id}")
        
        return {
            'transaction_id': transaction_id,
            'status': 'recorded',
            'commission': {
                'total': round(total_commission, 2),
                'partner_share': round(partner_share, 2),
                'our_share': round(total_commission - partner_share, 2),
            },
        }
    
    # ==========================================================================
    # Raporty i statystyki
    # ==========================================================================
    
    async def get_partner_stats(self, partner_id: str) -> Optional[Dict[str, Any]]:
        """Statystyki partnera"""
        partner = self.partners.get(partner_id)
        if not partner:
            return None
        
        return {
            'partner': partner.to_dict(),
            'performance': {
                'listings_shared': partner.total_listings_shared,
                'leads_received': partner.total_leads_received,
                'transactions': partner.total_transactions,
            },
            'commission': {
                'share_percent': partner.commission_share_percent,
            },
        }
    
    async def get_all_stats(self) -> Dict[str, Any]:
        """Statystyki wszystkich partnerów"""
        total = len(self.partners)
        active = len([p for p in self.partners.values() if p.status == PartnerStatus.ACTIVE])
        pending = len([p for p in self.partners.values() if p.status == PartnerStatus.PENDING])
        
        total_listings = sum(p.total_listings_shared for p in self.partners.values())
        total_leads = sum(p.total_leads_received for p in self.partners.values())
        total_transactions = sum(p.total_transactions for p in self.partners.values())
        
        return {
            'partners': {
                'total': total,
                'active': active,
                'pending': pending,
            },
            'activity': {
                'total_listings_shared': total_listings,
                'total_leads_received': total_leads,
                'total_transactions': total_transactions,
            },
        }
    
    # ==========================================================================
    # Metody prywatne
    # ==========================================================================
    
    def _generate_api_key(self) -> str:
        """Wygeneruj klucz API"""
        return f"pk_live_{secrets.token_urlsafe(32)}"
    
    def _generate_api_secret(self) -> str:
        """Wygeneruj sekret API"""
        return secrets.token_urlsafe(64)
    
    def _verify_secret(self, provided: str, stored: str) -> bool:
        """Weryfikuj sekret"""
        # W rzeczywistej implementacji: użyj bezpiecznego porównania
        return provided == stored
    
    async def _send_webhook(
        self,
        partner: Partner,
        event: str,
        data: Dict[str, Any],
    ):
        """Wyślij webhook do partnera"""
        if not partner.webhook_url:
            return
        
        # W rzeczywistej implementacji: wyślij HTTP POST
        logger.info(f"Webhook sent to {partner.name}: {event}")
    
    def _query_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Zapytanie do bazy ofert"""
        # W rzeczywistej implementacji
        return []


# Singleton
def get_partners_service(db_session: Session) -> PartnersAPIService:
    return PartnersAPIService(db_session)
