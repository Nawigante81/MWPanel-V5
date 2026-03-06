"""
Tests for fingerprint generation and deduplication.
"""
import pytest
from decimal import Decimal

from app.fingerprint import generate_fingerprint, canonicalize_url
from app.schemas import OfferNormalized


class TestFingerprintGeneration:
    """Test fingerprint generation logic."""
    
    def test_fingerprint_determinism(self):
        """Same input should produce same fingerprint."""
        offer = OfferNormalized(
            source="test",
            url="https://example.com/offer/123",
            title="Test Apartment",
            price=Decimal("450000"),
            currency="PLN",
            city="Gdansk",
            region="pomorskie",
            area_m2=45.5,
            rooms=2,
        )
        
        fp1 = generate_fingerprint("test", offer)
        fp2 = generate_fingerprint("test", offer)
        
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex length
    
    def test_fingerprint_different_sources(self):
        """Same offer from different sources should have different fingerprints."""
        offer = OfferNormalized(
            source="test",
            url="https://example.com/offer/123",
            title="Test Apartment",
            price=Decimal("450000"),
        )
        
        fp1 = generate_fingerprint("source1", offer)
        fp2 = generate_fingerprint("source2", offer)
        
        assert fp1 != fp2
    
    def test_fingerprint_url_based(self):
        """Stable URLs should use URL-based fingerprinting."""
        offer = OfferNormalized(
            source="test",
            url="https://example.com/offer/123",
            title="Test Apartment",
            price=Decimal("450000"),
        )
        
        fp = generate_fingerprint("test", offer, "https://example.com/offer/123")
        
        # Should be URL-based (64 char hex)
        assert len(fp) == 64
    
    def test_fingerprint_fallback(self):
        """Unstable URLs should use content-based fingerprinting."""
        offer = OfferNormalized(
            source="test",
            url="https://example.com/offer/123?session=abc&tracking=xyz",
            title="Test Apartment",
            price=Decimal("450000"),
            city="Gdansk",
            area_m2=45.5,
            rooms=2,
        )
        
        fp = generate_fingerprint("test", offer)
        
        # Should still produce valid fingerprint
        assert len(fp) == 64
    
    def test_fingerprint_price_change(self):
        """Price change should create different fingerprint with fallback."""
        offer1 = OfferNormalized(
            source="test",
            url="https://example.com/offer/123?tracking=1",
            title="Test Apartment",
            price=Decimal("450000"),
            city="Gdansk",
            area_m2=45.5,
            rooms=2,
        )
        
        offer2 = OfferNormalized(
            source="test",
            url="https://example.com/offer/123?tracking=2",
            title="Test Apartment",
            price=Decimal("460000"),  # Different price
            city="Gdansk",
            area_m2=45.5,
            rooms=2,
        )
        
        fp1 = generate_fingerprint("test", offer1)
        fp2 = generate_fingerprint("test", offer2)
        
        # Should be different due to price difference
        assert fp1 != fp2


class TestCanonicalizeUrl:
    """Test URL canonicalization."""
    
    def test_remove_tracking_params(self):
        """Tracking parameters should be removed."""
        url = "https://example.com/offer/123?utm_source=google&fbclid=abc"
        canonical = canonicalize_url(url, "test")
        
        assert "utm_source" not in canonical
        assert "fbclid" not in canonical
        assert "https://example.com/offer/123" in canonical
    
    def test_preserve_essential_params(self):
        """Essential parameters should be preserved."""
        url = "https://example.com/offer/123?page=2&category=apartments"
        canonical = canonicalize_url(url, "test")
        
        assert "page=2" in canonical
        assert "category=apartments" in canonical
    
    def test_handle_no_params(self):
        """URLs without params should remain unchanged."""
        url = "https://example.com/offer/123"
        canonical = canonicalize_url(url, "test")
        
        assert canonical == url


class TestFingerprintEdgeCases:
    """Test edge cases for fingerprinting."""
    
    def test_empty_offer(self):
        """Minimal offer should still produce fingerprint."""
        offer = OfferNormalized(
            source="test",
            url="https://example.com/offer/123",
            title="Test",
        )
        
        fp = generate_fingerprint("test", offer)
        assert len(fp) == 64
    
    def test_unicode_title(self):
        """Unicode titles should be handled correctly."""
        offer = OfferNormalized(
            source="test",
            url="https://example.com/offer/123",
            title="Mieszkanie w Gdańsku - świetna lokalizacja!",
            price=Decimal("450000"),
            city="Gdańsk",
        )
        
        fp = generate_fingerprint("test", offer)
        assert len(fp) == 64
    
    def test_special_characters_in_url(self):
        """URLs with special characters should be handled."""
        offer = OfferNormalized(
            source="test",
            url="https://example.com/offer/test-123%20special",
            title="Test",
        )
        
        fp = generate_fingerprint("test", offer)
        assert len(fp) == 64
