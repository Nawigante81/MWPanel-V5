"""
Data Quality Scoring Service

Evaluates the quality and reliability of property listings.
Detects suspicious offers, missing data, and potential scams.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import re

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.db.models import Offer, OfferStatus, PropertyType
from app.core.logging import get_logger

logger = get_logger(__name__)


class QualityFlag(str, Enum):
    """Data quality flags"""
    # Positive flags
    VERIFIED_PHOTOS = "verified_photos"
    DETAILED_DESCRIPTION = "detailed_description"
    COMPLETE_CONTACT = "complete_contact"
    FAST_RESPONSE = "fast_response"
    PREMIUM_LISTING = "premium_listing"
    
    # Negative flags
    PRICE_TOO_LOW = "price_too_low"
    PRICE_TOO_HIGH = "price_too_high"
    MISSING_PHOTOS = "missing_photos"
    MISSING_DESCRIPTION = "missing_description"
    GENERIC_DESCRIPTION = "generic_description"
    NO_CONTACT_INFO = "no_contact_info"
    DUPLICATE_LISTING = "duplicate_listing"
    SUSPICIOUS_PHOTOS = "suspicious_photos"
    STOCK_PHOTOS = "stock_photos"
    FAKE_LOCATION = "fake_location"
    SCAM_INDICATORS = "scam_indicators"
    UNREALISTIC_AREA = "unrealistic_area"
    WRONG_PRICE_PER_SQM = "wrong_price_per_sqm"
    OUTDATED_LISTING = "outdated_listing"
    INACTIVE_SELLER = "inactive_seller"


class QualityLevel(str, Enum):
    """Overall quality levels"""
    EXCELLENT = "excellent"      # 90-100
    GOOD = "good"                # 75-89
    AVERAGE = "average"          # 60-74
    BELOW_AVERAGE = "below_avg"  # 40-59
    POOR = "poor"                # 20-39
    SUSPICIOUS = "suspicious"    # 0-19


@dataclass
class QualityDimension:
    """Quality score for a specific dimension"""
    name: str
    score: float  # 0-100
    weight: float
    flags: List[QualityFlag] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class DataQualityScore:
    """Complete data quality assessment"""
    offer_id: str
    
    # Dimension scores
    completeness: QualityDimension = field(default_factory=lambda: QualityDimension("completeness", 0, 0.25))
    accuracy: QualityDimension = field(default_factory=lambda: QualityDimension("accuracy", 0, 0.20))
    freshness: QualityDimension = field(default_factory=lambda: QualityDimension("freshness", 0, 0.15))
    credibility: QualityDimension = field(default_factory=lambda: QualityDimension("credibility", 0, 0.20))
    presentation: QualityDimension = field(default_factory=lambda: QualityDimension("presentation", 0, 0.20))
    
    # Overall score
    total_score: float = 0.0
    quality_level: str = ""
    
    # Flags
    positive_flags: List[QualityFlag] = field(default_factory=list)
    negative_flags: List[QualityFlag] = field(default_factory=list)
    
    # Risk assessment
    scam_risk_score: float = 0.0  # 0-100, higher = more risky
    is_recommended: bool = False
    
    # Metadata
    assessed_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_total(self):
        """Calculate total quality score"""
        self.total_score = (
            self.completeness.weighted_score +
            self.accuracy.weighted_score +
            self.freshness.weighted_score +
            self.credibility.weighted_score +
            self.presentation.weighted_score
        )
        
        # Determine quality level
        self.quality_level = self._get_quality_level(self.total_score)
        
        # Collect all flags
        self.positive_flags = []
        self.negative_flags = []
        for dim in [self.completeness, self.accuracy, self.freshness, 
                    self.credibility, self.presentation]:
            for flag in dim.flags:
                if flag in [QualityFlag.VERIFIED_PHOTOS, QualityFlag.DETAILED_DESCRIPTION,
                           QualityFlag.COMPLETE_CONTACT, QualityFlag.FAST_RESPONSE,
                           QualityFlag.PREMIUM_LISTING]:
                    self.positive_flags.append(flag)
                else:
                    self.negative_flags.append(flag)
        
        # Determine if recommended
        self.is_recommended = (
            self.total_score >= 60 and
            self.scam_risk_score < 30 and
            QualityFlag.SCAM_INDICATORS not in self.negative_flags
        )
        
        return self.total_score
    
    @staticmethod
    def _get_quality_level(score: float) -> str:
        if score >= 90:
            return QualityLevel.EXCELLENT.value
        elif score >= 75:
            return QualityLevel.GOOD.value
        elif score >= 60:
            return QualityLevel.AVERAGE.value
        elif score >= 40:
            return QualityLevel.BELOW_AVERAGE.value
        elif score >= 20:
            return QualityLevel.POOR.value
        else:
            return QualityLevel.SUSPICIOUS.value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'offer_id': self.offer_id,
            'total_score': round(self.total_score, 1),
            'quality_level': self.quality_level,
            'is_recommended': self.is_recommended,
            'scam_risk_score': round(self.scam_risk_score, 1),
            'dimensions': {
                'completeness': {
                    'score': round(self.completeness.score, 1),
                    'flags': [f.value for f in self.completeness.flags],
                },
                'accuracy': {
                    'score': round(self.accuracy.score, 1),
                    'flags': [f.value for f in self.accuracy.flags],
                },
                'freshness': {
                    'score': round(self.freshness.score, 1),
                    'flags': [f.value for f in self.freshness.flags],
                },
                'credibility': {
                    'score': round(self.credibility.score, 1),
                    'flags': [f.value for f in self.credibility.flags],
                },
                'presentation': {
                    'score': round(self.presentation.score, 1),
                    'flags': [f.value for f in self.presentation.flags],
                },
            },
            'flags': {
                'positive': [f.value for f in self.positive_flags],
                'negative': [f.value for f in self.negative_flags],
            },
            'assessed_at': self.assessed_at.isoformat(),
        }


class DataQualityService:
    """
    Professional data quality assessment service.
    
    Features:
    - Multi-dimensional quality scoring
    - Scam detection algorithms
    - Duplicate detection
    - Market anomaly detection
    """
    
    # Scam indicator phrases
    SCAM_PHRASES = [
        'pilne', 'okazja', 'nie zwlekaj', 'tylko dzisiaj',
        'prześlij pieniądze', 'zapłać z góry', 'western union',
        'moneygram', 'przelew za granicę', 'agent za granicą',
        'nie mogę pokazać', 'klucze u sąsiada', 'wysyłam klucze',
    ]
    
    # Generic description phrases
    GENERIC_PHRASES = [
        'mieszkanie do wynajęcia',
        'mieszkanie na sprzedaż',
        'przytulne mieszkanie',
        'dogodna lokalizacja',
        'polecam',
    ]
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    async def assess_offer(self, offer: Offer) -> DataQualityScore:
        """Assess the quality of an offer"""
        score = DataQualityScore(offer_id=str(offer.id))
        
        # Assess each dimension
        score.completeness = self._assess_completeness(offer)
        score.accuracy = self._assess_accuracy(offer)
        score.freshness = self._assess_freshness(offer)
        score.credibility = self._assess_credibility(offer)
        score.presentation = self._assess_presentation(offer)
        
        # Calculate scam risk
        score.scam_risk_score = self._calculate_scam_risk(offer)
        
        # Calculate total
        score.calculate_total()
        
        return score
    
    def _assess_completeness(self, offer: Offer) -> QualityDimension:
        """Assess data completeness"""
        dim = QualityDimension(name="completeness", score=100, weight=0.25)
        
        required_fields = {
            'price': offer.price is not None and offer.price > 0,
            'area': offer.area_sqm is not None and offer.area_sqm > 0,
            'rooms': offer.rooms is not None and offer.rooms > 0,
            'address': bool(offer.address),
            'city': bool(offer.city),
            'description': bool(offer.description) and len(offer.description) > 50,
            'contact_phone': bool(offer.contact_phone),
            'photos': offer.images and len(offer.images) > 0,
        }
        
        missing_count = sum(1 for v in required_fields.values() if not v)
        
        # Score based on missing fields
        if missing_count == 0:
            dim.score = 100
        elif missing_count == 1:
            dim.score = 85
        elif missing_count == 2:
            dim.score = 70
        elif missing_count == 3:
            dim.score = 55
        else:
            dim.score = max(20, 40 - missing_count * 5)
        
        # Add flags
        if not required_fields['photos']:
            dim.flags.append(QualityFlag.MISSING_PHOTOS)
        if not required_fields['description']:
            dim.flags.append(QualityFlag.MISSING_DESCRIPTION)
        if not required_fields['contact_phone']:
            dim.flags.append(QualityFlag.NO_CONTACT_INFO)
        
        dim.details = {'missing_fields': [k for k, v in required_fields.items() if not v]}
        
        return dim
    
    def _assess_accuracy(self, offer: Offer) -> QualityDimension:
        """Assess data accuracy"""
        dim = QualityDimension(name="accuracy", score=100, weight=0.20)
        issues = []
        
        # Check price per sqm
        if offer.price and offer.area_sqm and offer.area_sqm > 0:
            price_per_sqm = offer.price / offer.area_sqm
            
            # Get market average for location
            market_avg = self._get_market_average_price_per_sqm(offer)
            
            if market_avg > 0:
                deviation = abs(price_per_sqm - market_avg) / market_avg
                
                if deviation > 0.50:  # More than 50% deviation
                    if price_per_sqm < market_avg * 0.5:
                        issues.append('price_too_low')
                        dim.flags.append(QualityFlag.PRICE_TOO_LOW)
                        dim.score -= 25
                    elif price_per_sqm > market_avg * 2:
                        issues.append('price_too_high')
                        dim.flags.append(QualityFlag.PRICE_TOO_HIGH)
                        dim.score -= 15
                elif deviation > 0.30:
                    dim.flags.append(QualityFlag.WRONG_PRICE_PER_SQM)
                    dim.score -= 10
        
        # Check area reasonableness
        if offer.area_sqm:
            if offer.rooms:
                avg_area_per_room = offer.area_sqm / offer.rooms
                if avg_area_per_room < 10:  # Less than 10 sqm per room
                    issues.append('unrealistic_area')
                    dim.flags.append(QualityFlag.UNREALISTIC_AREA)
                    dim.score -= 20
                elif avg_area_per_room > 80:  # More than 80 sqm per room
                    issues.append('unrealistic_area')
                    dim.flags.append(QualityFlag.UNREALISTIC_AREA)
                    dim.score -= 15
        
        # Check for duplicates
        if self._is_duplicate(offer):
            dim.flags.append(QualityFlag.DUPLICATE_LISTING)
            dim.score -= 30
        
        dim.score = max(0, dim.score)
        dim.details = {'issues': issues}
        
        return dim
    
    def _assess_freshness(self, offer: Offer) -> QualityDimension:
        """Assess listing freshness"""
        dim = QualityDimension(name="freshness", score=100, weight=0.15)
        
        if offer.created_at:
            age_days = (datetime.utcnow() - offer.created_at).days
            
            if age_days <= 7:
                dim.score = 100
            elif age_days <= 14:
                dim.score = 90
            elif age_days <= 30:
                dim.score = 80
            elif age_days <= 60:
                dim.score = 65
                dim.flags.append(QualityFlag.OUTDATED_LISTING)
            elif age_days <= 90:
                dim.score = 50
                dim.flags.append(QualityFlag.OUTDATED_LISTING)
            else:
                dim.score = 30
                dim.flags.append(QualityFlag.OUTDATED_LISTING)
            
            dim.details = {'age_days': age_days}
        
        return dim
    
    def _assess_credibility(self, offer: Offer) -> QualityDimension:
        """Assess seller/listing credibility"""
        dim = QualityDimension(name="credibility", score=100, weight=0.20)
        
        # Check seller type
        if offer.seller_type == 'developer':
            dim.score += 5  # Slight bonus for developers
        elif offer.seller_type == 'agency':
            dim.score += 3
        
        # Check for verified information
        if offer.contact_phone:
            # Check if phone format is valid
            if self._is_valid_phone(offer.contact_phone):
                dim.score += 5
            else:
                dim.score -= 10
        
        # Check description for scam indicators
        if offer.description:
            desc_lower = offer.description.lower()
            
            for phrase in self.SCAM_PHRASES:
                if phrase in desc_lower:
                    dim.flags.append(QualityFlag.SCAM_INDICATORS)
                    dim.score -= 30
                    break
        
        # Check for fake location indicators
        if offer.description and offer.address:
            if offer.address.lower() not in offer.description.lower():
                # Address not mentioned in description - possible red flag
                pass  # Not strong enough indicator alone
        
        dim.score = max(0, min(100, dim.score))
        
        return dim
    
    def _assess_presentation(self, offer: Offer) -> QualityDimension:
        """Assess listing presentation quality"""
        dim = QualityDimension(name="presentation", score=100, weight=0.20)
        
        # Photo quality
        if offer.images:
            photo_count = len(offer.images)
            
            if photo_count >= 10:
                dim.score += 10
                dim.flags.append(QualityFlag.VERIFIED_PHOTOS)
            elif photo_count >= 5:
                dim.score += 5
            elif photo_count < 3:
                dim.score -= 15
        else:
            dim.score -= 30
        
        # Description quality
        if offer.description:
            desc_len = len(offer.description)
            
            if desc_len >= 1000:
                dim.score += 15
                dim.flags.append(QualityFlag.DETAILED_DESCRIPTION)
            elif desc_len >= 500:
                dim.score += 10
            elif desc_len >= 200:
                dim.score += 5
            elif desc_len < 100:
                dim.score -= 20
                dim.flags.append(QualityFlag.MISSING_DESCRIPTION)
            
            # Check for generic description
            desc_lower = offer.description.lower()
            generic_count = sum(1 for phrase in self.GENERIC_PHRASES if phrase in desc_lower)
            
            if generic_count >= 3:
                dim.flags.append(QualityFlag.GENERIC_DESCRIPTION)
                dim.score -= 15
        else:
            dim.score -= 30
            dim.flags.append(QualityFlag.MISSING_DESCRIPTION)
        
        # Title quality
        if offer.title:
            if len(offer.title) < 20:
                dim.score -= 10
        
        dim.score = max(0, min(100, dim.score))
        
        return dim
    
    def _calculate_scam_risk(self, offer: Offer) -> float:
        """Calculate scam risk score (0-100, higher = more risky)"""
        risk_score = 0
        risk_factors = []
        
        # Price too low (major red flag)
        if offer.price and offer.area_sqm:
            price_per_sqm = offer.price / offer.area_sqm
            market_avg = self._get_market_average_price_per_sqm(offer)
            
            if market_avg > 0 and price_per_sqm < market_avg * 0.4:
                risk_score += 40
                risk_factors.append('price_60pct_below_market')
            elif market_avg > 0 and price_per_sqm < market_avg * 0.6:
                risk_score += 25
                risk_factors.append('price_40pct_below_market')
        
        # No photos
        if not offer.images:
            risk_score += 20
            risk_factors.append('no_photos')
        
        # Very short description
        if not offer.description or len(offer.description) < 50:
            risk_score += 15
            risk_factors.append('very_short_description')
        
        # No contact phone
        if not offer.contact_phone:
            risk_score += 10
            risk_factors.append('no_phone')
        
        # Scam phrases in description
        if offer.description:
            desc_lower = offer.description.lower()
            scam_phrases_found = [p for p in self.SCAM_PHRASES if p in desc_lower]
            if scam_phrases_found:
                risk_score += 30
                risk_factors.append(f'scam_phrases: {scam_phrases_found}')
        
        # Foreign phone number (for local listings)
        if offer.contact_phone:
            if not self._is_local_phone(offer.contact_phone, offer.city):
                risk_score += 10
                risk_factors.append('foreign_phone')
        
        return min(100, risk_score)
    
    def _get_market_average_price_per_sqm(self, offer: Offer) -> float:
        """Get market average price per sqm for similar properties"""
        query = self.db.query(Offer).filter(
            Offer.city == offer.city,
            Offer.property_type == offer.property_type,
            Offer.area_sqm.isnot(None),
            Offer.price.isnot(None),
            Offer.id != offer.id
        )
        
        if offer.district:
            query = query.filter(Offer.district == offer.district)
        
        results = query.all()
        
        if not results:
            return 0
        
        prices_per_sqm = [r.price / r.area_sqm for r in results if r.area_sqm > 0]
        
        if not prices_per_sqm:
            return 0
        
        # Use median to avoid outliers
        sorted_prices = sorted(prices_per_sqm)
        return sorted_prices[len(sorted_prices) // 2]
    
    def _is_duplicate(self, offer: Offer) -> bool:
        """Check if offer is a duplicate"""
        # Check for similar offers by same contact
        if offer.contact_phone:
            similar = self.db.query(Offer).filter(
                Offer.contact_phone == offer.contact_phone,
                Offer.id != offer.id,
                Offer.price == offer.price,
                Offer.area_sqm == offer.area_sqm,
                Offer.city == offer.city
            ).first()
            
            if similar:
                return True
        
        return False
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Check if phone number format is valid"""
        # Basic Polish phone validation
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        return bool(re.match(r'^(\+48)?\d{9}$', cleaned))
    
    def _is_local_phone(self, phone: str, city: Optional[str]) -> bool:
        """Check if phone is local to the listing city"""
        if not city:
            return True
        
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Check for Polish prefix
        if cleaned.startswith('+48') or cleaned.startswith('48'):
            return True
        
        if len(cleaned) == 9:
            return True
        
        return False
    
    async def batch_assess(self, offer_ids: List[str]) -> Dict[str, DataQualityScore]:
        """Assess multiple offers"""
        results = {}
        
        for offer_id in offer_ids:
            offer = self.db.query(Offer).filter(Offer.id == offer_id).first()
            if offer:
                results[offer_id] = await self.assess_offer(offer)
        
        return results
    
    async def get_quality_statistics(
        self,
        city: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get data quality statistics"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(Offer).filter(Offer.created_at >= start_date)
        
        if city:
            query = query.filter(Offer.city == city)
        
        total_offers = query.count()
        
        if total_offers == 0:
            return {'error': 'No offers found'}
        
        # Count by quality issues
        stats = {
            'total_offers': total_offers,
            'with_photos': query.filter(Offer.images != []).count(),
            'with_description': query.filter(Offer.description.isnot(None)).count(),
            'with_phone': query.filter(Offer.contact_phone.isnot(None)).count(),
            'with_area': query.filter(Offer.area_sqm.isnot(None)).count(),
            'with_rooms': query.filter(Offer.rooms.isnot(None)).count(),
        }
        
        # Calculate percentages
        stats['photos_percentage'] = round(stats['with_photos'] / total_offers * 100, 1)
        stats['description_percentage'] = round(stats['with_description'] / total_offers * 100, 1)
        stats['phone_percentage'] = round(stats['with_phone'] / total_offers * 100, 1)
        
        return stats
