"""
Auto-Matching Service - Inteligentne Parowanie Ofert z Klientami

Automatyczne dopasowywanie nowych ofert do zapisanych preferencji klientów.
Powiadomienia agentów o idealnych dopasowaniach.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import uuid
from enum import Enum

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Offer, Search, Lead

logger = get_logger(__name__)


class MatchScoreLevel(str, Enum):
    """Poziom dopasowania"""
    PERFECT = "perfect"        # 95-100%
    EXCELLENT = "excellent"    # 85-94%
    GOOD = "good"              # 70-84%
    FAIR = "fair"              # 55-69%
    POOR = "poor"              # <55%


@dataclass
class MatchCriteria:
    """Kryteria dopasowania"""
    # Lokalizacja
    cities: List[str] = field(default_factory=list)
    districts: List[str] = field(default_factory=list)
    max_distance_km: Optional[float] = None
    
    # Cena
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    price_per_sqm_max: Optional[float] = None
    
    # Parametry
    property_types: List[str] = field(default_factory=list)
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_floor: Optional[int] = None
    max_floor: Optional[int] = None
    
    # Udogodnienia
    must_have: List[str] = field(default_factory=list)  # balcony, parking, elevator, garden
    nice_to_have: List[str] = field(default_factory=list)
    
    # Inne
    offer_type: str = "sale"  # sale, rent
    build_year_min: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cities': self.cities,
            'districts': self.districts,
            'price_range': [self.min_price, self.max_price],
            'area_range': [self.min_area, self.max_area],
            'rooms_range': [self.min_rooms, self.max_rooms],
            'must_have': self.must_have,
        }


@dataclass
class MatchResult:
    """Wynik dopasowania oferty do klienta"""
    offer_id: str
    client_id: str
    client_name: str
    agent_id: str
    
    total_score: float  # 0-100
    score_level: str
    
    # Szczegóły dopasowania
    location_match: float
    price_match: float
    size_match: float
    rooms_match: float
    features_match: float
    
    # Informacje o ofercie
    offer_title: str
    offer_price: float
    offer_city: str
    offer_area: Optional[float]
    offer_rooms: Optional[int]
    
    # Dlaczego pasuje
    matching_points: List[str] = field(default_factory=list)
    missing_points: List[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'offer_id': self.offer_id,
            'client_id': self.client_id,
            'client_name': self.client_name,
            'agent_id': self.agent_id,
            'score': {
                'total': round(self.total_score, 1),
                'level': self.score_level,
            },
            'details': {
                'location': round(self.location_match, 1),
                'price': round(self.price_match, 1),
                'size': round(self.size_match, 1),
                'rooms': round(self.rooms_match, 1),
                'features': round(self.features_match, 1),
            },
            'offer': {
                'title': self.offer_title,
                'price': self.offer_price,
                'city': self.offer_city,
                'area': self.offer_area,
                'rooms': self.offer_rooms,
            },
            'matching_points': self.matching_points,
            'missing_points': self.missing_points,
        }


class AutoMatchingService:
    """
    Serwis automatycznego dopasowywania ofert do klientów.
    """
    
    # Wagi kryteriów
    WEIGHTS = {
        'location': 0.25,
        'price': 0.25,
        'size': 0.15,
        'rooms': 0.15,
        'features': 0.10,
        'other': 0.10,
    }
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def find_matches_for_offer(
        self,
        offer_id: str,
        min_score: float = 60.0,
        limit: int = 20
    ) -> List[MatchResult]:
        """
        Znajdź wszystkich klientów, którym pasuje dana oferta.
        
        Returns:
            Lista dopasowań posortowana od najlepszego
        """
        # Pobierz ofertę
        offer = self.db.query(Offer).filter(Offer.id == offer_id).first()
        if not offer:
            logger.warning(f"Offer {offer_id} not found")
            return []
        
        # Pobierz wszystkich aktywnych klientów z preferencjami
        active_clients = self.db.query(Lead).filter(
            Lead.status.notin_(['closed_won', 'closed_lost', 'disqualified']),
            Lead.assigned_agent_id.isnot(None)
        ).all()
        
        matches = []
        
        for client in active_clients:
            # Pobierz preferencje klienta (z ostatniego wyszukiwania lub leadu)
            criteria = await self._get_client_criteria(client)
            
            if not criteria:
                continue
            
            # Oblicz dopasowanie
            match = await self._calculate_match(offer, client, criteria)
            
            if match and match.total_score >= min_score:
                matches.append(match)
        
        # Sortuj po wyniku
        matches.sort(key=lambda x: x.total_score, reverse=True)
        
        return matches[:limit]
    
    async def find_matches_for_client(
        self,
        client_id: str,
        min_score: float = 60.0,
        limit: int = 20,
        max_age_days: int = 7
    ) -> List[MatchResult]:
        """
        Znajdź oferty pasujące do preferencji klienta.
        
        Returns:
            Lista dopasowań posortowana od najlepszego
        """
        # Pobierz klienta
        client = self.db.query(Lead).filter(Lead.id == client_id).first()
        if not client:
            return []
        
        # Pobierz preferencje
        criteria = await self._get_client_criteria(client)
        if not criteria:
            return []
        
        # Pobierz nowe oferty
        since = datetime.utcnow() - timedelta(days=max_age_days)
        
        offers = self.db.query(Offer).filter(
            Offer.created_at >= since,
            Offer.is_active == True
        ).order_by(Offer.created_at.desc()).limit(200).all()
        
        matches = []
        
        for offer in offers:
            match = await self._calculate_match(offer, client, criteria)
            
            if match and match.total_score >= min_score:
                matches.append(match)
        
        matches.sort(key=lambda x: x.total_score, reverse=True)
        
        return matches[:limit]
    
    async def _get_client_criteria(self, client: Lead) -> Optional[MatchCriteria]:
        """Pobierz kryteria wyszukiwania klienta"""
        # Sprawdź czy klient ma zapisane preferencje w leadzie
        if client.requirements_notes:
            # Parsuj preferencje z notatek (w produkcji: strukturalne dane)
            pass
        
        # Pobierz ostatnie wyszukiwanie klienta
        from app.db.models import UserSearch
        
        last_search = self.db.query(UserSearch).filter(
            UserSearch.user_id == client.assigned_agent_id  # Agent wyszukiwał dla klienta
        ).order_by(UserSearch.created_at.desc()).first()
        
        if last_search and last_search.search:
            search = last_search.search
            
            return MatchCriteria(
                cities=[search.city] if search.city else [],
                districts=[search.district] if search.district else [],
                min_price=search.min_price,
                max_price=search.max_price,
                property_types=[search.property_type.value] if search.property_type else [],
                min_area=search.min_area,
                max_area=search.max_area,
                min_rooms=search.min_rooms,
                max_rooms=search.max_rooms,
                offer_type=search.offer_type.value if search.offer_type else 'sale',
            )
        
        # Fallback: utwórz kryteria z leadu
        return MatchCriteria(
            cities=[client.preferred_location] if client.preferred_location else [],
            min_price=client.budget_min,
            max_price=client.budget_max,
            min_rooms=client.min_rooms,
            max_rooms=client.max_rooms,
        )
    
    async def _calculate_match(
        self,
        offer: Offer,
        client: Lead,
        criteria: MatchCriteria
    ) -> Optional[MatchResult]:
        """Oblicz wynik dopasowania"""
        matching_points = []
        missing_points = []
        
        # 1. Dopasowanie lokalizacji (25%)
        location_score = await self._calculate_location_match(offer, criteria)
        if criteria.cities and offer.city in criteria.cities:
            matching_points.append(f"Miasto: {offer.city}")
        elif criteria.cities:
            missing_points.append(f"Miasto: {offer.city} (oczekiwano: {', '.join(criteria.cities)})")
        
        if criteria.districts and offer.district in criteria.districts:
            matching_points.append(f"Dzielnica: {offer.district}")
        
        # 2. Dopasowanie ceny (25%)
        price_score = await self._calculate_price_match(offer, criteria)
        if price_score >= 90:
            matching_points.append(f"Cena: {offer.price:,.0f} PLN - idealna")
        elif price_score >= 70:
            matching_points.append(f"Cena: {offer.price:,.0f} PLN - w zakresie")
        elif criteria.max_price and offer.price > criteria.max_price:
            diff = ((offer.price - criteria.max_price) / criteria.max_price * 100)
            missing_points.append(f"Cena o {diff:.0f}% powyżej budżetu")
        
        # 3. Dopasowanie powierzchni (15%)
        size_score = await self._calculate_size_match(offer, criteria)
        if offer.area_sqm:
            if criteria.min_area and offer.area_sqm >= criteria.min_area:
                matching_points.append(f"Powierzchnia: {offer.area_sqm} m²")
            elif criteria.max_area and offer.area_sqm <= criteria.max_area:
                matching_points.append(f"Powierzchnia: {offer.area_sqm} m²")
        
        # 4. Dopasowanie pokoi (15%)
        rooms_score = await self._calculate_rooms_match(offer, criteria)
        if offer.rooms:
            if criteria.min_rooms and offer.rooms >= criteria.min_rooms:
                matching_points.append(f"Pokoje: {offer.rooms}")
            if criteria.max_rooms and offer.rooms <= criteria.max_rooms:
                matching_points.append(f"Pokoje: {offer.rooms} (w zakresie)")
        
        # 5. Dopasowanie udogodnień (10%)
        features_score = await self._calculate_features_match(offer, criteria)
        if criteria.must_have:
            for feature in criteria.must_have:
                has_feature = getattr(offer, f'has_{feature}', False)
                if has_feature:
                    matching_points.append(f"✓ {feature}")
                else:
                    missing_points.append(f"✗ Brak: {feature}")
        
        # 6. Inne (10%)
        other_score = 100.0
        if criteria.build_year_min and offer.build_year:
            if offer.build_year >= criteria.build_year_min:
                matching_points.append(f"Rok budowy: {offer.build_year}")
            else:
                other_score *= 0.8
                missing_points.append(f"Starszy budynek ({offer.build_year})")
        
        # Oblicz całkowity wynik
        total_score = (
            location_score * self.WEIGHTS['location'] +
            price_score * self.WEIGHTS['price'] +
            size_score * self.WEIGHTS['size'] +
            rooms_score * self.WEIGHTS['rooms'] +
            features_score * self.WEIGHTS['features'] +
            other_score * self.WEIGHTS['other']
        )
        
        # Określ poziom
        if total_score >= 95:
            level = MatchScoreLevel.PERFECT
        elif total_score >= 85:
            level = MatchScoreLevel.EXCELLENT
        elif total_score >= 70:
            level = MatchScoreLevel.GOOD
        elif total_score >= 55:
            level = MatchScoreLevel.FAIR
        else:
            level = MatchScoreLevel.POOR
        
        return MatchResult(
            offer_id=str(offer.id),
            client_id=str(client.id),
            client_name=f"{client.first_name} {client.last_name}",
            agent_id=client.assigned_agent_id,
            total_score=total_score,
            score_level=level.value,
            location_match=location_score,
            price_match=price_score,
            size_match=size_score,
            rooms_match=rooms_score,
            features_match=features_score,
            offer_title=offer.title or "",
            offer_price=offer.price or 0,
            offer_city=offer.city or "",
            offer_area=offer.area_sqm,
            offer_rooms=offer.rooms,
            matching_points=matching_points,
            missing_points=missing_points
        )
    
    async def _calculate_location_match(self, offer: Offer, criteria: MatchCriteria) -> float:
        """Oblicz dopasowanie lokalizacji (0-100)"""
        if not criteria.cities:
            return 100.0
        
        if offer.city in criteria.cities:
            # Sprawdź dzielnicę
            if criteria.districts and offer.district:
                if offer.district in criteria.districts:
                    return 100.0
                else:
                    return 80.0  # Dobre miasto, zła dzielnica
            return 90.0  # Dobre miasto, bez preferencji dzielnicy
        
        # Złe miasto
        return 0.0
    
    async def _calculate_price_match(self, offer: Offer, criteria: MatchCriteria) -> float:
        """Oblicz dopasowanie ceny (0-100)"""
        if offer.price is None:
            return 50.0
        
        price = offer.price
        
        # Sprawdź czy cena w zakresie
        if criteria.min_price and criteria.max_price:
            if criteria.min_price <= price <= criteria.max_price:
                return 100.0
            elif price < criteria.min_price:
                # Poniżej budżetu - dobrze!
                diff = (criteria.min_price - price) / criteria.min_price
                return max(70, 100 - diff * 30)
            else:
                # Powyżej budżetu
                diff = (price - criteria.max_price) / criteria.max_price
                return max(0, 100 - diff * 100)
        
        elif criteria.max_price:
            if price <= criteria.max_price:
                return 100.0
            else:
                diff = (price - criteria.max_price) / criteria.max_price
                return max(0, 100 - diff * 100)
        
        elif criteria.min_price:
            if price >= criteria.min_price:
                return 100.0
            else:
                return 80.0  # Poniżej oczekiwań ale może być ok
        
        return 100.0  # Brak preferencji
    
    async def _calculate_size_match(self, offer: Offer, criteria: MatchCriteria) -> float:
        """Oblicz dopasowanie powierzchni (0-100)"""
        if offer.area_sqm is None:
            return 50.0
        
        area = offer.area_sqm
        
        if criteria.min_area and criteria.max_area:
            if criteria.min_area <= area <= criteria.max_area:
                return 100.0
            elif area < criteria.min_area:
                diff = (criteria.min_area - area) / criteria.min_area
                return max(40, 100 - diff * 100)
            else:
                diff = (area - criteria.max_area) / criteria.max_area
                return max(50, 100 - diff * 50)
        
        elif criteria.min_area:
            if area >= criteria.min_area:
                return 100.0
            else:
                diff = (criteria.min_area - area) / criteria.min_area
                return max(40, 100 - diff * 100)
        
        elif criteria.max_area:
            if area <= criteria.max_area:
                return 100.0
            else:
                diff = (area - criteria.max_area) / criteria.max_area
                return max(50, 100 - diff * 50)
        
        return 100.0
    
    async def _calculate_rooms_match(self, offer: Offer, criteria: MatchCriteria) -> float:
        """Oblicz dopasowanie liczby pokoi (0-100)"""
        if offer.rooms is None:
            return 50.0
        
        rooms = offer.rooms
        
        if criteria.min_rooms and criteria.max_rooms:
            if criteria.min_rooms <= rooms <= criteria.max_rooms:
                return 100.0
            elif rooms < criteria.min_rooms:
                return max(50, 100 - (criteria.min_rooms - rooms) * 20)
            else:
                return max(60, 100 - (rooms - criteria.max_rooms) * 15)
        
        elif criteria.min_rooms:
            if rooms >= criteria.min_rooms:
                return 100.0
            else:
                return max(50, 100 - (criteria.min_rooms - rooms) * 20)
        
        elif criteria.max_rooms:
            if rooms <= criteria.max_rooms:
                return 100.0
            else:
                return max(60, 100 - (rooms - criteria.max_rooms) * 15)
        
        return 100.0
    
    async def _calculate_features_match(self, offer: Offer, criteria: MatchCriteria) -> float:
        """Oblicz dopasowanie udogodnień (0-100)"""
        if not criteria.must_have:
            return 100.0
        
        matched = 0
        for feature in criteria.must_have:
            if getattr(offer, f'has_{feature}', False):
                matched += 1
        
        if len(criteria.must_have) == 0:
            return 100.0
        
        return (matched / len(criteria.must_have)) * 100
    
    # ===== POWIADOMIENIA =====
    
    async def notify_agent_about_matches(
        self,
        offer_id: str,
        matches: List[MatchResult],
        min_score: float = 70.0
    ):
        """Powiadom agentów o dopasowaniach"""
        # Grupuj dopasowania po agencie
        by_agent: Dict[str, List[MatchResult]] = {}
        for match in matches:
            if match.total_score >= min_score:
                if match.agent_id not in by_agent:
                    by_agent[match.agent_id] = []
                by_agent[match.agent_id].append(match)
        
        # Wyślij powiadomienia
        for agent_id, agent_matches in by_agent.items():
            # Sortuj po wyniku
            agent_matches.sort(key=lambda x: x.total_score, reverse=True)
            
            # Weź top 5
            top_matches = agent_matches[:5]
            
            # Przygotuj wiadomość
            message = self._format_match_notification(top_matches)
            
            # Wyślij (w produkcji: WhatsApp/Email/Push)
            logger.info(f"Would notify agent {agent_id} about {len(top_matches)} matches")
            logger.info(message)
    
    def _format_match_notification(self, matches: List[MatchResult]) -> str:
        """Sformatuj powiadomienie o dopasowaniach"""
        if not matches:
            return ""
        
        offer = matches[0]
        
        msg = f"🎯 NOWA OFERTA pasuje do {len(matches)} klientów!\n\n"
        msg += f"📍 {offer.offer_title}\n"
        msg += f"💰 {offer.offer_price:,.0f} PLN"
        if offer.offer_area:
            msg += f" | {offer.offer_area} m²"
        if offer.offer_rooms:
            msg += f" | {offer.offer_rooms} pok."
        msg += "\n\n"
        
        msg += "👥 DOPASOWANIA:\n"
        for i, match in enumerate(matches[:3], 1):
            msg += f"{i}. {match.client_name} - {match.total_score:.0f}%\n"
            if match.matching_points:
                msg += f"   ✓ {', '.join(match.matching_points[:2])}\n"
        
        return msg
    
    # ===== RAPORTY =====
    
    async def generate_daily_matches_report(
        self,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generuj raport dzienny dopasowań"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Pobierz nowe oferty z dzisiaj
        new_offers = self.db.query(Offer).filter(
            Offer.created_at >= today
        ).all()
        
        total_matches = 0
        perfect_matches = 0
        
        for offer in new_offers:
            matches = await self.find_matches_for_offer(str(offer.id), min_score=60)
            total_matches += len(matches)
            perfect_matches += sum(1 for m in matches if m.score_level == 'perfect')
        
        return {
            'date': today.strftime('%Y-%m-%d'),
            'new_offers': len(new_offers),
            'total_matches': total_matches,
            'perfect_matches': perfect_matches,
            'avg_matches_per_offer': round(total_matches / len(new_offers), 1) if new_offers else 0,
        }
