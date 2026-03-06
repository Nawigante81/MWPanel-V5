"""
Comparable Sales Analysis (Comps) Service

Professional-grade comparable sales analysis for property valuation.
Finds similar properties and calculates adjusted market value estimates.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import math

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.db.models import Offer, OfferType, PropertyType
from app.core.logging import get_logger

logger = get_logger(__name__)


class CompQuality(str, Enum):
    """Quality rating of a comparable property"""
    EXCELLENT = "excellent"  # Very similar, recent sale
    GOOD = "good"            # Similar, minor adjustments needed
    FAIR = "fair"            # Some differences, moderate adjustments
    POOR = "poor"            # Significant differences, large adjustments


@dataclass
class ComparableProperty:
    """A comparable property with adjustment details"""
    # Property details
    offer_id: str
    address: str
    city: str
    district: str
    
    # Sale details
    sale_price: float
    sale_date: datetime
    days_on_market: Optional[int] = None
    
    # Property characteristics
    property_type: str = ""
    area_sqm: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    build_year: Optional[int] = None
    condition: Optional[str] = None
    
    # Features
    has_balcony: bool = False
    has_garden: bool = False
    has_parking: bool = False
    has_elevator: bool = False
    
    # Distance from subject
    distance_km: float = 0.0
    
    # Adjustments
    adjustments: Dict[str, float] = field(default_factory=dict)
    total_adjustment: float = 0.0
    adjusted_price: float = 0.0
    
    # Quality rating
    quality: CompQuality = CompQuality.FAIR
    similarity_score: float = 0.0  # 0-100
    
    def calculate_adjustments(self, subject_property: 'SubjectProperty'):
        """Calculate adjustments relative to subject property"""
        adjustments = {}
        
        # Time adjustment (market conditions)
        days_since_sale = (datetime.utcnow() - self.sale_date).days
        if days_since_sale > 90:
            # Assume 0.5% monthly appreciation
            monthly_appreciation = 0.005
            months_ago = days_since_sale / 30
            time_adjustment = self.sale_price * (monthly_appreciation * months_ago)
            adjustments['time'] = time_adjustment
        
        # Area adjustment (per sqm)
        if self.area_sqm and subject_property.area_sqm:
            area_diff = subject_property.area_sqm - self.area_sqm
            # Assume 3000 PLN per sqm adjustment
            price_per_sqm = self.sale_price / self.area_sqm
            adjustments['area'] = area_diff * price_per_sqm
        
        # Room count adjustment
        if self.rooms and subject_property.rooms:
            room_diff = subject_property.rooms - self.rooms
            # Assume 15000 PLN per room
            adjustments['rooms'] = room_diff * 15000
        
        # Floor adjustment
        if self.floor is not None and subject_property.floor is not None:
            floor_diff = subject_property.floor - self.floor
            # Ground floor discount, top floor premium
            if self.floor == 0 and subject_property.floor > 0:
                adjustments['floor'] = self.sale_price * 0.03  # 3% premium
            elif subject_property.floor == 0 and self.floor > 0:
                adjustments['floor'] = -self.sale_price * 0.03  # 3% discount
        
        # Condition adjustment
        condition_multipliers = {
            'excellent': 1.0,
            'good': 0.95,
            'average': 0.90,
            'poor': 0.80,
            'renovation_needed': 0.70,
        }
        
        if self.condition and subject_property.condition:
            subject_mult = condition_multipliers.get(subject_property.condition, 0.9)
            comp_mult = condition_multipliers.get(self.condition, 0.9)
            if subject_mult != comp_mult:
                adjustments['condition'] = self.sale_price * (subject_mult - comp_mult)
        
        # Feature adjustments
        if self.has_balcony != subject_property.has_balcony:
            if subject_property.has_balcony and not self.has_balcony:
                adjustments['balcony'] = 10000  # Add value for missing balcony
            else:
                adjustments['balcony'] = -10000
        
        if self.has_parking != subject_property.has_parking:
            if subject_property.has_parking and not self.has_parking:
                adjustments['parking'] = 30000  # Add value for missing parking
            else:
                adjustments['parking'] = -30000
        
        if self.has_elevator != subject_property.has_elevator:
            if subject_property.has_elevator and not self.has_elevator:
                adjustments['elevator'] = 15000
            else:
                adjustments['elevator'] = -15000
        
        # Location adjustment based on distance
        if self.distance_km > 1.0:
            # Assume 2% price reduction per km beyond 1km
            location_adjustment = -self.sale_price * (0.02 * (self.distance_km - 1))
            adjustments['location'] = location_adjustment
        
        self.adjustments = adjustments
        self.total_adjustment = sum(adjustments.values())
        self.adjusted_price = self.sale_price + self.total_adjustment
        
        # Calculate similarity score
        self._calculate_similarity_score(subject_property)
    
    def _calculate_similarity_score(self, subject: 'SubjectProperty'):
        """Calculate similarity score (0-100)"""
        scores = []
        
        # Area similarity (30%)
        if self.area_sqm and subject.area_sqm:
            area_diff_pct = abs(self.area_sqm - subject.area_sqm) / subject.area_sqm
            scores.append((1 - min(area_diff_pct, 1)) * 30)
        
        # Room similarity (20%)
        if self.rooms and subject.rooms:
            room_diff = abs(self.rooms - subject.rooms)
            scores.append(max(0, 20 - room_diff * 5))
        
        # Location similarity (25%)
        distance_score = max(0, 25 - self.distance_km * 5)
        scores.append(distance_score)
        
        # Time similarity (15%)
        days_since_sale = (datetime.utcnow() - self.sale_date).days
        time_score = max(0, 15 - days_since_sale * 0.1)
        scores.append(time_score)
        
        # Feature similarity (10%)
        feature_matches = sum([
            self.has_balcony == subject.has_balcony,
            self.has_parking == subject.has_parking,
            self.has_elevator == subject.has_elevator,
        ])
        scores.append((feature_matches / 3) * 10)
        
        self.similarity_score = sum(scores)
        
        # Determine quality rating
        if self.similarity_score >= 85:
            self.quality = CompQuality.EXCELLENT
        elif self.similarity_score >= 70:
            self.quality = CompQuality.GOOD
        elif self.similarity_score >= 50:
            self.quality = CompQuality.FAIR
        else:
            self.quality = CompQuality.POOR


@dataclass
class SubjectProperty:
    """The property being valued"""
    address: str
    city: str
    district: str
    zip_code: Optional[str] = None
    
    property_type: str = ""
    offer_type: OfferType = OfferType.SALE
    area_sqm: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    build_year: Optional[int] = None
    condition: Optional[str] = None
    
    has_balcony: bool = False
    has_garden: bool = False
    has_parking: bool = False
    has_elevator: bool = False
    
    # Coordinates for distance calculation
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class CompsAnalysisResult:
    """Result of comparable sales analysis"""
    subject_property: SubjectProperty
    comparables: List[ComparableProperty]
    
    # Value estimates
    estimated_value_min: float = 0.0
    estimated_value_max: float = 0.0
    estimated_value_mean: float = 0.0
    estimated_value_median: float = 0.0
    estimated_value_per_sqm: float = 0.0
    
    # Confidence metrics
    confidence_score: float = 0.0  # 0-100
    confidence_level: str = "low"  # low, medium, high
    
    # Market metrics
    avg_days_on_market: float = 0.0
    price_trend: str = "stable"  # rising, stable, falling
    
    # Adjustment summary
    total_adjustments_range: Tuple[float, float] = (0.0, 0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'subject_property': {
                'address': self.subject_property.address,
                'city': self.subject_property.city,
                'district': self.subject_property.district,
                'area_sqm': self.subject_property.area_sqm,
                'rooms': self.subject_property.rooms,
            },
            'value_estimate': {
                'min': round(self.estimated_value_min, 2),
                'max': round(self.estimated_value_max, 2),
                'mean': round(self.estimated_value_mean, 2),
                'median': round(self.estimated_value_median, 2),
                'per_sqm': round(self.estimated_value_per_sqm, 2),
            },
            'confidence': {
                'score': round(self.confidence_score, 1),
                'level': self.confidence_level,
            },
            'market_metrics': {
                'avg_days_on_market': round(self.avg_days_on_market, 1),
                'price_trend': self.price_trend,
            },
            'comparables': [
                {
                    'offer_id': comp.offer_id,
                    'address': comp.address,
                    'sale_price': comp.sale_price,
                    'adjusted_price': round(comp.adjusted_price, 2),
                    'adjustments': {k: round(v, 2) for k, v in comp.adjustments.items()},
                    'total_adjustment': round(comp.total_adjustment, 2),
                    'similarity_score': round(comp.similarity_score, 1),
                    'quality': comp.quality.value,
                    'sale_date': comp.sale_date.isoformat() if comp.sale_date else None,
                    'distance_km': round(comp.distance_km, 2),
                }
                for comp in self.comparables
            ],
        }


class CompsAnalyzer:
    """
    Professional comparable sales analyzer.
    
    Features:
    - Automated comparable property search
    - Multi-factor similarity scoring
    - Automated adjustments
    - Statistical value estimation
    - Market trend analysis
    """
    
    # Adjustment percentages
    MAX_TIME_ADJUSTMENT = 0.15  # 15% max for time
    MAX_LOCATION_ADJUSTMENT = 0.10  # 10% max for location
    MAX_TOTAL_ADJUSTMENT = 0.25  # 25% max total adjustment
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    async def find_comps(
        self,
        subject: SubjectProperty,
        max_results: int = 10,
        max_age_days: int = 180,
        max_distance_km: float = 2.0,
        min_similarity_score: float = 40.0
    ) -> CompsAnalysisResult:
        """
        Find comparable sales for a subject property.
        
        Args:
            subject: The property being valued
            max_results: Maximum number of comparables to return
            max_age_days: Maximum age of comparable sales
            max_distance_km: Maximum distance for comparables
            min_similarity_score: Minimum similarity score threshold
            
        Returns:
            CompsAnalysisResult with value estimates
        """
        # Build query for comparable properties
        query = self.db.query(Offer).filter(
            Offer.offer_type == subject.offer_type,
            Offer.property_type == subject.property_type,
            Offer.is_active == True,
            Offer.created_at >= datetime.utcnow() - timedelta(days=max_age_days)
        )
        
        # Location filter
        if subject.city:
            query = query.filter(Offer.city == subject.city)
        
        # Area range filter (±30%)
        if subject.area_sqm:
            min_area = subject.area_sqm * 0.7
            max_area = subject.area_sqm * 1.3
            query = query.filter(
                Offer.area_sqm >= min_area,
                Offer.area_sqm <= max_area
            )
        
        # Room filter (±1 room)
        if subject.rooms:
            query = query.filter(
                Offer.rooms >= subject.rooms - 1,
                Offer.rooms <= subject.rooms + 1
            )
        
        # Get potential comparables
        potential_comps = query.all()
        
        # Convert to ComparableProperty objects and calculate scores
        comparables = []
        for offer in potential_comps:
            comp = self._offer_to_comparable(offer, subject)
            if comp:
                comp.calculate_adjustments(subject)
                
                # Filter by similarity score
                if comp.similarity_score >= min_similarity_score:
                    comparables.append(comp)
        
        # Sort by similarity score
        comparables.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Take top results
        comparables = comparables[:max_results]
        
        # Build result
        result = CompsAnalysisResult(
            subject_property=subject,
            comparables=comparables
        )
        
        # Calculate value estimates
        self._calculate_value_estimates(result)
        
        # Calculate confidence
        self._calculate_confidence(result)
        
        return result
    
    def _offer_to_comparable(
        self,
        offer: Offer,
        subject: SubjectProperty
    ) -> Optional[ComparableProperty]:
        """Convert an Offer to a ComparableProperty"""
        try:
            # Calculate distance
            distance = self._calculate_distance(subject, offer)
            
            return ComparableProperty(
                offer_id=str(offer.id),
                address=offer.address or "",
                city=offer.city or "",
                district=offer.district or "",
                sale_price=offer.price,
                sale_date=offer.created_at,
                area_sqm=offer.area_sqm,
                rooms=offer.rooms,
                floor=offer.floor,
                total_floors=offer.total_floors,
                build_year=offer.build_year,
                condition=offer.condition,
                has_balcony=offer.has_balcony or False,
                has_garden=offer.has_garden or False,
                has_parking=offer.has_parking or False,
                has_elevator=offer.has_elevator or False,
                distance_km=distance,
            )
        except Exception as e:
            logger.warning(f"Error converting offer to comparable: {e}")
            return None
    
    def _calculate_distance(
        self,
        subject: SubjectProperty,
        offer: Offer
    ) -> float:
        """Calculate distance between subject and comparable"""
        # If coordinates available, use Haversine formula
        if (subject.latitude and subject.longitude and
            offer.latitude and offer.longitude):
            return self._haversine_distance(
                subject.latitude, subject.longitude,
                offer.latitude, offer.longitude
            )
        
        # Otherwise, estimate based on district match
        if subject.district and offer.district:
            if subject.district == offer.district:
                return 0.5  # Same district, estimate 500m
            else:
                return 1.5  # Different district, estimate 1.5km
        
        return 2.0  # Unknown distance
    
    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """Calculate Haversine distance between two points in km"""
        R = 6371  # Earth's radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _calculate_value_estimates(self, result: CompsAnalysisResult):
        """Calculate value estimates from comparables"""
        if not result.comparables:
            return
        
        # Get adjusted prices
        adjusted_prices = [comp.adjusted_price for comp in result.comparables]
        
        # Remove outliers (beyond 2 standard deviations)
        if len(adjusted_prices) >= 4:
            mean_price = sum(adjusted_prices) / len(adjusted_prices)
            variance = sum((p - mean_price) ** 2 for p in adjusted_prices) / len(adjusted_prices)
            std_dev = math.sqrt(variance)
            
            filtered_prices = [
                p for p in adjusted_prices
                if abs(p - mean_price) <= 2 * std_dev
            ]
            if filtered_prices:
                adjusted_prices = filtered_prices
        
        if not adjusted_prices:
            return
        
        # Calculate statistics
        result.estimated_value_min = min(adjusted_prices)
        result.estimated_value_max = max(adjusted_prices)
        result.estimated_value_mean = sum(adjusted_prices) / len(adjusted_prices)
        
        # Median
        sorted_prices = sorted(adjusted_prices)
        n = len(sorted_prices)
        if n % 2 == 0:
            result.estimated_value_median = (sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2
        else:
            result.estimated_value_median = sorted_prices[n//2]
        
        # Price per sqm
        if result.subject_property.area_sqm:
            result.estimated_value_per_sqm = (
                result.estimated_value_median / result.subject_property.area_sqm
            )
        
        # Average days on market
        days_on_market = [
            comp.days_on_market for comp in result.comparables
            if comp.days_on_market is not None
        ]
        if days_on_market:
            result.avg_days_on_market = sum(days_on_market) / len(days_on_market)
    
    def _calculate_confidence(self, result: CompsAnalysisResult):
        """Calculate confidence score for the analysis"""
        if not result.comparables:
            result.confidence_score = 0
            result.confidence_level = "low"
            return
        
        scores = []
        
        # Number of comparables (max 30 points)
        num_comps = len(result.comparables)
        scores.append(min(30, num_comps * 3))
        
        # Average similarity score (max 30 points)
        avg_similarity = sum(c.similarity_score for c in result.comparables) / num_comps
        scores.append(avg_similarity * 0.3)
        
        # Quality of comparables (max 20 points)
        excellent_count = sum(1 for c in result.comparables if c.quality == CompQuality.EXCELLENT)
        good_count = sum(1 for c in result.comparables if c.quality == CompQuality.GOOD)
        scores.append(excellent_count * 5 + good_count * 3)
        
        # Adjustment size (max 20 points) - smaller adjustments = higher confidence
        avg_adjustment_pct = sum(
            abs(c.total_adjustment) / c.sale_price
            for c in result.comparables
        ) / num_comps
        adjustment_score = max(0, 20 - avg_adjustment_pct * 100)
        scores.append(adjustment_score)
        
        result.confidence_score = sum(scores)
        
        # Determine confidence level
        if result.confidence_score >= 75:
            result.confidence_level = "high"
        elif result.confidence_score >= 50:
            result.confidence_level = "medium"
        else:
            result.confidence_level = "low"
    
    async def analyze_market_trends(
        self,
        city: str,
        district: Optional[str] = None,
        property_type: Optional[str] = None,
        months: int = 12
    ) -> Dict[str, Any]:
        """Analyze market trends for an area"""
        start_date = datetime.utcnow() - timedelta(days=30 * months)
        
        query = self.db.query(Offer).filter(
            Offer.city == city,
            Offer.created_at >= start_date,
            Offer.is_active == True
        )
        
        if district:
            query = query.filter(Offer.district == district)
        if property_type:
            query = query.filter(Offer.property_type == property_type)
        
        offers = query.all()
        
        if not offers:
            return {'error': 'No data available'}
        
        # Group by month
        monthly_data = {}
        for offer in offers:
            month_key = offer.created_at.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(offer)
        
        # Calculate monthly averages
        monthly_averages = {}
        for month, month_offers in monthly_data.items():
            prices = [o.price for o in month_offers if o.price]
            if prices:
                monthly_averages[month] = {
                    'avg_price': sum(prices) / len(prices),
                    'median_price': sorted(prices)[len(prices) // 2],
                    'count': len(prices),
                }
        
        # Calculate trend
        sorted_months = sorted(monthly_averages.keys())
        if len(sorted_months) >= 2:
            first_month = monthly_averages[sorted_months[0]]['avg_price']
            last_month = monthly_averages[sorted_months[-1]]['avg_price']
            
            if first_month > 0:
                total_change = ((last_month - first_month) / first_month) * 100
                annualized_change = total_change / (len(sorted_months) / 12)
            else:
                total_change = 0
                annualized_change = 0
        else:
            total_change = 0
            annualized_change = 0
        
        return {
            'city': city,
            'district': district,
            'property_type': property_type,
            'period_months': months,
            'total_transactions': len(offers),
            'monthly_averages': monthly_averages,
            'price_trend': {
                'total_change_percent': round(total_change, 2),
                'annualized_change_percent': round(annualized_change, 2),
                'direction': 'rising' if annualized_change > 2 else 'falling' if annualized_change < -2 else 'stable',
            },
            'current_metrics': {
                'avg_price': monthly_averages.get(sorted_months[-1], {}).get('avg_price', 0),
                'median_price': monthly_averages.get(sorted_months[-1], {}).get('median_price', 0),
            }
        }


# Convenience function

async def quick_value_estimate(
    db_session: Session,
    city: str,
    district: str,
    area_sqm: float,
    rooms: int,
    property_type: str = "apartment"
) -> Dict[str, Any]:
    """
    Quick property value estimate.
    
    Args:
        db_session: Database session
        city: City name
        district: District name
        area_sqm: Property area in sqm
        rooms: Number of rooms
        property_type: Type of property
        
    Returns:
        Value estimate with comparables
    """
    subject = SubjectProperty(
        address="",
        city=city,
        district=district,
        property_type=property_type,
        area_sqm=area_sqm,
        rooms=rooms
    )
    
    analyzer = CompsAnalyzer(db_session)
    result = await analyzer.find_comps(subject)
    
    return result.to_dict()
