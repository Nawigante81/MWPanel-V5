"""
Normalization utilities for offer data.
Handles price, area, rooms, and location normalization.
"""
import re
from decimal import Decimal
from typing import Optional, Tuple

from app.logging_config import get_logger

logger = get_logger("normalize")


class PriceNormalizer:
    """Normalize price values from various formats."""
    
    CURRENCY_MAP = {
        "zł": "PLN",
        "zl": "PLN",
        "pln": "PLN",
        "€": "EUR",
        "eur": "EUR",
        "$": "USD",
        "usd": "USD",
    }
    
    @classmethod
    def normalize(cls, price_text: Optional[str]) -> Tuple[Optional[Decimal], Optional[str]]:
        """
        Extract price and currency from text.
        
        Returns:
            Tuple of (price, currency)
        """
        if not price_text:
            return None, None
        
        text = price_text.lower().strip()
        
        # Extract currency
        currency = cls._extract_currency(text)
        
        # Extract numeric value
        price = cls._extract_price(text)
        
        return price, currency
    
    @classmethod
    def _extract_currency(cls, text: str) -> Optional[str]:
        """Extract currency code from text."""
        for symbol, code in cls.CURRENCY_MAP.items():
            if symbol in text:
                return code
        
        # Default to PLN for Polish listings
        return "PLN"
    
    @classmethod
    def _extract_price(cls, text: str) -> Optional[Decimal]:
        """Extract numeric price from text."""
        # Remove currency symbols and whitespace
        cleaned = text
        for symbol in cls.CURRENCY_MAP.keys():
            cleaned = cleaned.replace(symbol, "")
        
        # Extract all numbers
        # Handle formats: "450 000", "450,000", "450.000", "450000"
        numbers = re.findall(r'[\d\s,\.]+', cleaned)
        
        if not numbers:
            return None
        
        # Take the first/largest number
        number_str = numbers[0]
        
        # Remove all whitespace (including non-breaking spaces)
        number_str = re.sub(r"\s+", "", number_str)
        
        # Handle European format (comma as decimal separator)
        # If there's a comma with 2 digits after, it's likely decimal
        if "," in number_str:
            parts = number_str.split(",")
            if len(parts[-1]) == 2:
                # Decimal part
                number_str = number_str.replace(",", ".")
            else:
                # Thousands separator
                number_str = number_str.replace(",", "")
        
        try:
            return Decimal(number_str)
        except Exception:
            logger.warning(f"Failed to parse price: {text}")
            return None


class AreaNormalizer:
    """Normalize area values from various formats."""
    
    @classmethod
    def normalize(cls, area_text: Optional[str]) -> Optional[float]:
        """
        Extract area in square meters from text.
        
        Handles formats:
        - "45.5 m²"
        - "45,5 m2"
        - "45.5"
        - "45,5"
        """
        if not area_text:
            return None
        
        text = area_text.lower().strip()
        
        # Remove area units
        text = re.sub(r'm[²2]?\s*$', '', text)
        text = text.strip()
        
        # Extract number
        match = re.search(r'[\d\s,\.]+', text)
        
        if not match:
            return None
        
        number_str = match.group()
        number_str = number_str.replace(" ", "")
        
        # Handle comma as decimal separator
        if "," in number_str:
            parts = number_str.split(",")
            if len(parts[-1]) <= 2:
                number_str = number_str.replace(",", ".")
            else:
                number_str = number_str.replace(",", "")
        
        try:
            return float(number_str)
        except Exception:
            logger.warning(f"Failed to parse area: {area_text}")
            return None


class RoomsNormalizer:
    """Normalize room count from various formats."""
    
    @classmethod
    def normalize(cls, rooms_text: Optional[str]) -> Optional[int]:
        """
        Extract room count from text.
        
        Handles formats:
        - "3 pokoje"
        - "3"
        - "trzy"
        - "3 pok."
        """
        if not rooms_text:
            return None
        
        text = rooms_text.lower().strip()
        
        # Direct number
        if text.isdigit():
            return int(text)
        
        # Extract first number
        match = re.search(r'\d+', text)
        if match:
            return int(match.group())
        
        # Polish word numbers
        polish_numbers = {
            "kawalerka": 1,
            "jeden": 1,
            "jednopokojowe": 1,
            "dwa": 2,
            "dwupokojowe": 2,
            "trzy": 3,
            "trzypokojowe": 3,
            "cztery": 4,
            "czteropokojowe": 4,
            "pięć": 5,
            "pięciopokojowe": 5,
        }
        
        for word, number in polish_numbers.items():
            if word in text:
                return number
        
        return None


class LocationNormalizer:
    """Normalize location data."""
    
    # Polish voivodeships
    VOIVODESHIPS = {
        "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie",
        "łódzkie", "małopolskie", "mazowieckie", "opolskie",
        "podkarpackie", "podlaskie", "pomorskie", "śląskie",
        "świętokrzyskie", "warmińsko-mazurskie", "wielkopolskie",
        "zachodniopomorskie",
    }
    
    @classmethod
    def normalize_city(cls, city_text: Optional[str]) -> Optional[str]:
        """Normalize city name."""
        if not city_text:
            return None
        
        city = city_text.strip()
        
        # Remove common suffixes
        suffixes = [", polska", ", poland", " (miasto)"]
        for suffix in suffixes:
            city = city.lower().replace(suffix, "")
        
        # Title case
        city = city.strip().title()
        
        return city if city else None
    
    @classmethod
    def normalize_region(cls, region_text: Optional[str]) -> Optional[str]:
        """Normalize region/voivodeship name."""
        if not region_text:
            return None
        
        region = region_text.lower().strip()
        
        # Normalize Polish characters
        region = region.replace("śląskie", "slaskie")
        region = region.replace("łódzkie", "lodzkie")
        
        # Check if it's a valid voivodeship
        for v in cls.VOIVODESHIPS:
            if v in region:
                return v
        
        return region_text.strip() if region_text else None
    
    @classmethod
    def extract_city_region(cls, location_text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract city and region from combined location text.
        
        Example: "Gdańsk, pomorskie" -> ("Gdańsk", "pomorskie")
        """
        if not location_text:
            return None, None
        
        parts = [p.strip() for p in location_text.split(",")]
        
        city = None
        region = None
        
        for part in parts:
            part_lower = part.lower()
            
            # Check if it's a voivodeship
            is_voivodeship = any(v in part_lower for v in cls.VOIVODESHIPS)
            
            if is_voivodeship:
                region = cls.normalize_region(part)
            else:
                city = cls.normalize_city(part)
        
        return city, region


class CoordinateNormalizer:
    """Normalize GPS coordinates."""
    
    @classmethod
    def normalize(
        cls,
        lat: Optional[float],
        lng: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Validate and normalize coordinates.
        
        Returns None if coordinates are invalid.
        """
        if lat is None or lng is None:
            return None, None
        
        # Check ranges
        if not (-90 <= lat <= 90):
            logger.warning(f"Invalid latitude: {lat}")
            return None, None
        
        if not (-180 <= lng <= 180):
            logger.warning(f"Invalid longitude: {lng}")
            return None, None
        
        # Round to reasonable precision (6 decimal places = ~0.1m)
        return round(lat, 6), round(lng, 6)
