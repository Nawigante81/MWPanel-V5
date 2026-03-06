"""
Neighborhood Scoring Service

Professional neighborhood analysis and scoring system.
Evaluates locations based on multiple factors important for
real estate investment and living quality.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)


class ScoreCategory(str, Enum):
    """Categories for neighborhood scoring"""
    TRANSPORT = "transport"
    EDUCATION = "education"
    SHOPPING = "shopping"
    HEALTHCARE = "healthcare"
    SAFETY = "safety"
    GREENERY = "greenery"
    ENTERTAINMENT = "entertainment"
    INVESTMENT = "investment"
    OVERALL = "overall"


class ScoreLevel(str, Enum):
    """Score quality levels"""
    EXCELLENT = "excellent"    # 90-100
    VERY_GOOD = "very_good"    # 80-89
    GOOD = "good"              # 70-79
    AVERAGE = "average"        # 60-69
    BELOW_AVERAGE = "below_average"  # 50-59
    POOR = "poor"              # Below 50


@dataclass
class TransportScore:
    """Transportation accessibility score"""
    metro_distance_m: Optional[int] = None
    bus_stop_distance_m: Optional[int] = None
    tram_distance_m: Optional[int] = None
    train_station_distance_m: Optional[int] = None
    
    metro_score: float = 0.0
    bus_score: float = 0.0
    tram_score: float = 0.0
    train_score: float = 0.0
    
    bike_lanes_km: float = 0.0
    walkability_score: float = 0.0
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate transport score"""
        # Metro score (highest weight)
        if self.metro_distance_m is not None:
            if self.metro_distance_m <= 500:
                self.metro_score = 100
            elif self.metro_distance_m <= 1000:
                self.metro_score = 80
            elif self.metro_distance_m <= 1500:
                self.metro_score = 60
            elif self.metro_distance_m <= 2000:
                self.metro_score = 40
            else:
                self.metro_score = 20
        
        # Bus score
        if self.bus_stop_distance_m is not None:
            if self.bus_stop_distance_m <= 300:
                self.bus_score = 100
            elif self.bus_stop_distance_m <= 600:
                self.bus_score = 80
            elif self.bus_stop_distance_m <= 1000:
                self.bus_score = 60
            else:
                self.bus_score = 40
        
        # Tram score
        if self.tram_distance_m is not None:
            if self.tram_distance_m <= 500:
                self.tram_score = 100
            elif self.tram_distance_m <= 1000:
                self.tram_score = 75
            elif self.tram_distance_m <= 1500:
                self.tram_score = 50
            else:
                self.tram_score = 25
        
        # Train score
        if self.train_station_distance_m is not None:
            if self.train_station_distance_m <= 1000:
                self.train_score = 100
            elif self.train_station_distance_m <= 2000:
                self.train_score = 70
            elif self.train_station_distance_m <= 3000:
                self.train_score = 40
            else:
                self.train_score = 20
        
        # Calculate weighted overall
        self.overall = (
            self.metro_score * 0.35 +
            self.bus_score * 0.20 +
            self.tram_score * 0.20 +
            self.train_score * 0.10 +
            self.walkability_score * 0.15
        )
        
        return self.overall


@dataclass
class EducationScore:
    """Education facilities score"""
    primary_schools_count: int = 0
    primary_school_distance_m: Optional[int] = None
    primary_school_rating: float = 0.0
    
    secondary_schools_count: int = 0
    secondary_school_distance_m: Optional[int] = None
    secondary_school_rating: float = 0.0
    
    kindergartens_count: int = 0
    kindergarten_distance_m: Optional[int] = None
    
    universities_count: int = 0
    university_distance_m: Optional[int] = None
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate education score"""
        scores = []
        
        # Primary school (40% weight)
        if self.primary_school_distance_m is not None:
            if self.primary_school_distance_m <= 500:
                primary_score = 100
            elif self.primary_school_distance_m <= 1000:
                primary_score = 80
            elif self.primary_school_distance_m <= 1500:
                primary_score = 60
            else:
                primary_score = 40
            
            # Adjust by rating
            if self.primary_school_rating > 0:
                primary_score = primary_score * (0.7 + 0.3 * (self.primary_school_rating / 5))
            
            scores.append(primary_score * 0.40)
        
        # Secondary school (25% weight)
        if self.secondary_school_distance_m is not None:
            if self.secondary_school_distance_m <= 1000:
                secondary_score = 100
            elif self.secondary_school_distance_m <= 2000:
                secondary_score = 75
            elif self.secondary_school_distance_m <= 3000:
                secondary_score = 50
            else:
                secondary_score = 25
            
            if self.secondary_school_rating > 0:
                secondary_score = secondary_score * (0.7 + 0.3 * (self.secondary_school_rating / 5))
            
            scores.append(secondary_score * 0.25)
        
        # Kindergarten (20% weight)
        if self.kindergarten_distance_m is not None:
            if self.kindergarten_distance_m <= 500:
                kinder_score = 100
            elif self.kindergarten_distance_m <= 1000:
                kinder_score = 75
            elif self.kindergarten_distance_m <= 1500:
                kinder_score = 50
            else:
                kinder_score = 25
            scores.append(kinder_score * 0.20)
        
        # University (15% weight)
        if self.university_distance_m is not None:
            if self.university_distance_m <= 2000:
                uni_score = 100
            elif self.university_distance_m <= 5000:
                uni_score = 70
            else:
                uni_score = 40
            scores.append(uni_score * 0.15)
        
        self.overall = sum(scores) if scores else 50
        return self.overall


@dataclass
class ShoppingScore:
    """Shopping and amenities score"""
    grocery_store_distance_m: Optional[int] = None
    supermarket_distance_m: Optional[int] = None
    shopping_mall_distance_m: Optional[int] = None
    restaurant_count_500m: int = 0
    cafe_count_500m: int = 0
    pharmacy_distance_m: Optional[int] = None
    bank_distance_m: Optional[int] = None
    post_office_distance_m: Optional[int] = None
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate shopping score"""
        scores = []
        
        # Grocery store (25% weight)
        if self.grocery_store_distance_m is not None:
            if self.grocery_store_distance_m <= 300:
                scores.append(100 * 0.25)
            elif self.grocery_store_distance_m <= 600:
                scores.append(80 * 0.25)
            elif self.grocery_store_distance_m <= 1000:
                scores.append(60 * 0.25)
            else:
                scores.append(40 * 0.25)
        
        # Supermarket (20% weight)
        if self.supermarket_distance_m is not None:
            if self.supermarket_distance_m <= 500:
                scores.append(100 * 0.20)
            elif self.supermarket_distance_m <= 1000:
                scores.append(80 * 0.20)
            elif self.supermarket_distance_m <= 1500:
                scores.append(60 * 0.20)
            else:
                scores.append(40 * 0.20)
        
        # Shopping mall (15% weight)
        if self.shopping_mall_distance_m is not None:
            if self.shopping_mall_distance_m <= 1000:
                scores.append(100 * 0.15)
            elif self.shopping_mall_distance_m <= 2000:
                scores.append(75 * 0.15)
            elif self.shopping_mall_distance_m <= 3000:
                scores.append(50 * 0.15)
            else:
                scores.append(25 * 0.15)
        
        # Restaurants (15% weight)
        if self.restaurant_count_500m >= 10:
            scores.append(100 * 0.15)
        elif self.restaurant_count_500m >= 5:
            scores.append(80 * 0.15)
        elif self.restaurant_count_500m >= 2:
            scores.append(60 * 0.15)
        else:
            scores.append(40 * 0.15)
        
        # Cafes (10% weight)
        if self.cafe_count_500m >= 5:
            scores.append(100 * 0.10)
        elif self.cafe_count_500m >= 3:
            scores.append(80 * 0.10)
        elif self.cafe_count_500m >= 1:
            scores.append(60 * 0.10)
        else:
            scores.append(40 * 0.10)
        
        # Pharmacy (10% weight)
        if self.pharmacy_distance_m is not None:
            if self.pharmacy_distance_m <= 500:
                scores.append(100 * 0.10)
            elif self.pharmacy_distance_m <= 1000:
                scores.append(75 * 0.10)
            else:
                scores.append(50 * 0.10)
        
        # Bank (5% weight)
        if self.bank_distance_m is not None:
            if self.bank_distance_m <= 1000:
                scores.append(100 * 0.05)
            else:
                scores.append(60 * 0.05)
        
        self.overall = sum(scores) if scores else 50
        return self.overall


@dataclass
class HealthcareScore:
    """Healthcare facilities score"""
    hospital_distance_m: Optional[int] = None
    hospital_rating: float = 0.0
    clinic_distance_m: Optional[int] = None
    dentist_distance_m: Optional[int] = None
    vet_distance_m: Optional[int] = None
    emergency_room_distance_m: Optional[int] = None
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate healthcare score"""
        scores = []
        
        # Hospital (40% weight)
        if self.hospital_distance_m is not None:
            if self.hospital_distance_m <= 1000:
                hospital_score = 100
            elif self.hospital_distance_m <= 3000:
                hospital_score = 75
            elif self.hospital_distance_m <= 5000:
                hospital_score = 50
            else:
                hospital_score = 25
            
            # Adjust by rating
            if self.hospital_rating > 0:
                hospital_score = hospital_score * (0.7 + 0.3 * (self.hospital_rating / 5))
            
            scores.append(hospital_score * 0.40)
        
        # Clinic (25% weight)
        if self.clinic_distance_m is not None:
            if self.clinic_distance_m <= 500:
                scores.append(100 * 0.25)
            elif self.clinic_distance_m <= 1000:
                scores.append(80 * 0.25)
            elif self.clinic_distance_m <= 2000:
                scores.append(60 * 0.25)
            else:
                scores.append(40 * 0.25)
        
        # Emergency room (20% weight)
        if self.emergency_room_distance_m is not None:
            if self.emergency_room_distance_m <= 2000:
                scores.append(100 * 0.20)
            elif self.emergency_room_distance_m <= 5000:
                scores.append(70 * 0.20)
            else:
                scores.append(40 * 0.20)
        
        # Dentist (10% weight)
        if self.dentist_distance_m is not None:
            if self.dentist_distance_m <= 1000:
                scores.append(100 * 0.10)
            elif self.dentist_distance_m <= 2000:
                scores.append(70 * 0.10)
            else:
                scores.append(40 * 0.10)
        
        # Vet (5% weight)
        if self.vet_distance_m is not None:
            if self.vet_distance_m <= 1000:
                scores.append(100 * 0.05)
            else:
                scores.append(60 * 0.05)
        
        self.overall = sum(scores) if scores else 50
        return self.overall


@dataclass
class SafetyScore:
    """Safety and crime score"""
    crime_rate_index: Optional[float] = None  # 0-100, lower is safer
    violent_crime_rate: Optional[float] = None
    property_crime_rate: Optional[float] = None
    police_station_distance_m: Optional[int] = None
    street_lighting_score: float = 0.0
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate safety score"""
        scores = []
        
        # Crime rate (60% weight) - invert so higher is better
        if self.crime_rate_index is not None:
            crime_score = max(0, 100 - self.crime_rate_index)
            scores.append(crime_score * 0.60)
        
        # Police presence (20% weight)
        if self.police_station_distance_m is not None:
            if self.police_station_distance_m <= 1000:
                scores.append(100 * 0.20)
            elif self.police_station_distance_m <= 2000:
                scores.append(80 * 0.20)
            elif self.police_station_distance_m <= 3000:
                scores.append(60 * 0.20)
            else:
                scores.append(40 * 0.20)
        
        # Street lighting (20% weight)
        scores.append(self.street_lighting_score * 0.20)
        
        self.overall = sum(scores) if scores else 50
        return self.overall


@dataclass
class GreeneryScore:
    """Parks and green spaces score"""
    park_distance_m: Optional[int] = None
    park_area_sqm: float = 0.0
    forest_distance_m: Optional[int] = None
    playground_distance_m: Optional[int] = None
    green_coverage_percent: float = 0.0
    air_quality_index: Optional[float] = None  # Lower is better
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate greenery score"""
        scores = []
        
        # Park distance (35% weight)
        if self.park_distance_m is not None:
            if self.park_distance_m <= 300:
                scores.append(100 * 0.35)
            elif self.park_distance_m <= 600:
                scores.append(85 * 0.35)
            elif self.park_distance_m <= 1000:
                scores.append(70 * 0.35)
            elif self.park_distance_m <= 2000:
                scores.append(50 * 0.35)
            else:
                scores.append(30 * 0.35)
        
        # Green coverage (25% weight)
        scores.append(min(100, self.green_coverage_percent) * 0.25)
        
        # Playground (20% weight)
        if self.playground_distance_m is not None:
            if self.playground_distance_m <= 500:
                scores.append(100 * 0.20)
            elif self.playground_distance_m <= 1000:
                scores.append(75 * 0.20)
            else:
                scores.append(50 * 0.20)
        
        # Forest (10% weight)
        if self.forest_distance_m is not None:
            if self.forest_distance_m <= 2000:
                scores.append(100 * 0.10)
            elif self.forest_distance_m <= 5000:
                scores.append(70 * 0.10)
            else:
                scores.append(40 * 0.10)
        
        # Air quality (10% weight) - invert
        if self.air_quality_index is not None:
            air_score = max(0, 100 - self.air_quality_index)
            scores.append(air_score * 0.10)
        
        self.overall = sum(scores) if scores else 50
        return self.overall


@dataclass
class EntertainmentScore:
    """Entertainment and culture score"""
    cinema_distance_m: Optional[int] = None
    theater_distance_m: Optional[int] = None
    gym_distance_m: Optional[int] = None
    swimming_pool_distance_m: Optional[int] = None
    sports_facilities_count: int = 0
    museum_distance_m: Optional[int] = None
    nightlife_score: float = 0.0
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate entertainment score"""
        scores = []
        
        # Cinema (20% weight)
        if self.cinema_distance_m is not None:
            if self.cinema_distance_m <= 1000:
                scores.append(100 * 0.20)
            elif self.cinema_distance_m <= 2000:
                scores.append(75 * 0.20)
            elif self.cinema_distance_m <= 3000:
                scores.append(50 * 0.20)
            else:
                scores.append(25 * 0.20)
        
        # Gym (20% weight)
        if self.gym_distance_m is not None:
            if self.gym_distance_m <= 500:
                scores.append(100 * 0.20)
            elif self.gym_distance_m <= 1000:
                scores.append(80 * 0.20)
            elif self.gym_distance_m <= 2000:
                scores.append(60 * 0.20)
            else:
                scores.append(40 * 0.20)
        
        # Theater (15% weight)
        if self.theater_distance_m is not None:
            if self.theater_distance_m <= 2000:
                scores.append(100 * 0.15)
            elif self.theater_distance_m <= 5000:
                scores.append(70 * 0.15)
            else:
                scores.append(40 * 0.15)
        
        # Swimming pool (15% weight)
        if self.swimming_pool_distance_m is not None:
            if self.swimming_pool_distance_m <= 1000:
                scores.append(100 * 0.15)
            elif self.swimming_pool_distance_m <= 2000:
                scores.append(70 * 0.15)
            else:
                scores.append(40 * 0.15)
        
        # Sports facilities (15% weight)
        if self.sports_facilities_count >= 3:
            scores.append(100 * 0.15)
        elif self.sports_facilities_count >= 2:
            scores.append(75 * 0.15)
        elif self.sports_facilities_count >= 1:
            scores.append(50 * 0.15)
        else:
            scores.append(25 * 0.15)
        
        # Nightlife (15% weight)
        scores.append(self.nightlife_score * 0.15)
        
        self.overall = sum(scores) if scores else 50
        return self.overall


@dataclass
class InvestmentScore:
    """Investment potential score"""
    price_trend_percent: float = 0.0  # Annual price change
    rental_yield_percent: float = 0.0
    demand_index: float = 50.0  # 0-100
    supply_index: float = 50.0  # 0-100
    infrastructure_development: float = 0.0  # 0-100
    new_construction_count: int = 0
    days_on_market_avg: float = 30.0
    
    overall: float = 0.0
    
    def calculate(self):
        """Calculate investment score"""
        scores = []
        
        # Price trend (25% weight)
        if self.price_trend_percent >= 10:
            trend_score = 100
        elif self.price_trend_percent >= 5:
            trend_score = 80
        elif self.price_trend_percent >= 2:
            trend_score = 60
        elif self.price_trend_percent >= 0:
            trend_score = 40
        else:
            trend_score = 20
        scores.append(trend_score * 0.25)
        
        # Rental yield (25% weight)
        if self.rental_yield_percent >= 8:
            yield_score = 100
        elif self.rental_yield_percent >= 6:
            yield_score = 85
        elif self.rental_yield_percent >= 4:
            yield_score = 70
        elif self.rental_yield_percent >= 2:
            yield_score = 50
        else:
            yield_score = 30
        scores.append(yield_score * 0.25)
        
        # Demand vs Supply (20% weight)
        demand_supply_ratio = self.demand_index / max(1, self.supply_index)
        if demand_supply_ratio >= 1.5:
            ds_score = 100
        elif demand_supply_ratio >= 1.2:
            ds_score = 80
        elif demand_supply_ratio >= 1.0:
            ds_score = 60
        else:
            ds_score = 40
        scores.append(ds_score * 0.20)
        
        # Infrastructure development (15% weight)
        scores.append(self.infrastructure_development * 0.15)
        
        # Market velocity (15% weight)
        if self.days_on_market_avg <= 15:
            velocity_score = 100
        elif self.days_on_market_avg <= 30:
            velocity_score = 80
        elif self.days_on_market_avg <= 60:
            velocity_score = 60
        else:
            velocity_score = 40
        scores.append(velocity_score * 0.15)
        
        self.overall = sum(scores) if scores else 50
        return self.overall


@dataclass
class NeighborhoodScore:
    """Complete neighborhood score"""
    address: str
    city: str
    district: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    transport: TransportScore = field(default_factory=TransportScore)
    education: EducationScore = field(default_factory=EducationScore)
    shopping: ShoppingScore = field(default_factory=ShoppingScore)
    healthcare: HealthcareScore = field(default_factory=HealthcareScore)
    safety: SafetyScore = field(default_factory=HealthScore)
    greenery: GreeneryScore = field(default_factory=GreeneryScore)
    entertainment: EntertainmentScore = field(default_factory=EntertainmentScore)
    investment: InvestmentScore = field(default_factory=InvestmentScore)
    
    overall_score: float = 0.0
    score_level: str = ""
    
    # Category weights for overall score
    CATEGORY_WEIGHTS = {
        'transport': 0.18,
        'education': 0.15,
        'shopping': 0.12,
        'healthcare': 0.12,
        'safety': 0.15,
        'greenery': 0.10,
        'entertainment': 0.08,
        'investment': 0.10,
    }
    
    def calculate_overall(self):
        """Calculate overall neighborhood score"""
        # Calculate individual scores
        scores = {
            'transport': self.transport.calculate(),
            'education': self.education.calculate(),
            'shopping': self.shopping.calculate(),
            'healthcare': self.healthcare.calculate(),
            'safety': self.safety.calculate(),
            'greenery': self.greenery.calculate(),
            'entertainment': self.entertainment.calculate(),
            'investment': self.investment.calculate(),
        }
        
        # Calculate weighted overall
        self.overall_score = sum(
            scores[category] * weight
            for category, weight in self.CATEGORY_WEIGHTS.items()
        )
        
        # Determine score level
        self.score_level = self._get_score_level(self.overall_score)
        
        return self.overall_score
    
    @staticmethod
    def _get_score_level(score: float) -> str:
        """Get score level description"""
        if score >= 90:
            return ScoreLevel.EXCELLENT.value
        elif score >= 80:
            return ScoreLevel.VERY_GOOD.value
        elif score >= 70:
            return ScoreLevel.GOOD.value
        elif score >= 60:
            return ScoreLevel.AVERAGE.value
        elif score >= 50:
            return ScoreLevel.BELOW_AVERAGE.value
        else:
            return ScoreLevel.POOR.value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'location': {
                'address': self.address,
                'city': self.city,
                'district': self.district,
                'coordinates': {
                    'lat': self.latitude,
                    'lng': self.longitude,
                } if self.latitude and self.longitude else None,
            },
            'overall': {
                'score': round(self.overall_score, 1),
                'level': self.score_level,
            },
            'categories': {
                'transport': {
                    'score': round(self.transport.overall, 1),
                    'details': {
                        'metro_score': round(self.transport.metro_score, 1),
                        'bus_score': round(self.transport.bus_score, 1),
                        'walkability': round(self.transport.walkability_score, 1),
                    }
                },
                'education': {
                    'score': round(self.education.overall, 1),
                },
                'shopping': {
                    'score': round(self.shopping.overall, 1),
                },
                'healthcare': {
                    'score': round(self.healthcare.overall, 1),
                },
                'safety': {
                    'score': round(self.safety.overall, 1),
                },
                'greenery': {
                    'score': round(self.greenery.overall, 1),
                },
                'entertainment': {
                    'score': round(self.entertainment.overall, 1),
                },
                'investment': {
                    'score': round(self.investment.overall, 1),
                    'details': {
                        'price_trend': self.investment.price_trend_percent,
                        'rental_yield': self.investment.rental_yield_percent,
                    }
                },
            },
            'generated_at': datetime.utcnow().isoformat(),
        }


class NeighborhoodScoringService:
    """
    Professional neighborhood scoring service.
    
    Features:
    - Multi-factor location analysis
    - Investment potential scoring
    - Lifestyle quality assessment
    - Comparable neighborhood comparison
    """
    
    def __init__(self):
        pass
    
    async def score_neighborhood(
        self,
        address: str,
        city: str,
        district: str,
        **kwargs
    ) -> NeighborhoodScore:
        """
        Score a neighborhood based on available data.
        
        In production, this would integrate with:
        - Google Places API
        - OpenStreetMap
        - Crime statistics APIs
        - Air quality APIs
        - Real estate market data
        """
        score = NeighborhoodScore(
            address=address,
            city=city,
            district=district,
            **kwargs
        )
        
        # Calculate overall score
        score.calculate_overall()
        
        return score
    
    async def compare_neighborhoods(
        self,
        neighborhoods: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Compare multiple neighborhoods"""
        scores = []
        
        for nb_data in neighborhoods:
            score = await self.score_neighborhood(**nb_data)
            scores.append(score)
        
        # Sort by overall score
        scores.sort(key=lambda x: x.overall_score, reverse=True)
        
        return {
            'comparison': [
                {
                    'location': f"{s.city}, {s.district}",
                    'overall_score': round(s.overall_score, 1),
                    'level': s.score_level,
                    'best_categories': self._get_best_categories(s),
                }
                for s in scores
            ],
            'ranking': [
                {
                    'rank': i + 1,
                    'location': f"{s.city}, {s.district}",
                    'score': round(s.overall_score, 1),
                }
                for i, s in enumerate(scores)
            ],
        }
    
    def _get_best_categories(self, score: NeighborhoodScore) -> List[str]:
        """Get top 3 categories for a neighborhood"""
        categories = [
            ('transport', score.transport.overall),
            ('education', score.education.overall),
            ('shopping', score.shopping.overall),
            ('healthcare', score.healthcare.overall),
            ('safety', score.safety.overall),
            ('greenery', score.greenery.overall),
            ('entertainment', score.entertainment.overall),
            ('investment', score.investment.overall),
        ]
        
        categories.sort(key=lambda x: x[1], reverse=True)
        return [cat[0] for cat in categories[:3]]
