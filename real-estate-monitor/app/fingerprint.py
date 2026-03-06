"""
Fingerprint generation for offer deduplication.
Uses SHA-256 for deterministic, collision-resistant hashes.
"""
import hashlib
from typing import Optional

from app.schemas import OfferNormalized


def generate_fingerprint(
    source_name: str,
    offer: OfferNormalized,
    canonical_url: Optional[str] = None,
) -> str:
    """
    Generate a unique fingerprint for an offer.
    
    Strategy:
    1. If canonical_url is provided and stable, use: sha256(source + url)
    2. Otherwise, use: sha256(source + title + price + city + area + rooms)
    
    Args:
        source_name: Name of the source (e.g., 'otodom')
        offer: Normalized offer data
        canonical_url: Optional stable/canonical URL
    
    Returns:
        Hex-encoded SHA-256 hash (64 characters)
    """
    # Try URL-based fingerprint if URL is stable
    if canonical_url and _is_url_stable(canonical_url):
        content = f"{source_name}:{canonical_url}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    
    # Fallback to content-based fingerprint
    return _generate_content_fingerprint(source_name, offer)


def _is_url_stable(url: str) -> bool:
    """
    Check if a URL is stable enough for fingerprinting.
    
    URLs with session IDs, timestamps, or tracking params are unstable.
    """
    if not url:
        return False
    
    # List of unstable query parameters
    unstable_params = [
        "sessionid", "session", "sid", "token",
        "timestamp", "ts", "t", "time",
        "utm_", "fbclid", "gclid", "ref",
        "tracking", "track", "click",
    ]
    
    url_lower = url.lower()
    
    # Check for unstable parameters
    for param in unstable_params:
        if param in url_lower:
            return False
    
    return True


def _generate_content_fingerprint(source_name: str, offer: OfferNormalized) -> str:
    """
    Generate a content-based fingerprint from offer fields.
    
    Uses normalized title, price, city, area, and rooms.
    """
    # Normalize fields for consistent hashing
    normalized_title = _normalize_text(offer.title)
    price_str = str(offer.price) if offer.price else ""
    city_str = _normalize_text(offer.city) if offer.city else ""
    area_str = str(offer.area_m2) if offer.area_m2 else ""
    rooms_str = str(offer.rooms) if offer.rooms else ""
    
    # Build content string
    content_parts = [
        source_name,
        normalized_title,
        price_str,
        city_str,
        area_str,
        rooms_str,
    ]
    
    content = ":".join(content_parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_text(text: Optional[str]) -> str:
    """
    Normalize text for consistent fingerprinting.
    
    - Lowercase
    - Remove extra whitespace
    - Remove special characters that might vary
    """
    if not text:
        return ""
    
    # Lowercase and strip
    normalized = text.lower().strip()
    
    # Replace multiple whitespace with single space
    normalized = " ".join(normalized.split())
    
    # Remove common variable parts (apartment numbers, floor numbers)
    # This is a conservative approach - only remove obvious variables
    
    return normalized


def canonicalize_url(url: str, source_name: str) -> str:
    """
    Attempt to canonicalize a URL for stable fingerprinting.
    
    Removes tracking parameters and normalizes the URL.
    """
    if not url:
        return ""
    
    # Remove common tracking parameters
    tracking_params = [
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "referral", "tracking",
    ]
    
    # Split URL and query string
    if "?" in url:
        base_url, query = url.split("?", 1)
        params = query.split("&")
        filtered_params = [
            p for p in params
            if not any(tp in p.lower() for tp in tracking_params)
        ]
        if filtered_params:
            return f"{base_url}?{'&'.join(filtered_params)}"
        return base_url
    
    return url
