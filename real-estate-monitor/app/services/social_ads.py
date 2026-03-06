"""
Social Media Ads Service - Integracja Facebook/Instagram Ads

Automatyczne promowanie ofert na Facebooku i Instagramie.
Tworzenie kampanii, targetowanie, budżetowanie, raporty.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class AdPlatform(str, Enum):
    """Platforma reklamowa"""
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    BOTH = "both"


class CampaignStatus(str, Enum):
    """Status kampanii"""
    DRAFT = "draft"              # Szkic
    PENDING = "pending"          # Oczekuje na zatwierdzenie
    ACTIVE = "active"            # Aktywna
    PAUSED = "paused"            # Wstrzymana
    COMPLETED = "completed"      # Zakończona
    REJECTED = "rejected"        # Odrzucona


class CampaignObjective(str, Enum):
    """Cel kampanii"""
    REACH = "REACH"              # Zasięg
    TRAFFIC = "TRAFFIC"          # Ruch na stronę
    LEADS = "LEADS"              # Pozyskiwanie leadów
    CONVERSIONS = "CONVERSIONS"  # Konwersje
    ENGAGEMENT = "ENGAGEMENT"    # Zaangażowanie


@dataclass
class AdCampaign:
    """Kampania reklamowa"""
    id: str
    name: str
    
    # Powiązanie z ofertą
    listing_id: str
    listing_title: str
    
    # Platforma i cel
    platform: AdPlatform
    objective: CampaignObjective
    
    # Status
    status: CampaignStatus
    
    # Targetowanie
    targeting: Dict[str, Any]    # Lokalizacja, wiek, zainteresowania
    
    # Budżet
    budget_total: float          # Całkowity budżet
    budget_daily: Optional[float]  # Dzienny budżet
    currency: str
    
    # Harmonogram
    start_date: datetime
    end_date: Optional[datetime]
    
    # Treść
    headline: str
    description: str
    image_urls: List[str]
    call_to_action: str          # "Zobacz więcej", "Skontaktuj się", etc.
    
    # Linki
    destination_url: str
    utm_parameters: Dict[str, str]
    
    # Statystyki
    impressions: int
    clicks: int
    ctr: float                   # Click-through rate
    cpc: float                  # Cost per click
    spend: float                # Wydane środki
    leads: int                  # Liczba leadów
    
    # Daty
    created_at: datetime
    created_by: str
    updated_at: datetime
    
    # Zewnętrzne ID
    facebook_campaign_id: Optional[str]
    facebook_adset_id: Optional[str]
    facebook_ad_id: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'listing': {
                'id': self.listing_id,
                'title': self.listing_title,
            },
            'platform': self.platform.value,
            'objective': self.objective.value,
            'status': self.status.value,
            'targeting': self.targeting,
            'budget': {
                'total': self.budget_total,
                'daily': self.budget_daily,
                'currency': self.currency,
                'spent': self.spend,
            },
            'schedule': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat() if self.end_date else None,
            },
            'content': {
                'headline': self.headline,
                'description': self.description,
                'images': self.image_urls,
                'cta': self.call_to_action,
            },
            'stats': {
                'impressions': self.impressions,
                'clicks': self.clicks,
                'ctr': round(self.ctr, 4),
                'cpc': round(self.cpc, 2),
                'leads': self.leads,
            },
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class AdTemplate:
    """Szablon reklamy"""
    id: str
    name: str
    objective: CampaignObjective
    
    # Domyślne ustawienia
    default_targeting: Dict[str, Any]
    default_budget: float
    default_duration_days: int
    
    # Szablony tekstów
    headline_template: str
    description_template: str
    
    def generate_campaign(
        self,
        listing: Dict[str, Any],
        created_by: str,
    ) -> AdCampaign:
        """Wygeneruj kampanię z szablonu"""
        variables = {
            'title': listing.get('title', ''),
            'price': f"{listing.get('price', 0):,.0f}",
            'city': listing.get('city', ''),
            'district': listing.get('district', ''),
            'area': listing.get('area_sqm', ''),
            'rooms': listing.get('rooms', ''),
        }
        
        headline = self.headline_template.format(**variables)
        description = self.description_template.format(**variables)
        
        return AdCampaign(
            id=str(uuid.uuid4()),
            name=f"{self.name} - {listing.get('title', '')[:30]}",
            listing_id=listing.get('id', ''),
            listing_title=listing.get('title', ''),
            platform=AdPlatform.BOTH,
            objective=self.objective,
            status=CampaignStatus.DRAFT,
            targeting=self.default_targeting.copy(),
            budget_total=self.default_budget,
            budget_daily=self.default_budget / self.default_duration_days,
            currency="PLN",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=self.default_duration_days),
            headline=headline,
            description=description,
            image_urls=listing.get('images', []),
            call_to_action="Zobacz więcej",
            destination_url=listing.get('url', ''),
            utm_parameters={
                'utm_source': 'facebook',
                'utm_medium': 'paid_social',
                'utm_campaign': self.name.lower().replace(' ', '_'),
            },
            impressions=0,
            clicks=0,
            ctr=0.0,
            cpc=0.0,
            spend=0.0,
            leads=0,
            created_at=datetime.utcnow(),
            created_by=created_by,
            updated_at=datetime.utcnow(),
            facebook_campaign_id=None,
            facebook_adset_id=None,
            facebook_ad_id=None,
        )


# Predefiniowane szablony
AD_TEMPLATES = {
    'standard_sale': AdTemplate(
        id='standard_sale',
        name='Standardowa Sprzedaż',
        objective=CampaignObjective.TRAFFIC,
        default_targeting={
            'locations': [],  # Do uzupełnienia
            'age_min': 25,
            'age_max': 65,
            'interests': ['nieruchomości', 'mieszkania', 'domy'],
        },
        default_budget=500,
        default_duration_days=14,
        headline_template='{title}',
        description_template='Sprawdź tę wyjątkową ofertę! Cena: {price} zł, {city}. '
                            'Powierzchnia: {area} m², {rooms} pokoje. '
                            'Skontaktuj się z nami już dziś!',
    ),
    'premium_listing': AdTemplate(
        id='premium_listing',
        name='Premium Listing',
        objective=CampaignObjective.REACH,
        default_targeting={
            'locations': [],
            'age_min': 30,
            'age_max': 60,
            'interests': ['nieruchomości luksusowe', 'inwestycje'],
        },
        default_budget=1000,
        default_duration_days=21,
        headline_template='🏡 Luksusowa nieruchomość - {city}',
        description_template='Ekskluzywna oferta w {district}! '
                            'Cena: {price} zł. Nie przegap tej okazji!',
    ),
    'quick_sale': AdTemplate(
        id='quick_sale',
        name='Szybka Sprzedaż',
        objective=CampaignObjective.CONVERSIONS,
        default_targeting={
            'locations': [],
            'age_min': 25,
            'age_max': 55,
            'interests': ['okazje', 'nieruchomości'],
        },
        default_budget=300,
        default_duration_days=7,
        headline_template='🔥 OKAZJA! {title}',
        description_template='Nie przegap! Atrakcyjna cena: {price} zł. '
                            'Szybka sprzedaż - skontaktuj się teraz!',
    ),
    'rental': AdTemplate(
        id='rental',
        name='Wynajem',
        objective=CampaignObjective.LEADS,
        default_targeting={
            'locations': [],
            'age_min': 20,
            'age_max': 45,
            'interests': ['wynajem mieszkań', 'mieszkania'],
        },
        default_budget=400,
        default_duration_days=10,
        headline_template='Mieszkanie do wynajęcia - {city}',
        description_template='Szukasz mieszkania do wynajęcia? '
                            'Sprawdź: {area} m², {rooms} pokoje. '
                            'Zadzwoń i umów się na oglądanie!',
    ),
}


class SocialAdsService:
    """
    Serwis reklam social media.
    
    Zarządza kampaniami reklamowymi na Facebooku i Instagramie.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.facebook_api_key = None  # Wczytaj z konfiguracji
    
    async def create_campaign(
        self,
        listing_id: str,
        listing_data: Dict[str, Any],
        template_id: str,
        created_by: str,
        custom_budget: Optional[float] = None,
        custom_targeting: Optional[Dict[str, Any]] = None,
    ) -> AdCampaign:
        """
        Utwórz kampanię reklamową.
        
        Args:
            listing_id: ID oferty
            listing_data: Dane oferty
            template_id: ID szablonu
            created_by: ID twórcy
            custom_budget: Niestandardowy budżet
            custom_targeting: Niestandardowe targetowanie
        """
        template = AD_TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        campaign = template.generate_campaign(listing_data, created_by)
        
        # Nadpisz customowe wartości
        if custom_budget:
            campaign.budget_total = custom_budget
            campaign.budget_daily = custom_budget / template.default_duration_days
        
        if custom_targeting:
            campaign.targeting.update(custom_targeting)
        
        # Zapisz w bazie
        self._save_campaign(campaign)
        
        logger.info(f"Campaign created: {campaign.id} for listing {listing_id}")
        
        return campaign
    
    async def publish_campaign(self, campaign_id: str) -> Optional[AdCampaign]:
        """Opublikuj kampanię na Facebooku"""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None
        
        # W rzeczywistej implementacji: wywołanie Facebook Ads API
        # campaign.facebook_campaign_id = await self._create_fb_campaign(campaign)
        
        campaign.status = CampaignStatus.PENDING
        campaign.updated_at = datetime.utcnow()
        
        self._update_campaign(campaign)
        
        logger.info(f"Campaign {campaign_id} published to Facebook")
        
        return campaign
    
    async def pause_campaign(self, campaign_id: str) -> Optional[AdCampaign]:
        """Wstrzymaj kampanię"""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None
        
        # W rzeczywistej implementacji: wywołanie Facebook Ads API
        
        campaign.status = CampaignStatus.PAUSED
        campaign.updated_at = datetime.utcnow()
        
        self._update_campaign(campaign)
        
        logger.info(f"Campaign {campaign_id} paused")
        
        return campaign
    
    async def resume_campaign(self, campaign_id: str) -> Optional[AdCampaign]:
        """Wznów kampanię"""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None
        
        campaign.status = CampaignStatus.ACTIVE
        campaign.updated_at = datetime.utcnow()
        
        self._update_campaign(campaign)
        
        return campaign
    
    async def stop_campaign(self, campaign_id: str) -> Optional[AdCampaign]:
        """Zatrzymaj kampanię"""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None
        
        # W rzeczywistej implementacji: wywołanie Facebook Ads API
        
        campaign.status = CampaignStatus.COMPLETED
        campaign.end_date = datetime.utcnow()
        campaign.updated_at = datetime.utcnow()
        
        self._update_campaign(campaign)
        
        logger.info(f"Campaign {campaign_id} stopped")
        
        return campaign
    
    async def get_campaigns(
        self,
        listing_id: Optional[str] = None,
        status: Optional[CampaignStatus] = None,
        platform: Optional[AdPlatform] = None,
        created_by: Optional[str] = None,
        limit: int = 50,
    ) -> List[AdCampaign]:
        """Pobierz kampanie z filtrami"""
        return self._query_campaigns(
            listing_id=listing_id,
            status=status,
            platform=platform,
            created_by=created_by,
            limit=limit,
        )
    
    async def get_campaign_stats(
        self,
        campaign_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Pobierz statystyki kampanii"""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None
        
        # W rzeczywistej implementacji: pobierz aktualne dane z Facebook API
        
        return {
            'campaign_id': campaign_id,
            'status': campaign.status.value,
            'impressions': campaign.impressions,
            'clicks': campaign.clicks,
            'ctr': round(campaign.ctr, 4),
            'cpc': round(campaign.cpc, 2),
            'spend': round(campaign.spend, 2),
            'leads': campaign.leads,
            'budget_remaining': round(campaign.budget_total - campaign.spend, 2),
        }
    
    async def update_campaign_budget(
        self,
        campaign_id: str,
        new_budget: float,
    ) -> Optional[AdCampaign]:
        """Zaktualizuj budżet kampanii"""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None
        
        campaign.budget_total = new_budget
        campaign.updated_at = datetime.utcnow()
        
        self._update_campaign(campaign)
        
        logger.info(f"Campaign {campaign_id} budget updated to {new_budget}")
        
        return campaign
    
    async def get_templates(self) -> List[Dict[str, Any]]:
        """Pobierz dostępne szablony"""
        return [
            {
                'id': t.id,
                'name': t.name,
                'objective': t.objective.value,
                'default_budget': t.default_budget,
                'default_duration_days': t.default_duration_days,
            }
            for t in AD_TEMPLATES.values()
        ]
    
    async def get_recommendations(
        self,
        listing: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pobierz rekomendacje kampanii dla oferty"""
        price = listing.get('price', 0)
        
        # Rekomenduj szablon na podstawie ceny
        if price > 1000000:
            recommended_template = 'premium_listing'
            recommended_budget = 1000
        elif price < 300000:
            recommended_template = 'quick_sale'
            recommended_budget = 300
        else:
            recommended_template = 'standard_sale'
            recommended_budget = 500
        
        # Rekomenduj targetowanie
        city = listing.get('city', '')
        district = listing.get('district', '')
        
        return {
            'recommended_template': recommended_template,
            'recommended_budget': recommended_budget,
            'recommended_duration_days': 14,
            'targeting': {
                'locations': [city] if city else [],
                'age_min': 25,
                'age_max': 65,
            },
            'expected_results': {
                'estimated_reach': int(recommended_budget * 20),  # ~20 osób/zł
                'estimated_clicks': int(recommended_budget * 0.5),  # ~0.5 kliknięcia/zł
                'estimated_cpc': 2.0,
            },
        }
    
    async def sync_stats(self, campaign_id: str) -> Optional[AdCampaign]:
        """Zsynchronizuj statystyki z Facebook"""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None
        
        # W rzeczywistej implementacji: pobierz dane z Facebook Ads API
        
        return campaign
    
    # ==========================================================================
    # Metody pomocnicze
    # ==========================================================================
    
    def _save_campaign(self, campaign: AdCampaign):
        """Zapisz kampanię do bazy"""
        pass
    
    def _get_campaign(self, campaign_id: str) -> Optional[AdCampaign]:
        """Pobierz kampanię z bazy"""
        return None
    
    def _update_campaign(self, campaign: AdCampaign):
        """Zaktualizuj kampanię"""
        pass
    
    def _query_campaigns(
        self,
        listing_id: Optional[str] = None,
        status: Optional[CampaignStatus] = None,
        platform: Optional[AdPlatform] = None,
        created_by: Optional[str] = None,
        limit: int = 50,
    ) -> List[AdCampaign]:
        """Zapytanie do bazy kampanii"""
        return []
    
    async def _create_fb_campaign(self, campaign: AdCampaign) -> str:
        """Utwórz kampanię w Facebook Ads API"""
        # W rzeczywistej implementacji
        return "fb_campaign_id"


# Singleton
def get_social_ads_service(db_session: Session) -> SocialAdsService:
    return SocialAdsService(db_session)
