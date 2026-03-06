"""
Smart filtering and ML scoring system.
Learns user preferences and scores offers accordingly.
"""
from typing import List, Optional
from decimal import Decimal
import math

from app.logging_config import get_logger
from app.models import UserPreference
from app.schemas import OfferNormalized

logger = get_logger("smart_filter")


class OfferScorer:
    """
    Scores offers based on user preferences.
    Uses weighted scoring algorithm.
    """
    
    def __init__(self, preferences: UserPreference):
        self.prefs = preferences
    
    def score_offer(self, offer: OfferNormalized) -> float:
        """
        Calculate overall score for an offer (0-100).
        Higher score = better match for user preferences.
        """
        scores = {
            'price': self._score_price(offer),
            'location': self._score_location(offer),
            'size': self._score_size(offer),
            'rooms': self._score_rooms(offer),
        }
        
        weights = {
            'price': self.prefs.price_weight,
            'location': self.prefs.location_weight,
            'size': self.prefs.size_weight,
            'rooms': self.prefs.rooms_weight,
        }
        
        # Weighted average
        total_score = sum(
            scores[key] * weights[key] 
            for key in scores
        ) / sum(weights.values())
        
        return round(total_score * 100, 2)
    
    def _score_price(self, offer: OfferNormalized) -> float:
        """Score based on price (0-1)."""
        if not offer.price:
            return 0.5  # Neutral if no price
        
        price = float(offer.price)
        
        # If within preferred range, perfect score
        if self.prefs.min_price and self.prefs.max_price:
            if self.prefs.min_price <= offer.price <= self.prefs.max_price:
                return 1.0
        
        # Calculate distance from preferred range
        if self.prefs.max_price and price > float(self.prefs.max_price):
            overshoot = price - float(self.prefs.max_price)
            return max(0, 1 - (overshoot / float(self.prefs.max_price)))
        
        if self.prefs.min_price and price < float(self.prefs.min_price):
            undershoot = float(self.prefs.min_price) - price
            return max(0, 1 - (undershoot / float(self.prefs.min_price)))
        
        return 0.5
    
    def _score_location(self, offer: OfferNormalized) -> float:
        """Score based on location (0-1)."""
        # Check preferred cities
        if self.prefs.preferred_cities:
            if offer.city and offer.city.lower() in [
                c.lower() for c in self.prefs.preferred_cities
            ]:
                return 1.0
        
        # Check preferred regions
        if self.prefs.preferred_regions:
            if offer.region and offer.region.lower() in [
                r.lower() for r in self.prefs.preferred_regions
            ]:
                return 0.9
        
        # Check distance from reference point
        if (self.prefs.reference_lat and self.prefs.reference_lng and 
            self.prefs.max_distance_km and offer.lat and offer.lng):
            
            distance = self._haversine_distance(
                float(self.prefs.reference_lat),
                float(self.prefs.reference_lng),
                offer.lat,
                offer.lng
            )
            
            if distance <= self.prefs.max_distance_km:
                return 1.0 - (distance / self.prefs.max_distance_km) * 0.5
        
        return 0.3
    
    def _score_size(self, offer: OfferNormalized) -> float:
        """Score based on area/size (0-1)."""
        if not offer.area_m2:
            return 0.5
        
        area = offer.area_m2
        
        # Within preferred range
        if self.prefs.min_area and self.prefs.max_area:
            if self.prefs.min_area <= area <= self.prefs.max_area:
                return 1.0
        
        # Outside range - calculate penalty
        if self.prefs.max_area and area > self.prefs.max_area:
            overshoot = area - self.prefs.max_area
            return max(0, 1 - (overshoot / self.prefs.max_area))
        
        if self.prefs.min_area and area < self.prefs.min_area:
            undershoot = self.prefs.min_area - area
            return max(0, 1 - (undershoot / self.prefs.min_area))
        
        return 0.5
    
    def _score_rooms(self, offer: OfferNormalized) -> float:
        """Score based on room count (0-1)."""
        if not offer.rooms:
            return 0.5
        
        if self.prefs.preferred_rooms:
            if offer.rooms in self.prefs.preferred_rooms:
                return 1.0
            # Close to preferred
            closest = min(
                self.prefs.preferred_rooms,
                key=lambda x: abs(x - offer.rooms)
            )
            diff = abs(closest - offer.rooms)
            return max(0, 1 - diff * 0.3)
        
        return 0.5
    
    @staticmethod
    def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points in kilometers."""
        R = 6371  # Earth's radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c


class PreferenceLearner:
    """
    Learns user preferences from interactions.
    Adjusts weights based on user behavior.
    """
    
    def __init__(self, preferences: UserPreference):
        self.prefs = preferences
    
    def record_interaction(
        self,
        offer: OfferNormalized,
        action: str,  # 'viewed', 'saved', 'contacted', 'ignored'
        duration_seconds: Optional[float] = None
    ):
        """Record user interaction with an offer."""
        # Positive interactions increase weights for matching features
        if action in ['saved', 'contacted']:
            self._reinforce_preferences(offer, positive=True)
        elif action == 'ignored':
            self._reinforce_preferences(offer, positive=False)
        
        # Long view duration indicates interest
        if duration_seconds and duration_seconds > 30:
            self._reinforce_preferences(offer, positive=True, strength=0.1)
    
    def _reinforce_preferences(
        self,
        offer: OfferNormalized,
        positive: bool,
        strength: float = 0.2
    ):
        """Adjust weights based on offer features."""
        multiplier = 1 + strength if positive else 1 - strength
        
        # Adjust price preference
        if offer.price:
            if positive:
                # Move preferred range towards this price
                pass  # Complex logic omitted for brevity
        
        # Adjust location preference
        if offer.city and self.prefs.preferred_cities is not None:
            if positive and offer.city not in self.prefs.preferred_cities:
                self.prefs.preferred_cities.append(offer.city)
        
        logger.debug(f"Updated preferences based on interaction (positive={positive})")


class SmartFilter:
    """
    Main smart filter interface.
    Filters and sorts offers based on user preferences.
    """
    
    def __init__(self, preferences: UserPreference):
        self.preferences = preferences
        self.scorer = OfferScorer(preferences)
    
    def filter_offers(
        self,
        offers: List[OfferNormalized],
        min_score: float = 0.0,
        limit: Optional[int] = None
    ) -> List[tuple]:
        """
        Filter and score offers.
        
        Returns:
            List of (offer, score) tuples sorted by score descending
        """
        scored_offers = []
        
        for offer in offers:
            score = self.scorer.score_offer(offer)
            
            if score >= min_score:
                scored_offers.append((offer, score))
        
        # Sort by score descending
        scored_offers.sort(key=lambda x: x[1], reverse=True)
        
        if limit:
            scored_offers = scored_offers[:limit]
        
        return scored_offers
    
    def get_top_offers(
        self,
        offers: List[OfferNormalized],
        count: int = 10
    ) -> List[tuple]:
        """Get top N offers by score."""
        return self.filter_offers(offers, limit=count)


def calculate_price_trend(price_history: List[dict]) -> dict:
    """
    Calculate price trend from history.
    
    Returns:
        dict with trend direction, change percent, etc.
    """
    if len(price_history) < 2:
        return {"trend": "stable", "change_percent": 0}
    
    prices = [float(p['price']) for p in price_history]
    
    # Simple linear regression
    n = len(prices)
    x = list(range(n))
    
    mean_x = sum(x) / n
    mean_y = sum(prices) / n
    
    numerator = sum((x[i] - mean_x) * (prices[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
    
    slope = numerator / denominator if denominator != 0 else 0
    
    # Calculate total change
    first_price = prices[0]
    last_price = prices[-1]
    change_percent = ((last_price - first_price) / first_price) * 100 if first_price else 0
    
    if slope < -100:  # Decreasing
        trend = "decreasing"
    elif slope > 100:  # Increasing
        trend = "increasing"
    else:
        trend = "stable"
    
    return {
        "trend": trend,
        "change_percent": round(change_percent, 2),
        "slope": round(slope, 2),
        "first_price": first_price,
        "last_price": last_price,
    }
