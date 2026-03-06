"""
Recommendations Service - System Rekomendacji

Rekomendacje ofert na podstawie zachowań użytkowników,
podobnych klientów, historii przeglądania.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import math

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class RecommendationType(str, Enum):
    """Typ rekomendacji"""
    SIMILAR = "similar"              # Podobne oferty
    COLLABORATIVE = "collaborative"  # Inni klienci oglądali
    TRENDING = "trending"            # Popularne
    PERSONALIZED = "personalized"    # Dla Ciebie
    COMPLEMENTARY = "complementary"  # Uzupełniające


@dataclass
class Recommendation:
    """Rekomendacja oferty"""
    listing_id: str
    listing_title: str
    listing_image: Optional[str]
    price: float
    city: str
    
    # Metadane rekomendacji
    recommendation_type: RecommendationType
    score: float                   # 0-100
    reason: str                    # Dlaczego ta rekomendacja
    
    # Dodatkowe dane
    similarity_factors: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'listing': {
                'id': self.listing_id,
                'title': self.listing_title,
                'image': self.listing_image,
                'price': self.price,
                'city': self.city,
            },
            'recommendation_type': self.recommendation_type.value,
            'score': round(self.score, 2),
            'reason': self.reason,
            'similarity_factors': self.similarity_factors,
        }


@dataclass
class UserProfile:
    """Profil użytkownika do rekomendacji"""
    user_id: str
    
    # Preferencje
    preferred_property_types: List[str] = field(default_factory=list)
    preferred_cities: List[str] = field(default_factory=list)
    preferred_districts: List[str] = field(default_factory=list)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    rooms_preferred: Optional[int] = None
    
    # Historia
    viewed_listings: List[str] = field(default_factory=list)
    favorited_listings: List[str] = field(default_factory=list)
    contacted_listings: List[str] = field(default_factory=list)
    search_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Zachowania
    avg_time_on_listing: float = 0.0  # sekundy
    total_sessions: int = 0
    last_active: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'preferences': {
                'property_types': self.preferred_property_types,
                'cities': self.preferred_cities,
                'districts': self.preferred_districts,
                'price_range': {
                    'min': self.price_min,
                    'max': self.price_max,
                },
                'area_range': {
                    'min': self.area_min,
                    'max': self.area_max,
                },
                'rooms': self.rooms_preferred,
            },
            'history': {
                'viewed': len(self.viewed_listings),
                'favorited': len(self.favorited_listings),
                'contacted': len(self.contacted_listings),
            },
        }


class RecommendationsService:
    """
    Serwis rekomendacji.
    
    Generuje spersonalizowane rekomendacje ofert
    na podstawie zachowań użytkowników i podobieństwa ofert.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.user_profiles: Dict[str, UserProfile] = {}
    
    async def get_similar_listings(
        self,
        listing_id: str,
        limit: int = 5,
    ) -> List[Recommendation]:
        """
        Znajdź oferty podobne do podanej.
        
        Algorytm:
        - Taki sam typ nieruchomości
        - Podobna powierzchnia (±30%)
        - Podobna cena (±30%)
        - Ta sama lokalizacja
        """
        # Pobierz referencyjną ofertę
        reference = self._get_listing(listing_id)
        if not reference:
            return []
        
        # Pobierz kandydatów
        candidates = self._get_candidate_listings(
            city=reference.get('city'),
            exclude_id=listing_id,
        )
        
        recommendations = []
        
        for candidate in candidates:
            score, factors = self._calculate_similarity(reference, candidate)
            
            if score >= 50:  # Min 50% podobieństwa
                recommendations.append(Recommendation(
                    listing_id=candidate['id'],
                    listing_title=candidate['title'],
                    listing_image=candidate.get('images', [None])[0],
                    price=candidate.get('price', 0),
                    city=candidate.get('city', ''),
                    recommendation_type=RecommendationType.SIMILAR,
                    score=score,
                    reason=self._generate_similarity_reason(factors),
                    similarity_factors=factors,
                ))
        
        # Sortuj po score
        recommendations.sort(key=lambda r: r.score, reverse=True)
        
        return recommendations[:limit]
    
    async def get_recommendations_for_user(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[Recommendation]:
        """
        Spersonalizowane rekomendacje dla użytkownika.
        
        Algorytm hybrydowy:
        1. Content-based (na podstawie historii)
        2. Collaborative filtering (co oglądali podobni użytkownicy)
        3. Trending (popularne oferty)
        """
        profile = await self._get_user_profile(user_id)
        
        all_recommendations = []
        
        # 1. Content-based recommendations
        if profile.viewed_listings:
            content_based = await self._get_content_based_recommendations(profile, limit=limit//2)
            all_recommendations.extend(content_based)
        
        # 2. Collaborative filtering
        collaborative = await self._get_collaborative_recommendations(profile, limit=limit//3)
        all_recommendations.extend(collaborative)
        
        # 3. Trending
        trending = await self._get_trending_listings(limit=limit//3)
        all_recommendations.extend(trending)
        
        # Usuń duplikaty i już oglądane
        seen_ids = set(profile.viewed_listings)
        unique_recommendations = []
        
        for rec in all_recommendations:
            if rec.listing_id not in seen_ids:
                unique_recommendations.append(rec)
                seen_ids.add(rec.listing_id)
        
        # Sortuj po score
        unique_recommendations.sort(key=lambda r: r.score, reverse=True)
        
        return unique_recommendations[:limit]
    
    async def get_trending_listings(
        self,
        city: Optional[str] = None,
        days: int = 7,
        limit: int = 10,
    ) -> List[Recommendation]:
        """Popularne oferty (trending)"""
        # Pobierz oferty z największą aktywnością
        trending = self._get_trending(
            city=city,
            days=days,
            limit=limit,
        )
        
        recommendations = []
        
        for listing in trending:
            recommendations.append(Recommendation(
                listing_id=listing['id'],
                listing_title=listing['title'],
                listing_image=listing.get('images', [None])[0],
                price=listing.get('price', 0),
                city=listing.get('city', ''),
                recommendation_type=RecommendationType.TRENDING,
                score=listing.get('trend_score', 50),
                reason="Popularne ostatnio - wielu klientów ogląda tę ofertę",
            ))
        
        return recommendations
    
    async def get_complementary_listings(
        self,
        listing_id: str,
        limit: int = 3,
    ) -> List[Recommendation]:
        """
        Oferty uzupełniające (np. garaż do mieszkania).
        """
        listing = self._get_listing(listing_id)
        if not listing:
            return []
        
        recommendations = []
        
        # Jeśli mieszkanie bez garażu - pokaż garaże w okolicy
        if listing.get('property_type') == 'apartment' and not listing.get('has_garage'):
            garages = self._get_complementary_listings(
                property_type='garage',
                city=listing.get('city'),
                district=listing.get('district'),
            )
            
            for garage in garages[:limit]:
                recommendations.append(Recommendation(
                    listing_id=garage['id'],
                    listing_title=garage['title'],
                    listing_image=garage.get('images', [None])[0],
                    price=garage.get('price', 0),
                    city=garage.get('city', ''),
                    recommendation_type=RecommendationType.COMPLEMENTARY,
                    score=70,
                    reason="Garaż w tej samej okolicy",
                ))
        
        return recommendations
    
    async def get_customers_also_viewed(
        self,
        listing_id: str,
        limit: int = 5,
    ) -> List[Recommendation]:
        """
        "Klienci oglądali również" - collaborative filtering.
        """
        # Znajdź użytkowników, którzy oglądali tę ofertę
        users_who_viewed = self._get_users_who_viewed(listing_id)
        
        if not users_who_viewed:
            return []
        
        # Znajdź inne oferty oglądane przez tych użytkowników
        other_listings = self._get_listings_viewed_by_users(
            users_who_viewed,
            exclude_listing_id=listing_id,
        )
        
        # Policz częstość
        listing_counts = {}
        for listing in other_listings:
            lid = listing['id']
            if lid not in listing_counts:
                listing_counts[lid] = {'count': 0, 'listing': listing}
            listing_counts[lid]['count'] += 1
        
        # Sortuj po popularności
        sorted_listings = sorted(
            listing_counts.values(),
            key=lambda x: x['count'],
            reverse=True,
        )
        
        recommendations = []
        for item in sorted_listings[:limit]:
            listing = item['listing']
            count = item['count']
            
            recommendations.append(Recommendation(
                listing_id=listing['id'],
                listing_title=listing['title'],
                listing_image=listing.get('images', [None])[0],
                price=listing.get('price', 0),
                city=listing.get('city', ''),
                recommendation_type=RecommendationType.COLLABORATIVE,
                score=min(50 + count * 5, 95),
                reason=f"Klienci oglądający tę ofertę interesowali się również",
            ))
        
        return recommendations
    
    async def track_listing_view(
        self,
        user_id: str,
        listing_id: str,
        duration_seconds: float = 0,
    ):
        """Śledź oglądanie oferty"""
        profile = await self._get_user_profile(user_id)
        
        if listing_id not in profile.viewed_listings:
            profile.viewed_listings.append(listing_id)
        
        # Aktualizuj średni czas
        total_time = profile.avg_time_on_listing * profile.total_sessions
        profile.total_sessions += 1
        profile.avg_time_on_listing = (total_time + duration_seconds) / profile.total_sessions
        
        profile.last_active = datetime.utcnow()
        
        # Zapisz
        self._save_user_profile(profile)
    
    async def track_search(
        self,
        user_id: str,
        search_params: Dict[str, Any],
    ):
        """Śledź wyszukiwanie"""
        profile = await self._get_user_profile(user_id)
        
        profile.search_history.append({
            'params': search_params,
            'timestamp': datetime.utcnow().isoformat(),
        })
        
        # Aktualizuj preferencje
        if 'property_type' in search_params:
            pt = search_params['property_type']
            if pt not in profile.preferred_property_types:
                profile.preferred_property_types.append(pt)
        
        if 'city' in search_params:
            city = search_params['city']
            if city not in profile.preferred_cities:
                profile.preferred_cities.append(city)
        
        if 'price_min' in search_params:
            profile.price_min = search_params['price_min']
        if 'price_max' in search_params:
            profile.price_max = search_params['price_max']
        
        self._save_user_profile(profile)
    
    async def track_favorite(
        self,
        user_id: str,
        listing_id: str,
    ):
        """Śledź dodanie do ulubionych"""
        profile = await self._get_user_profile(user_id)
        
        if listing_id not in profile.favorited_listings:
            profile.favorited_listings.append(listing_id)
        
        self._save_user_profile(profile)
    
    async def get_recommendation_explanation(
        self,
        user_id: str,
        listing_id: str,
    ) -> str:
        """Wyjaśnij dlaczego ta rekomendacja"""
        profile = await self._get_user_profile(user_id)
        listing = self._get_listing(listing_id)
        
        if not listing:
            return "Oferta wybrana dla Ciebie"
        
        reasons = []
        
        if listing.get('city') in profile.preferred_cities:
            reasons.append(f"interesujesz się ofertami w mieście {listing['city']}")
        
        if listing.get('property_type') in profile.preferred_property_types:
            reasons.append("szukasz tego typu nieruchomości")
        
        if listing['id'] in [r.listing_id for r in await self.get_customers_also_viewed(listing_id)]:
            reasons.append("klienci o podobnych preferencjach oglądali tę ofertę")
        
        if reasons:
            return f"Polecamy, ponieważ {' i '.join(reasons)}"
        
        return "Oferta może Cię zainteresować"
    
    # ==========================================================================
    # Metody prywatne
    # ==========================================================================
    
    async def _get_user_profile(self, user_id: str) -> UserProfile:
        """Pobierz lub utwórz profil użytkownika"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)
        
        return self.user_profiles[user_id]
    
    def _save_user_profile(self, profile: UserProfile):
        """Zapisz profil użytkownika"""
        self.user_profiles[profile.user_id] = profile
    
    def _get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Pobierz ofertę z bazy"""
        # W rzeczywistej implementacji
        return None
    
    def _get_candidate_listings(
        self,
        city: Optional[str] = None,
        exclude_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Pobierz kandydatów do rekomendacji"""
        # W rzeczywistej implementacji
        return []
    
    def _calculate_similarity(
        self,
        reference: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> Tuple[float, Dict[str, float]]:
        """Oblicz podobieństwo dwóch ofert"""
        factors = {}
        total_score = 0
        
        # Typ nieruchomości (25%)
        if reference.get('property_type') == candidate.get('property_type'):
            factors['property_type'] = 1.0
            total_score += 25
        else:
            factors['property_type'] = 0.0
        
        # Lokalizacja (25%)
        if reference.get('city') == candidate.get('city'):
            if reference.get('district') == candidate.get('district'):
                factors['location'] = 1.0
                total_score += 25
            else:
                factors['location'] = 0.5
                total_score += 12.5
        else:
            factors['location'] = 0.0
        
        # Cena (25%)
        ref_price = reference.get('price', 0)
        cand_price = candidate.get('price', 0)
        if ref_price > 0 and cand_price > 0:
            price_diff = abs(ref_price - cand_price) / ref_price
            price_sim = max(0, 1 - price_diff / 0.3)  # 30% tolerancji
            factors['price'] = price_sim
            total_score += price_sim * 25
        
        # Powierzchnia (25%)
        ref_area = reference.get('area_sqm', 0)
        cand_area = candidate.get('area_sqm', 0)
        if ref_area > 0 and cand_area > 0:
            area_diff = abs(ref_area - cand_area) / ref_area
            area_sim = max(0, 1 - area_diff / 0.3)
            factors['area'] = area_sim
            total_score += area_sim * 25
        
        return total_score, factors
    
    def _generate_similarity_reason(self, factors: Dict[str, float]) -> str:
        """Wygeneruj powód podobieństwa"""
        reasons = []
        
        if factors.get('property_type', 0) > 0.8:
            reasons.append("ten sam typ nieruchomości")
        
        if factors.get('location', 0) > 0.8:
            reasons.append("ta sama dzielnica")
        elif factors.get('location', 0) > 0.4:
            reasons.append("to samo miasto")
        
        if factors.get('price', 0) > 0.8:
            reasons.append("podobna cena")
        
        if factors.get('area', 0) > 0.8:
            reasons.append("podobny metraż")
        
        if reasons:
            return f"Podobna oferta: {', '.join(reasons)}"
        
        return "Oferta o podobnych parametrach"
    
    async def _get_content_based_recommendations(
        self,
        profile: UserProfile,
        limit: int = 5,
    ) -> List[Recommendation]:
        """Rekomendacje content-based"""
        # Pobierz ostatnio oglądane oferty
        if not profile.viewed_listings:
            return []
        
        recent_listings = profile.viewed_listings[-5:]
        
        # Znajdź podobne do każdej
        all_similar = []
        for listing_id in recent_listings:
            similar = await self.get_similar_listings(listing_id, limit=3)
            all_similar.extend(similar)
        
        # Usuń duplikaty
        seen = set()
        unique = []
        for rec in all_similar:
            if rec.listing_id not in seen:
                rec.recommendation_type = RecommendationType.PERSONALIZED
                rec.reason = "Na podstawie Twoich ostatnich oglądanych ofert"
                unique.append(rec)
                seen.add(rec.listing_id)
        
        return unique[:limit]
    
    async def _get_collaborative_recommendations(
        self,
        profile: UserProfile,
        limit: int = 5,
    ) -> List[Recommendation]:
        """Rekomendacje collaborative filtering"""
        if not profile.viewed_listings:
            return []
        
        # Znajdź co oglądali inni użytkownicy
        all_recommendations = []
        
        for listing_id in profile.viewed_listings[-3:]:
            also_viewed = await self.get_customers_also_viewed(listing_id, limit=3)
            all_recommendations.extend(also_viewed)
        
        # Usuń duplikaty
        seen = set()
        unique = []
        for rec in all_recommendations:
            if rec.listing_id not in seen:
                unique.append(rec)
                seen.add(rec.listing_id)
        
        return unique[:limit]
    
    def _get_trending(
        self,
        city: Optional[str] = None,
        days: int = 7,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Pobierz popularne oferty"""
        # W rzeczywistej implementacji
        return []
    
    def _get_complementary_listings(
        self,
        property_type: str,
        city: str,
        district: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Pobierz oferty uzupełniające"""
        # W rzeczywistej implementacji
        return []
    
    def _get_users_who_viewed(self, listing_id: str) -> List[str]:
        """Pobierz użytkowników, którzy oglądali ofertę"""
        users = []
        for profile in self.user_profiles.values():
            if listing_id in profile.viewed_listings:
                users.append(profile.user_id)
        return users
    
    def _get_listings_viewed_by_users(
        self,
        user_ids: List[str],
        exclude_listing_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Pobierz oferty oglądane przez użytkowników"""
        listings = []
        for user_id in user_ids:
            profile = self.user_profiles.get(user_id)
            if profile:
                for listing_id in profile.viewed_listings:
                    if listing_id != exclude_listing_id:
                        listing = self._get_listing(listing_id)
                        if listing:
                            listings.append(listing)
        return listings


# Singleton
def get_recommendations_service(db_session: Session) -> RecommendationsService:
    return RecommendationsService(db_session)
