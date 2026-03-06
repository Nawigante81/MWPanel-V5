"""
Competitor Monitoring Service - Monitoring Konkurencji

Śledzenie ofert konkurencyjnych biur, analiza cen,
wykrywanie zmian i generowanie alertów.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.core.logging import get_logger

logger = get_logger(__name__)


class CompetitorStatus(str, Enum):
    """Status konkurenta"""
    ACTIVE = "active"              # Aktywny monitoring
    PAUSED = "paused"              # Wstrzymany
    INACTIVE = "inactive"          # Nieaktywny


class PriceChangeType(str, Enum):
    """Typ zmiany ceny"""
    INCREASE = "increase"          # Podwyżka
    DECREASE = "decrease"          # Obniżka
    UNCHANGED = "unchanged"        # Bez zmian


@dataclass
class CompetitorListing:
    """Oferta konkurenta"""
    id: str
    competitor_id: str
    external_id: str               # ID z portalu
    
    # Dane oferty
    title: str
    address: str
    city: str
    district: str
    price: float
    area_sqm: Optional[float]
    rooms: Optional[int]
    
    # URL
    source_url: str
    source_portal: str             # otodom, olx, etc.
    
    # Status
    is_active: bool
    first_seen_at: datetime
    last_seen_at: datetime
    last_price_change_at: Optional[datetime]
    
    # Historia cen
    price_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'address': self.address,
            'city': self.city,
            'district': self.district,
            'price': self.price,
            'area_sqm': self.area_sqm,
            'rooms': self.rooms,
            'source_url': self.source_url,
            'source_portal': self.source_portal,
            'is_active': self.is_active,
            'first_seen_at': self.first_seen_at.isoformat(),
            'last_seen_at': self.last_seen_at.isoformat(),
            'price_history': self.price_history,
        }


@dataclass
class MarketAnalysis:
    """Analiza rynku w danej lokalizacji"""
    city: str
    district: Optional[str]
    property_type: str
    
    # Statystyki
    total_listings: int
    avg_price: float
    avg_price_per_sqm: float
    median_price: float
    min_price: float
    max_price: float
    
    # Nasze oferty vs konkurencja
    our_listings_count: int
    our_avg_price: float
    competitor_avg_price: float
    price_difference_percent: float
    
    # Trend
    price_trend_percent: float      # Zmiana w ciągu miesiąca
    new_listings_this_week: int
    sold_listings_this_week: int
    
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'location': {
                'city': self.city,
                'district': self.district,
            },
            'property_type': self.property_type,
            'market_stats': {
                'total_listings': self.total_listings,
                'avg_price': round(self.avg_price, 2),
                'avg_price_per_sqm': round(self.avg_price_per_sqm, 2),
                'median_price': round(self.median_price, 2),
                'min_price': round(self.min_price, 2),
                'max_price': round(self.max_price, 2),
            },
            'comparison': {
                'our_listings': self.our_listings_count,
                'our_avg_price': round(self.our_avg_price, 2),
                'competitor_avg_price': round(self.competitor_avg_price, 2),
                'price_difference_percent': round(self.price_difference_percent, 2),
            },
            'trend': {
                'price_change_percent': round(self.price_trend_percent, 2),
                'new_this_week': self.new_listings_this_week,
                'sold_this_week': self.sold_listings_this_week,
            },
            'generated_at': self.generated_at.isoformat(),
        }


class CompetitorMonitoringService:
    """
    Serwis monitorowania konkurencji.
    
    Śledzi oferty innych biur w tych samych lokalizacjach,
    analizuje zmiany cen i generuje raporty porównawcze.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def track_competitor_listing(
        self,
        competitor_id: str,
        external_id: str,
        title: str,
        address: str,
        city: str,
        district: str,
        price: float,
        area_sqm: Optional[float],
        rooms: Optional[int],
        source_url: str,
        source_portal: str
    ) -> Dict[str, Any]:
        """
        Zarejestruj lub zaktualizuj ofertę konkurenta.
        
        Returns:
            Dict z informacją czy to nowa oferta, zmiana ceny, itp.
        """
        # Sprawdź czy oferta już istnieje
        existing = self.db.query(CompetitorListing).filter(
            CompetitorListing.external_id == external_id,
            CompetitorListing.source_portal == source_portal
        ).first()
        
        now = datetime.utcnow()
        
        if existing:
            # Aktualizuj istniejącą
            result = {
                'action': 'updated',
                'listing_id': str(existing.id),
                'price_changed': False,
                'old_price': existing.price,
                'new_price': price,
            }
            
            # Sprawdź zmianę ceny
            if existing.price != price:
                change_type = PriceChangeType.INCREASE if price > existing.price else PriceChangeType.DECREASE
                change_percent = abs(price - existing.price) / existing.price * 100
                
                # Zapisz historię
                if not existing.price_history:
                    existing.price_history = []
                
                existing.price_history.append({
                    'price': existing.price,
                    'changed_at': existing.last_seen_at.isoformat(),
                })
                
                existing.price = price
                existing.last_price_change_at = now
                
                result['price_changed'] = True
                result['price_change_type'] = change_type.value
                result['price_change_percent'] = round(change_percent, 2)
                
                logger.info(f"Competitor price change: {existing.title} - {change_type.value} {change_percent:.1f}%")
            
            existing.last_seen_at = now
            existing.is_active = True
            
            self.db.commit()
            return result
        
        else:
            # Nowa oferta
            new_listing = CompetitorListing(
                id=str(uuid.uuid4()),
                competitor_id=competitor_id,
                external_id=external_id,
                title=title,
                address=address,
                city=city,
                district=district,
                price=price,
                area_sqm=area_sqm,
                rooms=rooms,
                source_url=source_url,
                source_portal=source_portal,
                is_active=True,
                first_seen_at=now,
                last_seen_at=now,
            )
            
            self.db.add(new_listing)
            self.db.commit()
            
            logger.info(f"New competitor listing tracked: {title}")
            
            return {
                'action': 'created',
                'listing_id': str(new_listing.id),
                'price_changed': False,
            }
    
    async def mark_as_sold(
        self,
        external_id: str,
        source_portal: str,
        sold_price: Optional[float] = None
    ) -> bool:
        """Oznacz ofertę konkurenta jako sprzedaną"""
        listing = self.db.query(CompetitorListing).filter(
            CompetitorListing.external_id == external_id,
            CompetitorListing.source_portal == source_portal
        ).first()
        
        if not listing:
            return False
        
        listing.is_active = False
        if sold_price:
            listing.price_history.append({
                'price': sold_price,
                'changed_at': datetime.utcnow().isoformat(),
                'status': 'sold'
            })
        
        self.db.commit()
        
        logger.info(f"Competitor listing marked as sold: {listing.title}")
        return True
    
    async def get_market_analysis(
        self,
        city: str,
        district: Optional[str] = None,
        property_type: str = "apartment",
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        min_rooms: Optional[int] = None,
        max_rooms: Optional[int] = None,
        organization_id: Optional[str] = None
    ) -> MarketAnalysis:
        """Generuj analizę rynku dla danej lokalizacji"""
        # Pobierz oferty konkurentów
        query = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == city,
            CompetitorListing.is_active == True
        )
        
        if district:
            query = query.filter(CompetitorListing.district == district)
        
        if min_area:
            query = query.filter(CompetitorListing.area_sqm >= min_area)
        if max_area:
            query = query.filter(CompetitorListing.area_sqm <= max_area)
        
        if min_rooms:
            query = query.filter(CompetitorListing.rooms >= min_rooms)
        if max_rooms:
            query = query.filter(CompetitorListing.rooms <= max_rooms)
        
        competitor_listings = query.all()
        
        # Pobierz nasze oferty
        from app.services.listing_management import Listing, ListingStatus
        
        our_query = self.db.query(Listing).filter(
            Listing.city == city,
            Listing.status == ListingStatus.ACTIVE
        )
        
        if district:
            our_query = our_query.filter(Listing.district == district)
        
        if organization_id:
            our_query = our_query.filter(Listing.organization_id == organization_id)
        
        our_listings = our_query.all()
        
        # Oblicz statystyki
        total_listings = len(competitor_listings) + len(our_listings)
        
        all_prices = [l.price for l in competitor_listings] + [l.price for l in our_listings]
        all_prices_per_sqm = []
        
        for l in competitor_listings:
            if l.area_sqm and l.area_sqm > 0:
                all_prices_per_sqm.append(l.price / l.area_sqm)
        
        for l in our_listings:
            if l.area_sqm and l.area_sqm > 0:
                all_prices_per_sqm.append(l.price / l.area_sqm)
        
        if all_prices:
            avg_price = sum(all_prices) / len(all_prices)
            median_price = sorted(all_prices)[len(all_prices) // 2]
            min_price = min(all_prices)
            max_price = max(all_prices)
        else:
            avg_price = median_price = min_price = max_price = 0
        
        avg_price_per_sqm = sum(all_prices_per_sqm) / len(all_prices_per_sqm) if all_prices_per_sqm else 0
        
        # Nasze statystyki
        our_avg_price = sum(l.price for l in our_listings) / len(our_listings) if our_listings else 0
        competitor_avg_price = sum(l.price for l in competitor_listings) / len(competitor_listings) if competitor_listings else 0
        
        price_diff = ((our_avg_price - competitor_avg_price) / competitor_avg_price * 100) if competitor_avg_price > 0 else 0
        
        # Trend (porównanie z miesiącem temu)
        month_ago = datetime.utcnow() - timedelta(days=30)
        old_listings = [l for l in competitor_listings if l.first_seen_at < month_ago]
        
        if old_listings:
            old_avg = sum(l.price for l in old_listings) / len(old_listings)
            trend = ((competitor_avg_price - old_avg) / old_avg * 100) if old_avg > 0 else 0
        else:
            trend = 0
        
        # Nowe oferty w tym tygodniu
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_this_week = sum(1 for l in competitor_listings if l.first_seen_at >= week_ago)
        
        # Sprzedane w tym tygodniu (te które zniknęły)
        recently_inactive = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == city,
            CompetitorListing.is_active == False,
            CompetitorListing.last_seen_at >= week_ago
        ).count()
        
        return MarketAnalysis(
            city=city,
            district=district,
            property_type=property_type,
            total_listings=total_listings,
            avg_price=avg_price,
            avg_price_per_sqm=avg_price_per_sqm,
            median_price=median_price,
            min_price=min_price,
            max_price=max_price,
            our_listings_count=len(our_listings),
            our_avg_price=our_avg_price,
            competitor_avg_price=competitor_avg_price,
            price_difference_percent=price_diff,
            price_trend_percent=trend,
            new_listings_this_week=new_this_week,
            sold_listings_this_week=recently_inactive
        )
    
    async def get_price_alerts(
        self,
        organization_id: str,
        days: int = 7,
        min_change_percent: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Pobierz alerty o zmianach cen konkurentów"""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Pobierz oferty ze zmianą ceny
        listings = self.db.query(CompetitorListing).filter(
            CompetitorListing.last_price_change_at >= since,
            CompetitorListing.is_active == True
        ).all()
        
        alerts = []
        for listing in listings:
            if len(listing.price_history) >= 1:
                old_price = listing.price_history[-1]['price']
                change_percent = abs(listing.price - old_price) / old_price * 100
                
                if change_percent >= min_change_percent:
                    alerts.append({
                        'listing_id': str(listing.id),
                        'title': listing.title,
                        'address': listing.address,
                        'old_price': old_price,
                        'new_price': listing.price,
                        'change_percent': round(change_percent, 2),
                        'change_type': 'increase' if listing.price > old_price else 'decrease',
                        'changed_at': listing.last_price_change_at.isoformat(),
                        'source_url': listing.source_url,
                    })
        
        # Sortuj po % zmiany
        alerts.sort(key=lambda x: x['change_percent'], reverse=True)
        
        return alerts
    
    async def compare_with_our_listing(
        self,
        our_listing_id: uuid.UUID,
        radius_km: float = 1.0
    ) -> Dict[str, Any]:
        """Porównaj naszą ofertę z konkurencją w okolicy"""
        from app.services.listing_management import ListingManagementService
        
        service = ListingManagementService(self.db)
        our_listing = await service.get_listing(our_listing_id)
        
        if not our_listing:
            return {'error': 'Listing not found'}
        
        # Pobierz konkurencyjne oferty w podobnej lokalizacji
        competitor_listings = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == our_listing.city,
            CompetitorListing.district == our_listing.district,
            CompetitorListing.is_active == True
        ).all()
        
        # Filtruj po podobnej powierzchni (±20%)
        if our_listing.area_sqm:
            similar = [
                l for l in competitor_listings
                if l.area_sqm and abs(l.area_sqm - our_listing.area_sqm) / our_listing.area_sqm <= 0.2
            ]
        else:
            similar = competitor_listings
        
        if not similar:
            return {
                'our_listing': {
                    'id': str(our_listing.id),
                    'title': our_listing.title,
                    'price': our_listing.price,
                    'price_per_sqm': our_listing.price / our_listing.area_sqm if our_listing.area_sqm else None,
                },
                'competitors': [],
                'comparison': {
                    'avg_competitor_price': None,
                    'price_difference_percent': None,
                    'recommendation': 'Brak podobnych ofert konkurencji w tej lokalizacji.'
                }
            }
        
        # Oblicz średnie
        avg_price = sum(l.price for l in similar) / len(similar)
        avg_price_per_sqm = sum(l.price / l.area_sqm for l in similar if l.area_sqm) / len([l for l in similar if l.area_sqm])
        
        our_price_per_sqm = our_listing.price / our_listing.area_sqm if our_listing.area_sqm else 0
        
        price_diff = ((our_listing.price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        
        # Rekomendacja
        if price_diff > 10:
            recommendation = f"Nasza cena jest o {price_diff:.1f}% wyższa niż średnia konkurencji. Rozważ obniżkę."
        elif price_diff < -10:
            recommendation = f"Nasza cena jest o {abs(price_diff):.1f}% niższa niż średnia. To może być okazja!"
        else:
            recommendation = "Nasza cena jest konkurencyjna w porównaniu do rynku."
        
        return {
            'our_listing': {
                'id': str(our_listing.id),
                'title': our_listing.title,
                'price': our_listing.price,
                'price_per_sqm': round(our_price_per_sqm, 2) if our_price_per_sqm else None,
            },
            'competitors': [
                {
                    'id': str(l.id),
                    'title': l.title,
                    'price': l.price,
                    'price_per_sqm': round(l.price / l.area_sqm, 2) if l.area_sqm else None,
                    'source_url': l.source_url,
                }
                for l in similar[:5]
            ],
            'comparison': {
                'avg_competitor_price': round(avg_price, 2),
                'avg_competitor_price_per_sqm': round(avg_price_per_sqm, 2),
                'price_difference_percent': round(price_diff, 2),
                'competitor_count': len(similar),
                'recommendation': recommendation
            }
        }
    
    async def get_competitor_activity_report(
        self,
        city: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Raport aktywności konkurencji"""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Nowe oferty
        new_listings = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == city,
            CompetitorListing.first_seen_at >= since
        ).count()
        
        # Zmiany cen
        price_changes = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == city,
            CompetitorListing.last_price_change_at >= since
        ).count()
        
        # Obniżki cen
        price_decreases = []
        listings_with_changes = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == city,
            CompetitorListing.last_price_change_at >= since
        ).all()
        
        for listing in listings_with_changes:
            if len(listing.price_history) >= 1:
                old_price = listing.price_history[-1]['price']
                if listing.price < old_price:
                    price_decreases.append({
                        'title': listing.title,
                        'old_price': old_price,
                        'new_price': listing.price,
                        'decrease_percent': round((old_price - listing.price) / old_price * 100, 2)
                    })
        
        # Sprzedane (zniknęłe)
        sold = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == city,
            CompetitorListing.is_active == False,
            CompetitorListing.last_seen_at >= since
        ).count()
        
        # Aktywne oferty
        active = self.db.query(CompetitorListing).filter(
            CompetitorListing.city == city,
            CompetitorListing.is_active == True
        ).count()
        
        return {
            'period_days': days,
            'city': city,
            'new_listings': new_listings,
            'price_changes': price_changes,
            'price_decreases': len(price_decreases),
            'biggest_decreases': sorted(price_decreases, key=lambda x: x['decrease_percent'], reverse=True)[:5],
            'sold_or_withdrawn': sold,
            'currently_active': active,
        }
