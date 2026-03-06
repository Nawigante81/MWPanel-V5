"""
Google Maps Integration Service - Integracja z Google Maps

Geokodowanie adresów, obliczanie odległości, optymalizacja tras,
autouzupełnianie adresów i wizualizacja na mapach.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import math
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.settings import settings

logger = get_logger(__name__)


@dataclass
class GeoLocation:
    """Współrzędne geograficzne"""
    lat: float
    lng: float
    
    def to_dict(self) -> Dict[str, float]:
        return {'lat': self.lat, 'lng': self.lng}


@dataclass
class GeocodingResult:
    """Wynik geokodowania"""
    address: str
    location: GeoLocation
    formatted_address: str
    place_id: Optional[str]
    address_components: Dict[str, str]
    confidence: str  # high, medium, low
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'address': self.address,
            'location': self.location.to_dict(),
            'formatted_address': self.formatted_address,
            'place_id': self.place_id,
            'address_components': self.address_components,
            'confidence': self.confidence,
        }


@dataclass
class DistanceResult:
    """Wynik obliczenia odległości"""
    origin: GeoLocation
    destination: GeoLocation
    distance_meters: int
    duration_seconds: int
    distance_text: str
    duration_text: str
    
    @property
    def distance_km(self) -> float:
        return self.distance_meters / 1000
    
    @property
    def duration_minutes(self) -> int:
        return self.duration_seconds // 60
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'origin': self.origin.to_dict(),
            'destination': self.destination.to_dict(),
            'distance': {
                'meters': self.distance_meters,
                'km': round(self.distance_km, 2),
                'text': self.distance_text,
            },
            'duration': {
                'seconds': self.duration_seconds,
                'minutes': self.duration_minutes,
                'text': self.duration_text,
            },
        }


@dataclass
class RouteWaypoint:
    """Punkt na trasie"""
    id: str
    address: str
    location: GeoLocation
    duration_minutes: int  # Czas pobytu w minutach
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'address': self.address,
            'location': self.location.to_dict(),
            'duration_minutes': self.duration_minutes,
        }


@dataclass
class OptimizedRoute:
    """Zoptymalizowana trasa"""
    waypoints: List[RouteWaypoint]
    total_distance_meters: int
    total_duration_seconds: int
    total_duration_with_stops: int
    legs: List[DistanceResult]
    
    @property
    def total_distance_km(self) -> float:
        return self.total_distance_meters / 1000
    
    @property
    def total_duration_minutes(self) -> int:
        return self.total_duration_seconds // 60
    
    @property
    def total_duration_with_stops_minutes(self) -> int:
        return self.total_duration_with_stops // 60
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'waypoints': [wp.to_dict() for wp in self.waypoints],
            'total_distance': {
                'meters': self.total_distance_meters,
                'km': round(self.total_distance_km, 2),
            },
            'total_duration': {
                'seconds': self.total_duration_seconds,
                'minutes': self.total_duration_minutes,
            },
            'total_duration_with_stops': {
                'seconds': self.total_duration_with_stops,
                'minutes': self.total_duration_with_stops_minutes,
            },
            'legs': [leg.to_dict() for leg in self.legs],
        }


@dataclass
class PlaceSuggestion:
    """Sugestia adresu z autouzupełniania"""
    place_id: str
    description: str
    main_text: str
    secondary_text: str
    types: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'place_id': self.place_id,
            'description': self.description,
            'main_text': self.main_text,
            'secondary_text': self.secondary_text,
            'types': self.types,
        }


class GoogleMapsService:
    """
    Serwis integracji z Google Maps API.
    
    Dostarcza funkcje:
    - Geokodowanie adresów na współrzędne
    - Reverse geokodowanie (współrzędne -> adres)
    - Obliczanie odległości i czasu dojazdu
    - Optymalizacja tras (np. dla prezentacji)
    - Autouzupełnianie adresów
    """
    
    BASE_URL = "https://maps.googleapis.com/maps/api"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.google_maps_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def geocode_address(
        self,
        address: str,
        city: Optional[str] = None,
        country: str = "Polska",
    ) -> Optional[GeocodingResult]:
        """
        Geokoduj adres na współrzędne geograficzne.
        
        Args:
            address: Adres do geokodowania
            city: Miasto (opcjonalne, dodawane do adresu)
            country: Kraj
        
        Returns:
            GeocodingResult lub None jeśli nie znaleziono
        """
        if not self.api_key:
            logger.warning("Google Maps API key not configured")
            return self._fallback_geocode(address, city)
        
        full_address = address
        if city:
            full_address = f"{address}, {city}"
        full_address = f"{full_address}, {country}"
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/geocode/json",
                params={
                    'address': full_address,
                    'key': self.api_key,
                    'language': 'pl',
                    'region': 'pl',
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'OK' or not data['results']:
                logger.warning(f"Geocoding failed: {data['status']} for address: {address}")
                return self._fallback_geocode(address, city)
            
            result = data['results'][0]
            location = result['geometry']['location']
            
            # Określ poziom ufności
            location_type = result['geometry'].get('location_type', '')
            confidence = 'high' if location_type == 'ROOFTOP' else 'medium' if location_type == 'GEOMETRIC_CENTER' else 'low'
            
            # Parsuj komponenty adresu
            components = {}
            for component in result.get('address_components', []):
                types = component.get('types', [])
                if 'street_number' in types:
                    components['street_number'] = component['long_name']
                elif 'route' in types:
                    components['street'] = component['long_name']
                elif 'locality' in types:
                    components['city'] = component['long_name']
                elif 'postal_code' in types:
                    components['postal_code'] = component['long_name']
                elif 'administrative_area_level_1' in types:
                    components['voivodeship'] = component['long_name']
            
            return GeocodingResult(
                address=address,
                location=GeoLocation(lat=location['lat'], lng=location['lng']),
                formatted_address=result['formatted_address'],
                place_id=result.get('place_id'),
                address_components=components,
                confidence=confidence,
            )
            
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return self._fallback_geocode(address, city)
    
    async def reverse_geocode(
        self,
        lat: float,
        lng: float,
    ) -> Optional[GeocodingResult]:
        """
        Reverse geokodowanie - współrzędne na adres.
        
        Args:
            lat: Szerokość geograficzna
            lng: Długość geograficzna
        
        Returns:
            GeocodingResult lub None
        """
        if not self.api_key:
            logger.warning("Google Maps API key not configured")
            return None
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/geocode/json",
                params={
                    'latlng': f"{lat},{lng}",
                    'key': self.api_key,
                    'language': 'pl',
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'OK' or not data['results']:
                return None
            
            result = data['results'][0]
            location = result['geometry']['location']
            
            components = {}
            for component in result.get('address_components', []):
                types = component.get('types', [])
                if 'street_number' in types:
                    components['street_number'] = component['long_name']
                elif 'route' in types:
                    components['street'] = component['long_name']
                elif 'locality' in types:
                    components['city'] = component['long_name']
                elif 'postal_code' in types:
                    components['postal_code'] = component['long_name']
                elif 'sublocality' in types or 'neighborhood' in types:
                    components['district'] = component['long_name']
            
            return GeocodingResult(
                address=result['formatted_address'],
                location=GeoLocation(lat=location['lat'], lng=location['lng']),
                formatted_address=result['formatted_address'],
                place_id=result.get('place_id'),
                address_components=components,
                confidence='high',
            )
            
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
            return None
    
    async def calculate_distance(
        self,
        origin: GeoLocation,
        destination: GeoLocation,
        mode: str = "driving",
    ) -> Optional[DistanceResult]:
        """
        Oblicz odległość i czas dojazdu między dwoma punktami.
        
        Args:
            origin: Punkt początkowy
            destination: Punkt docelowy
            mode: Tryb transportu (driving, walking, bicycling, transit)
        
        Returns:
            DistanceResult lub None
        """
        if not self.api_key:
            # Fallback: oblicz odległość w linii prostej
            return self._calculate_haversine_distance(origin, destination)
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/distancematrix/json",
                params={
                    'origins': f"{origin.lat},{origin.lng}",
                    'destinations': f"{destination.lat},{destination.lng}",
                    'mode': mode,
                    'key': self.api_key,
                    'language': 'pl',
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'OK':
                return self._calculate_haversine_distance(origin, destination)
            
            element = data['rows'][0]['elements'][0]
            
            if element['status'] != 'OK':
                return self._calculate_haversine_distance(origin, destination)
            
            return DistanceResult(
                origin=origin,
                destination=destination,
                distance_meters=element['distance']['value'],
                duration_seconds=element['duration']['value'],
                distance_text=element['distance']['text'],
                duration_text=element['duration']['text'],
            )
            
        except Exception as e:
            logger.error(f"Distance calculation error: {e}")
            return self._calculate_haversine_distance(origin, destination)
    
    async def optimize_route(
        self,
        waypoints: List[RouteWaypoint],
        start_location: Optional[GeoLocation] = None,
        end_location: Optional[GeoLocation] = None,
        mode: str = "driving",
    ) -> OptimizedRoute:
        """
        Zoptymalizuj trasę przez wiele punktów (problem komiwojażera).
        
        Args:
            waypoints: Lista punktów do odwiedzenia
            start_location: Punkt startowy (opcjonalny, domyślnie pierwszy waypoint)
            end_location: Punkt końcowy (opcjonalny, domyślnie ostatni waypoint)
            mode: Tryb transportu
        
        Returns:
            OptimizedRoute z optymalną kolejnością punktów
        """
        if len(waypoints) < 2:
            raise ValueError("At least 2 waypoints required")
        
        # Jeśli mamy klucz API, użyj Google Directions API z optymalizacją
        if self.api_key and len(waypoints) <= 23:  # Limit Google API
            return await self._optimize_with_google(waypoints, start_location, end_location, mode)
        
        # Fallback: prosta optymalizacja najbliższego sąsiada
        return self._optimize_nearest_neighbor(waypoints, start_location, end_location)
    
    async def autocomplete_address(
        self,
        input_text: str,
        city: Optional[str] = None,
        types: Optional[List[str]] = None,
    ) -> List[PlaceSuggestion]:
        """
        Autouzupełnianie adresów.
        
        Args:
            input_text: Wprowadzony tekst
            city: Ogranicz do miasta
            types: Typy miejsc (address, establishment, etc.)
        
        Returns:
            Lista sugestii
        """
        if not self.api_key:
            return []
        
        try:
            params = {
                'input': input_text,
                'key': self.api_key,
                'language': 'pl',
                'components': 'country:pl',
            }
            
            if types:
                params['types'] = '|'.join(types)
            
            if city:
                # Dodaj bias do miasta
                params['location'] = city  # Wymaga geokodowania
            
            response = await self.client.get(
                f"{self.BASE_URL}/place/autocomplete/json",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'OK':
                return []
            
            suggestions = []
            for prediction in data.get('predictions', [])[:5]:  # Max 5 sugestii
                structured = prediction.get('structured_formatting', {})
                suggestions.append(PlaceSuggestion(
                    place_id=prediction['place_id'],
                    description=prediction['description'],
                    main_text=structured.get('main_text', ''),
                    secondary_text=structured.get('secondary_text', ''),
                    types=prediction.get('types', []),
                ))
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Autocomplete error: {e}")
            return []
    
    async def get_static_map_url(
        self,
        location: GeoLocation,
        zoom: int = 15,
        size: str = "600x400",
        markers: Optional[List[GeoLocation]] = None,
    ) -> str:
        """
        Generuj URL do statycznej mapy.
        
        Args:
            location: Środek mapy
            zoom: Poziom przybliżenia
            size: Rozmiar obrazu (szerokośćxwysokość)
            markers: Dodatkowe markery
        
        Returns:
            URL do obrazu mapy
        """
        if not self.api_key:
            # Fallback: OpenStreetMap
            return f"https://staticmap.openstreetmap.de/staticmap.php?center={location.lat},{location.lng}&zoom={zoom}&size={size}"
        
        params = {
            'center': f"{location.lat},{location.lng}",
            'zoom': zoom,
            'size': size,
            'key': self.api_key,
            'maptype': 'roadmap',
        }
        
        # Dodaj markery
        if markers:
            marker_str = '|'.join([f"{m.lat},{m.lng}" for m in markers[:10]])  # Max 10
            params['markers'] = marker_str
        else:
            params['markers'] = f"{location.lat},{location.lng}"
        
        query = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.BASE_URL}/staticmap?{query}"
    
    async def batch_geocode(
        self,
        addresses: List[str],
    ) -> List[Optional[GeocodingResult]]:
        """
        Geokoduj wiele adresów jednocześnie.
        
        Args:
            addresses: Lista adresów
        
        Returns:
            Lista wyników (None dla nieudanych)
        """
        results = []
        for address in addresses:
            result = await self.geocode_address(address)
            results.append(result)
        return results
    
    async def find_nearby_listings(
        self,
        center: GeoLocation,
        listings: List[Dict[str, Any]],
        radius_km: float = 5.0,
    ) -> List[Dict[str, Any]]:
        """
        Znajdź oferty w promieniu od danego punktu.
        
        Args:
            center: Punkt centralny
            listings: Lista ofert z współrzędnymi
            radius_km: Promień w km
        
        Returns:
            Oferty w promieniu z odległością
        """
        nearby = []
        
        for listing in listings:
            lat = listing.get('lat')
            lng = listing.get('lng')
            
            if lat is None or lng is None:
                continue
            
            distance = self._haversine_distance(
                center.lat, center.lng,
                lat, lng
            )
            
            if distance <= radius_km:
                listing_copy = listing.copy()
                listing_copy['distance_km'] = round(distance, 2)
                nearby.append(listing_copy)
        
        # Sortuj po odległości
        nearby.sort(key=lambda x: x['distance_km'])
        
        return nearby
    
    # ==========================================================================
    # Metody prywatne
    # ==========================================================================
    
    def _fallback_geocode(
        self,
        address: str,
        city: Optional[str] = None,
    ) -> Optional[GeocodingResult]:
        """Fallback geokodowanie (np. używając lokalnej bazy)"""
        # W rzeczywistej implementacji: sprawdź lokalną bazę adresów
        logger.debug(f"Fallback geocoding for: {address}")
        return None
    
    def _calculate_haversine_distance(
        self,
        origin: GeoLocation,
        destination: GeoLocation,
    ) -> DistanceResult:
        """Oblicz odległość w linii prostej używając wzoru Haversine"""
        distance_m = self._haversine_distance(
            origin.lat, origin.lng,
            destination.lat, destination.lng
        ) * 1000  # km -> m
        
        # Szacowany czas (zakładając 40 km/h średnio)
        duration_s = int((distance_m / 1000) / 40 * 3600)
        
        return DistanceResult(
            origin=origin,
            destination=destination,
            distance_meters=int(distance_m),
            duration_seconds=duration_s,
            distance_text=f"{distance_m/1000:.1f} km",
            duration_text=f"{duration_s//60} min",
        )
    
    def _haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float:
        """Oblicz odległość Haversine w km"""
        R = 6371  # Promień Ziemi w km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    async def _optimize_with_google(
        self,
        waypoints: List[RouteWaypoint],
        start_location: Optional[GeoLocation],
        end_location: Optional[GeoLocation],
        mode: str,
    ) -> OptimizedRoute:
        """Optymalizuj trasę używając Google Directions API"""
        # Przygotuj punkty
        origin = start_location or waypoints[0].location
        destination = end_location or waypoints[-1].location
        
        # Punkty pośrednie (bez pierwszego i ostatniego jeśli są start/end)
        intermediate = waypoints
        if start_location is None:
            intermediate = intermediate[1:]
        if end_location is None:
            intermediate = intermediate[:-1]
        
        waypoint_str = '|'.join([
            f"{wp.location.lat},{wp.location.lng}"
            for wp in intermediate
        ])
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/directions/json",
                params={
                    'origin': f"{origin.lat},{origin.lng}",
                    'destination': f"{destination.lat},{destination.lng}",
                    'waypoints': f"optimize:true|{waypoint_str}",
                    'mode': mode,
                    'key': self.api_key,
                    'language': 'pl',
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'OK':
                raise Exception(f"Directions API error: {data['status']}")
            
            route = data['routes'][0]
            waypoint_order = route.get('waypoint_order', list(range(len(intermediate))))
            
            # Zbuduj optymalną kolejność
            optimized_waypoints = []
            if start_location is None:
                optimized_waypoints.append(waypoints[0])
            
            for idx in waypoint_order:
                optimized_waypoints.append(intermediate[idx])
            
            if end_location is None:
                optimized_waypoints.append(waypoints[-1])
            
            # Parsuj legs
            legs = []
            total_distance = 0
            total_duration = 0
            
            for leg in route['legs']:
                total_distance += leg['distance']['value']
                total_duration += leg['duration']['value']
                
                start = leg['start_location']
                end = leg['end_location']
                
                legs.append(DistanceResult(
                    origin=GeoLocation(lat=start['lat'], lng=start['lng']),
                    destination=GeoLocation(lat=end['lat'], lng=end['lng']),
                    distance_meters=leg['distance']['value'],
                    duration_seconds=leg['duration']['value'],
                    distance_text=leg['distance']['text'],
                    duration_text=leg['duration']['text'],
                ))
            
            # Dodaj czas postojów
            total_with_stops = total_duration + sum(wp.duration_minutes * 60 for wp in optimized_waypoints)
            
            return OptimizedRoute(
                waypoints=optimized_waypoints,
                total_distance_meters=total_distance,
                total_duration_seconds=total_duration,
                total_duration_with_stops=total_with_stops,
                legs=legs,
            )
            
        except Exception as e:
            logger.error(f"Google route optimization error: {e}")
            return self._optimize_nearest_neighbor(waypoints, start_location, end_location)
    
    def _optimize_nearest_neighbor(
        self,
        waypoints: List[RouteWaypoint],
        start_location: Optional[GeoLocation],
        end_location: Optional[GeoLocation],
    ) -> OptimizedRoute:
        """Prosta optymalizacja algorytmem najbliższego sąsiada"""
        if not waypoints:
            raise ValueError("No waypoints provided")
        
        # Zacznij od pierwszego punktu lub podanej lokalizacji
        current = start_location or waypoints[0].location
        remaining = list(waypoints)
        
        if start_location is None:
            remaining = remaining[1:]
        
        optimized = []
        if start_location is None:
            optimized.append(waypoints[0])
        
        total_distance = 0
        legs = []
        
        while remaining:
            # Znajdź najbliższy punkt
            nearest_idx = min(
                range(len(remaining)),
                key=lambda i: self._haversine_distance(
                    current.lat, current.lng,
                    remaining[i].location.lat, remaining[i].location.lng
                )
            )
            
            nearest = remaining.pop(nearest_idx)
            distance = self._haversine_distance(
                current.lat, current.lng,
                nearest.location.lat, nearest.location.lng
            ) * 1000  # m
            
            total_distance += distance
            
            legs.append(DistanceResult(
                origin=current,
                destination=nearest.location,
                distance_meters=int(distance),
                duration_seconds=int(distance / 1000 / 40 * 3600),  # ~40 km/h
                distance_text=f"{distance/1000:.1f} km",
                duration_text=f"{int(distance/1000/40*60)} min",
            ))
            
            optimized.append(nearest)
            current = nearest.location
        
        # Dodaj ostatni leg jeśli mamy end_location
        if end_location:
            distance = self._haversine_distance(
                current.lat, current.lng,
                end_location.lat, end_location.lng
            ) * 1000
            
            total_distance += distance
            
            legs.append(DistanceResult(
                origin=current,
                destination=end_location,
                distance_meters=int(distance),
                duration_seconds=int(distance / 1000 / 40 * 3600),
                distance_text=f"{distance/1000:.1f} km",
                duration_text=f"{int(distance/1000/40*60)} min",
            ))
        
        total_duration = sum(leg.duration_seconds for leg in legs)
        total_with_stops = total_duration + sum(wp.duration_minutes * 60 for wp in optimized)
        
        return OptimizedRoute(
            waypoints=optimized,
            total_distance_meters=int(total_distance),
            total_duration_seconds=total_duration,
            total_duration_with_stops=total_with_stops,
            legs=legs,
        )
    
    async def close(self):
        """Zamknij klienta HTTP"""
        await self.client.aclose()


# Singleton instance
_maps_service: Optional[GoogleMapsService] = None


def get_google_maps_service() -> GoogleMapsService:
    """Get singleton Google Maps service instance"""
    global _maps_service
    if _maps_service is None:
        _maps_service = GoogleMapsService()
    return _maps_service
