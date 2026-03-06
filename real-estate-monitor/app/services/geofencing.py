"""
Geofencing and maps integration service.
Provides location-based filtering and distance calculations.
"""
import math
from typing import List, Optional, Tuple
from dataclasses import dataclass

import httpx

from app.logging_config import get_logger
from app.settings import settings

logger = get_logger("geofencing")


@dataclass
class GeoPoint:
    """Geographic point."""
    lat: float
    lng: float
    
    def distance_to(self, other: 'GeoPoint') -> float:
        """Calculate distance to another point in km."""
        return haversine_distance(self.lat, self.lng, other.lat, other.lng)


@dataclass
class Geofence:
    """Geofence area."""
    center: GeoPoint
    radius_km: float
    name: Optional[str] = None
    
    def contains(self, point: GeoPoint) -> bool:
        """Check if point is within geofence."""
        return self.center.distance_to(point) <= self.radius_km


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def calculate_bounding_box(
    center_lat: float,
    center_lng: float,
    radius_km: float
) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box for a circle.
    
    Returns:
        (min_lat, max_lat, min_lng, max_lng)
    """
    # Approximate degrees per km
    lat_degree = radius_km / 111.0
    lng_degree = radius_km / (111.0 * math.cos(math.radians(center_lat)))
    
    return (
        center_lat - lat_degree,
        center_lat + lat_degree,
        center_lng - lng_degree,
        center_lng + lng_degree
    )


class GeocodingService:
    """Service for geocoding addresses."""
    
    def __init__(self):
        self.api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    async def geocode_address(self, address: str) -> Optional[GeoPoint]:
        """
        Convert address to coordinates.
        
        Returns:
            GeoPoint or None if not found
        """
        if not self.api_key:
            logger.warning("Google Maps API key not configured")
            return None
        
        params = {
            "address": address,
            "key": self.api_key,
            "region": "pl",  # Bias results to Poland
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                location = data["results"][0]["geometry"]["location"]
                return GeoPoint(lat=location["lat"], lng=location["lng"])
            
            return None
            
        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
            return None
    
    async def reverse_geocode(
        self,
        lat: float,
        lng: float
    ) -> Optional[dict]:
        """
        Convert coordinates to address.
        
        Returns:
            Dict with address components
        """
        if not self.api_key:
            return None
        
        params = {
            "latlng": f"{lat},{lng}",
            "key": self.api_key,
            "language": "pl",
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
            
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                return {
                    "formatted_address": result["formatted_address"],
                    "components": result["address_components"],
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {e}")
            return None


class DistanceMatrixService:
    """Service for calculating distances and travel times."""
    
    def __init__(self):
        self.api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
        self.base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    async def get_travel_time(
        self,
        origin: GeoPoint,
        destination: GeoPoint,
        mode: str = "transit"  # driving, walking, bicycling, transit
    ) -> Optional[int]:
        """
        Get travel time between two points.
        
        Returns:
            Travel time in seconds or None
        """
        if not self.api_key:
            return None
        
        params = {
            "origins": f"{origin.lat},{origin.lng}",
            "destinations": f"{destination.lat},{destination.lng}",
            "mode": mode,
            "key": self.api_key,
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
            
            if data.get("status") == "OK":
                element = data["rows"][0]["elements"][0]
                if element.get("status") == "OK":
                    return element["duration"]["value"]  # seconds
            
            return None
            
        except Exception as e:
            logger.error(f"Distance matrix failed: {e}")
            return None


class LocationFilter:
    """Filter offers based on location criteria."""
    
    def __init__(
        self,
        reference_point: Optional[GeoPoint] = None,
        max_distance_km: Optional[float] = None,
        geofences: Optional[List[Geofence]] = None
    ):
        self.reference_point = reference_point
        self.max_distance_km = max_distance_km
        self.geofences = geofences or []
    
    def filter_by_distance(
        self,
        offers: List[dict]  # Offers with lat/lng
    ) -> List[dict]:
        """Filter offers within max distance."""
        if not self.reference_point or not self.max_distance_km:
            return offers
        
        filtered = []
        for offer in offers:
            if offer.get('lat') and offer.get('lng'):
                point = GeoPoint(offer['lat'], offer['lng'])
                distance = self.reference_point.distance_to(point)
                
                if distance <= self.max_distance_km:
                    offer['distance_km'] = round(distance, 2)
                    filtered.append(offer)
        
        # Sort by distance
        filtered.sort(key=lambda x: x.get('distance_km', float('inf')))
        
        return filtered
    
    def filter_by_geofence(
        self,
        offers: List[dict]
    ) -> List[dict]:
        """Filter offers within any geofence."""
        if not self.geofences:
            return offers
        
        filtered = []
        for offer in offers:
            if offer.get('lat') and offer.get('lng'):
                point = GeoPoint(offer['lat'], offer['lng'])
                
                for geofence in self.geofences:
                    if geofence.contains(point):
                        offer['geofence'] = geofence.name
                        filtered.append(offer)
                        break
        
        return filtered


# Major Polish cities coordinates
POLISH_CITIES = {
    "warszawa": GeoPoint(52.2297, 21.0122),
    "krakow": GeoPoint(50.0647, 19.9450),
    "gdansk": GeoPoint(54.3520, 18.6466),
    "wroclaw": GeoPoint(51.1079, 17.0385),
    "poznan": GeoPoint(52.4064, 16.9252),
    "lodz": GeoPoint(51.7592, 19.4560),
    "szczecin": GeoPoint(53.4285, 14.5528),
    "bydgoszcz": GeoPoint(53.1235, 18.0084),
    "lublin": GeoPoint(51.2465, 22.5684),
    "katowice": GeoPoint(50.2649, 19.0238),
    "gdynia": GeoPoint(54.5189, 18.5305),
    "sopot": GeoPoint(54.4416, 18.5601),
}


# Global instances
_geocoding_service: Optional[GeocodingService] = None
_distance_service: Optional[DistanceMatrixService] = None


def get_geocoding_service() -> GeocodingService:
    """Get or create geocoding service."""
    global _geocoding_service
    
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    
    return _geocoding_service


def get_distance_service() -> DistanceMatrixService:
    """Get or create distance service."""
    global _distance_service
    
    if _distance_service is None:
        _distance_service = DistanceMatrixService()
    
    return _distance_service
