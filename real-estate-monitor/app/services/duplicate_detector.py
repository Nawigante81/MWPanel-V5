"""
Cross-source duplicate detection service.
Detects the same offer listed on multiple platforms.
"""
from typing import Dict, List, Optional, Set, Tuple
from difflib import SequenceMatcher
from dataclasses import dataclass

from app.logging_config import get_logger
from app.schemas import OfferNormalized

logger = get_logger("duplicate_detector")


@dataclass
class DuplicateMatch:
    """Duplicate match result."""
    offer1_id: str
    offer2_id: str
    confidence: float  # 0-1
    match_reasons: List[str]


class CrossSourceDuplicateDetector:
    """
    Detects duplicate offers across different sources.
    
    Uses multiple signals:
    - Title similarity (fuzzy matching)
    - Price similarity
    - Location similarity
    - Image similarity (perceptual hash)
    """
    
    def __init__(self):
        self.title_similarity_threshold = 0.75
        self.price_tolerance_percent = 5
        self.location_tolerance_km = 0.5
    
    def find_duplicates(
        self,
        offers: List[OfferNormalized]
    ) -> List[DuplicateMatch]:
        """
        Find duplicate offers in the list.
        
        Returns:
            List of duplicate matches
        """
        duplicates = []
        
        for i, offer1 in enumerate(offers):
            for offer2 in offers[i+1:]:
                match = self._check_duplicate(offer1, offer2)
                if match:
                    duplicates.append(match)
        
        return duplicates
    
    def _check_duplicate(
        self,
        offer1: OfferNormalized,
        offer2: OfferNormalized
    ) -> Optional[DuplicateMatch]:
        """Check if two offers are duplicates."""
        if offer1.source == offer2.source:
            return None  # Same source, different deduplication logic
        
        reasons = []
        confidence_factors = []
        
        # Check title similarity
        title_sim = self._title_similarity(offer1.title, offer2.title)
        if title_sim > self.title_similarity_threshold:
            reasons.append(f"title_similarity:{title_sim:.2f}")
            confidence_factors.append(title_sim)
        
        # Check price similarity
        price_sim = self._price_similarity(offer1.price, offer2.price)
        if price_sim > 0.9:
            reasons.append(f"price_similarity:{price_sim:.2f}")
            confidence_factors.append(price_sim)
        
        # Check location similarity
        location_sim = self._location_similarity(
            offer1.lat, offer1.lng,
            offer2.lat, offer2.lng
        )
        if location_sim > 0.9:
            reasons.append(f"location_similarity:{location_sim:.2f}")
            confidence_factors.append(location_sim)
        
        # Check area similarity
        area_sim = self._area_similarity(offer1.area_m2, offer2.area_m2)
        if area_sim > 0.9:
            reasons.append(f"area_similarity:{area_sim:.2f}")
            confidence_factors.append(area_sim)
        
        # Check rooms
        if offer1.rooms and offer2.rooms and offer1.rooms == offer2.rooms:
            reasons.append("same_rooms")
            confidence_factors.append(1.0)
        
        # Determine if duplicate
        # Need at least 2 matching signals or very high title similarity
        is_duplicate = (
            len(reasons) >= 3 or
            (title_sim > 0.85 and len(reasons) >= 2) or
            (title_sim > 0.9)
        )
        
        if is_duplicate and confidence_factors:
            avg_confidence = sum(confidence_factors) / len(confidence_factors)
            return DuplicateMatch(
                offer1_id=offer1.url,  # Using URL as ID
                offer2_id=offer2.url,
                confidence=avg_confidence,
                match_reasons=reasons
            )
        
        return None
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate title similarity using SequenceMatcher."""
        if not title1 or not title2:
            return 0.0
        
        # Normalize titles
        t1 = self._normalize_title(title1)
        t2 = self._normalize_title(title2)
        
        return SequenceMatcher(None, t1, t2).ratio()
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Lowercase
        title = title.lower()
        
        # Remove common words
        stop_words = {
            'na', 'sprzedaz', 'wynajem', 'mieszkanie', 'dom', 'pokoj',
            'the', 'for', 'sale', 'rent', 'apartment', 'house', 'room'
        }
        
        words = title.split()
        words = [w for w in words if w not in stop_words]
        
        return ' '.join(words)
    
    def _price_similarity(
        self,
        price1: Optional[float],
        price2: Optional[float]
    ) -> float:
        """Calculate price similarity."""
        if price1 is None or price2 is None:
            return 0.5  # Unknown
        
        if price1 == 0 or price2 == 0:
            return 0.0
        
        diff = abs(price1 - price2)
        max_price = max(price1, price2)
        
        tolerance = max_price * (self.price_tolerance_percent / 100)
        
        if diff <= tolerance:
            return 1.0 - (diff / tolerance) * 0.5
        
        return max(0, 1.0 - (diff / max_price))
    
    def _location_similarity(
        self,
        lat1: Optional[float],
        lng1: Optional[float],
        lat2: Optional[float],
        lng2: Optional[float]
    ) -> float:
        """Calculate location similarity."""
        if None in [lat1, lng1, lat2, lng2]:
            return 0.5  # Unknown
        
        # Calculate distance
        from app.services.geofencing import haversine_distance
        distance = haversine_distance(lat1, lng1, lat2, lng2)
        
        if distance <= self.location_tolerance_km:
            return 1.0
        elif distance <= self.location_tolerance_km * 2:
            return 0.5
        else:
            return max(0, 1.0 - (distance / 10))  # Decay over 10km
    
    def _area_similarity(
        self,
        area1: Optional[float],
        area2: Optional[float]
    ) -> float:
        """Calculate area similarity."""
        if area1 is None or area2 is None:
            return 0.5  # Unknown
        
        if area1 == 0 or area2 == 0:
            return 0.0
        
        diff = abs(area1 - area2)
        max_area = max(area1, area2)
        
        # Within 2m2 is very similar
        if diff <= 2:
            return 1.0
        elif diff <= 5:
            return 0.8
        else:
            return max(0, 1.0 - (diff / max_area))
    
    def group_duplicates(
        self,
        matches: List[DuplicateMatch]
    ) -> List[Set[str]]:
        """
        Group duplicate matches into clusters.
        
        Returns:
            List of sets, each containing IDs of duplicate offers
        """
        # Build graph
        graph: Dict[str, Set[str]] = {}
        
        for match in matches:
            if match.offer1_id not in graph:
                graph[match.offer1_id] = set()
            if match.offer2_id not in graph:
                graph[match.offer2_id] = set()
            
            graph[match.offer1_id].add(match.offer2_id)
            graph[match.offer2_id].add(match.offer1_id)
        
        # Find connected components
        visited = set()
        groups = []
        
        def dfs(node, group):
            visited.add(node)
            group.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, group)
        
        for node in graph:
            if node not in visited:
                group = set()
                dfs(node, group)
                groups.append(group)
        
        return groups


class DuplicateStore:
    """
    Store and manage duplicate relationships.
    Uses Redis for fast lookups.
    """
    
    def __init__(self):
        from app.services.rate_limit import get_redis_client
        self.redis = get_redis_client()
        self.key_prefix = "duplicates"
    
    def add_duplicate(self, offer1_id: str, offer2_id: str):
        """Record duplicate relationship."""
        key = f"{self.key_prefix}:{offer1_id}"
        self.redis.sadd(key, offer2_id)
        self.redis.expire(key, 86400 * 30)  # 30 days
    
    def get_duplicates(self, offer_id: str) -> Set[str]:
        """Get all duplicates for an offer."""
        key = f"{self.key_prefix}:{offer_id}"
        return self.redis.smembers(key)
    
    def is_duplicate(self, offer_id: str) -> bool:
        """Check if offer has known duplicates."""
        key = f"{self.key_prefix}:{offer_id}"
        return self.redis.scard(key) > 0
    
    def clear_old(self, max_age_days: int = 30):
        """Clear old duplicate records."""
        # Redis TTL handles this automatically
        pass


# Global instance
_duplicate_detector: Optional[CrossSourceDuplicateDetector] = None
_duplicate_store: Optional[DuplicateStore] = None


def get_duplicate_detector() -> CrossSourceDuplicateDetector:
    """Get or create duplicate detector."""
    global _duplicate_detector
    
    if _duplicate_detector is None:
        _duplicate_detector = CrossSourceDuplicateDetector()
    
    return _duplicate_detector


def get_duplicate_store() -> DuplicateStore:
    """Get or create duplicate store."""
    global _duplicate_store
    
    if _duplicate_store is None:
        _duplicate_store = DuplicateStore()
    
    return _duplicate_store
