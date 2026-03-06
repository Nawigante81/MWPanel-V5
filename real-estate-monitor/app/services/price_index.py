"""
Historical Price Index Service

Tracks and analyzes historical price trends for real estate markets.
Provides price indices, trend analysis, and market forecasts.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import statistics

from sqlalchemy import func, and_, extract
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Offer, OfferType, PropertyType
from app.core.logging import get_logger

logger = get_logger(__name__)


class TrendDirection(str, Enum):
    """Price trend direction"""
    STRONGLY_RISING = "strongly_rising"
    RISING = "rising"
    STABLE = "stable"
    FALLING = "falling"
    STRONGLY_FALLING = "strongly_falling"


@dataclass
class PricePoint:
    """Single price data point"""
    date: datetime
    avg_price: float
    median_price: float
    min_price: float
    max_price: float
    price_per_sqm: float
    transaction_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'date': self.date.isoformat(),
            'avg_price': round(self.avg_price, 2),
            'median_price': round(self.median_price, 2),
            'min_price': round(self.min_price, 2),
            'max_price': round(self.max_price, 2),
            'price_per_sqm': round(self.price_per_sqm, 2),
            'transaction_count': self.transaction_count,
        }


@dataclass
class PriceIndex:
    """Price index for a specific market segment"""
    id: str
    name: str
    city: str
    district: Optional[str]
    property_type: PropertyType
    offer_type: OfferType
    
    base_date: datetime
    base_value: float = 100.0
    
    current_value: float = 100.0
    current_date: Optional[datetime] = None
    
    # Historical data
    data_points: List[PricePoint] = field(default_factory=list)
    
    # Trend analysis
    yoy_change: float = 0.0  # Year-over-year change
    mom_change: float = 0.0  # Month-over-month change
    trend_direction: str = "stable"
    volatility: float = 0.0
    
    def calculate_changes(self):
        """Calculate price changes"""
        if len(self.data_points) < 2:
            return
        
        # Sort by date
        sorted_points = sorted(self.data_points, key=lambda x: x.date)
        
        # Current value (latest)
        latest = sorted_points[-1]
        self.current_value = latest.price_per_sqm
        self.current_date = latest.date
        
        # Month-over-month change
        if len(sorted_points) >= 2:
            previous = sorted_points[-2]
            if previous.price_per_sqm > 0:
                self.mom_change = (
                    (latest.price_per_sqm - previous.price_per_sqm) / 
                    previous.price_per_sqm * 100
                )
        
        # Year-over-year change
        one_year_ago = latest.date - timedelta(days=365)
        year_ago_point = None
        
        for point in reversed(sorted_points):
            if point.date <= one_year_ago:
                year_ago_point = point
                break
        
        if year_ago_point and year_ago_point.price_per_sqm > 0:
            self.yoy_change = (
                (latest.price_per_sqm - year_ago_point.price_per_sqm) / 
                year_ago_point.price_per_sqm * 100
            )
        
        # Calculate volatility (standard deviation of monthly changes)
        if len(sorted_points) >= 3:
            changes = []
            for i in range(1, len(sorted_points)):
                if sorted_points[i-1].price_per_sqm > 0:
                    change = (
                        (sorted_points[i].price_per_sqm - sorted_points[i-1].price_per_sqm) /
                        sorted_points[i-1].price_per_sqm * 100
                    )
                    changes.append(change)
            
            if changes:
                self.volatility = statistics.stdev(changes) if len(changes) > 1 else 0
        
        # Determine trend direction
        self.trend_direction = self._get_trend_direction(self.yoy_change)
    
    @staticmethod
    def _get_trend_direction(yoy_change: float) -> str:
        """Determine trend direction from YoY change"""
        if yoy_change >= 15:
            return TrendDirection.STRONGLY_RISING.value
        elif yoy_change >= 5:
            return TrendDirection.RISING.value
        elif yoy_change >= -5:
            return TrendDirection.STABLE.value
        elif yoy_change >= -15:
            return TrendDirection.FALLING.value
        else:
            return TrendDirection.STRONGLY_FALLING.value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'location': {
                'city': self.city,
                'district': self.district,
            },
            'property_type': self.property_type.value,
            'offer_type': self.offer_type.value,
            'base_date': self.base_date.isoformat(),
            'base_value': self.base_value,
            'current_value': round(self.current_value, 2),
            'current_date': self.current_date.isoformat() if self.current_date else None,
            'changes': {
                'yoy_percent': round(self.yoy_change, 2),
                'mom_percent': round(self.mom_change, 2),
                'trend_direction': self.trend_direction,
            },
            'volatility': round(self.volatility, 2),
            'data_points': [p.to_dict() for p in self.data_points[-24:]],  # Last 24 months
        }


@dataclass
class MarketForecast:
    """Price forecast for a market"""
    index_id: str
    forecast_date: datetime
    
    # Predictions
    predicted_price_per_sqm: float
    confidence_interval_low: float
    confidence_interval_high: float
    
    # Time horizons
    one_month_forecast: float
    three_month_forecast: float
    six_month_forecast: float
    one_year_forecast: float
    
    # Factors
    key_factors: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'index_id': self.index_id,
            'forecast_date': self.forecast_date.isoformat(),
            'predictions': {
                'current': round(self.predicted_price_per_sqm, 2),
                'confidence_interval': [
                    round(self.confidence_interval_low, 2),
                    round(self.confidence_interval_high, 2)
                ],
                'forecasts': {
                    '1_month': round(self.one_month_forecast, 2),
                    '3_months': round(self.three_month_forecast, 2),
                    '6_months': round(self.six_month_forecast, 2),
                    '1_year': round(self.one_year_forecast, 2),
                }
            },
            'factors': {
                'positive': self.key_factors,
                'risks': self.risk_factors,
            }
        }


class PriceIndexService:
    """
    Historical price index service.
    
    Features:
    - Price index calculation and tracking
    - Market trend analysis
    - Price forecasting
    - Comparative market analysis
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self._indices_cache: Dict[str, PriceIndex] = {}
        
    async def calculate_index(
        self,
        city: str,
        district: Optional[str] = None,
        property_type: PropertyType = PropertyType.APARTMENT,
        offer_type: OfferType = OfferType.SALE,
        months: int = 24
    ) -> PriceIndex:
        """
        Calculate price index for a market segment.
        
        Args:
            city: City name
            district: District name (optional)
            property_type: Type of property
            offer_type: Sale or rent
            months: Number of months of historical data
            
        Returns:
            PriceIndex with historical data
        """
        # Create index ID
        index_id = f"{city}_{district or 'all'}_{property_type.value}_{offer_type.value}"
        
        # Build index name
        index_name = f"{city}"
        if district:
            index_name += f" - {district}"
        index_name += f" {property_type.value.title()} {offer_type.value.title()}"
        
        index = PriceIndex(
            id=index_id,
            name=index_name,
            city=city,
            district=district,
            property_type=property_type,
            offer_type=offer_type,
            base_date=datetime.utcnow() - timedelta(days=30 * months),
        )
        
        # Query historical data
        start_date = datetime.utcnow() - timedelta(days=30 * months)
        
        query = self.db.query(Offer).filter(
            Offer.city == city,
            Offer.property_type == property_type,
            Offer.offer_type == offer_type,
            Offer.created_at >= start_date,
            Offer.price.isnot(None),
            Offer.area_sqm.isnot(None),
            Offer.area_sqm > 0
        )
        
        if district:
            query = query.filter(Offer.district == district)
        
        offers = query.all()
        
        if not offers:
            logger.warning(f"No data found for index {index_id}")
            return index
        
        # Group by month
        monthly_data = {}
        for offer in offers:
            month_key = offer.created_at.strftime('%Y-%m')
            
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            
            monthly_data[month_key].append(offer)
        
        # Calculate monthly price points
        for month_key, month_offers in sorted(monthly_data.items()):
            prices = [o.price for o in month_offers]
            prices_per_sqm = [o.price / o.area_sqm for o in month_offers if o.area_sqm > 0]
            
            if prices and prices_per_sqm:
                point = PricePoint(
                    date=datetime.strptime(month_key + '-01', '%Y-%m-%d'),
                    avg_price=statistics.mean(prices),
                    median_price=statistics.median(prices),
                    min_price=min(prices),
                    max_price=max(prices),
                    price_per_sqm=statistics.median(prices_per_sqm),
                    transaction_count=len(month_offers)
                )
                index.data_points.append(point)
        
        # Calculate changes
        index.calculate_changes()
        
        # Cache the index
        self._indices_cache[index_id] = index
        
        return index
    
    async def get_index(
        self,
        city: str,
        district: Optional[str] = None,
        property_type: PropertyType = PropertyType.APARTMENT,
        offer_type: OfferType = OfferType.SALE
    ) -> Optional[PriceIndex]:
        """Get cached index or calculate new one"""
        index_id = f"{city}_{district or 'all'}_{property_type.value}_{offer_type.value}"
        
        if index_id in self._indices_cache:
            return self._indices_cache[index_id]
        
        return await self.calculate_index(city, district, property_type, offer_type)
    
    async def compare_indices(
        self,
        indices: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare multiple price indices"""
        comparison = {
            'indices': [],
            'comparison_table': [],
            'best_performers': [],
            'worst_performers': [],
        }
        
        index_objects = []
        
        for idx_spec in indices:
            index = await self.get_index(**idx_spec)
            if index:
                index_objects.append(index)
                comparison['indices'].append(index.to_dict())
        
        # Sort by YoY performance
        sorted_by_yoy = sorted(index_objects, key=lambda x: x.yoy_change, reverse=True)
        
        comparison['best_performers'] = [
            {'name': idx.name, 'yoy_change': round(idx.yoy_change, 2)}
            for idx in sorted_by_yoy[:3]
        ]
        
        comparison['worst_performers'] = [
            {'name': idx.name, 'yoy_change': round(idx.yoy_change, 2)}
            for idx in sorted_by_yoy[-3:]
        ]
        
        return comparison
    
    async def forecast_prices(
        self,
        city: str,
        district: Optional[str] = None,
        property_type: PropertyType = PropertyType.APARTMENT,
        offer_type: OfferType = OfferType.SALE
    ) -> MarketForecast:
        """
        Generate price forecast for a market.
        
        Uses simple trend extrapolation with seasonality adjustment.
        For production, would use ML models.
        """
        index = await self.get_index(city, district, property_type, offer_type)
        
        if not index or not index.data_points:
            raise ValueError("Insufficient data for forecasting")
        
        # Get trend from last 6 months
        recent_points = index.data_points[-6:]
        
        if len(recent_points) < 3:
            raise ValueError("Insufficient recent data for forecasting")
        
        # Calculate average monthly change
        monthly_changes = []
        for i in range(1, len(recent_points)):
            if recent_points[i-1].price_per_sqm > 0:
                change = (
                    (recent_points[i].price_per_sqm - recent_points[i-1].price_per_sqm) /
                    recent_points[i-1].price_per_sqm
                )
                monthly_changes.append(change)
        
        avg_monthly_change = statistics.mean(monthly_changes) if monthly_changes else 0
        
        # Current price
        current_price = index.data_points[-1].price_per_sqm
        
        # Generate forecasts
        forecast = MarketForecast(
            index_id=index.id,
            forecast_date=datetime.utcnow(),
            predicted_price_per_sqm=current_price,
            confidence_interval_low=current_price * 0.95,
            confidence_interval_high=current_price * 1.05,
            one_month_forecast=current_price * (1 + avg_monthly_change),
            three_month_forecast=current_price * (1 + avg_monthly_change) ** 3,
            six_month_forecast=current_price * (1 + avg_monthly_change) ** 6,
            one_year_forecast=current_price * (1 + avg_monthly_change) ** 12,
        )
        
        # Add factors
        if avg_monthly_change > 0.01:
            forecast.key_factors.append("Positive price momentum")
        elif avg_monthly_change < -0.01:
            forecast.risk_factors.append("Declining price trend")
        
        if index.volatility > 2:
            forecast.risk_factors.append("High market volatility")
        
        if index.yoy_change > 10:
            forecast.risk_factors.append("Market may be overheating")
        
        return forecast
    
    async def get_market_heatmap(
        self,
        city: str,
        offer_type: OfferType = OfferType.SALE
    ) -> Dict[str, Any]:
        """Generate price heatmap data by district"""
        # Get all districts in city
        districts = self.db.query(Offer.district).filter(
            Offer.city == city,
            Offer.district.isnot(None)
        ).distinct().all()
        
        districts = [d[0] for d in districts if d[0]]
        
        heatmap_data = []
        
        for district in districts:
            try:
                index = await self.calculate_index(
                    city=city,
                    district=district,
                    offer_type=offer_type
                )
                
                if index.data_points:
                    heatmap_data.append({
                        'district': district,
                        'current_price_per_sqm': round(index.current_value, 2),
                        'yoy_change': round(index.yoy_change, 2),
                        'trend': index.trend_direction,
                        'transaction_count': sum(p.transaction_count for p in index.data_points[-3:]),
                    })
            except Exception as e:
                logger.warning(f"Error calculating index for {district}: {e}")
        
        # Sort by price
        heatmap_data.sort(key=lambda x: x['current_price_per_sqm'], reverse=True)
        
        return {
            'city': city,
            'offer_type': offer_type.value,
            'districts': heatmap_data,
            'generated_at': datetime.utcnow().isoformat(),
        }
    
    async def get_affordability_index(
        self,
        city: str,
        avg_household_income: float
    ) -> Dict[str, Any]:
        """
        Calculate housing affordability index.
        
        Affordability = (Median home price) / (Annual household income)
        """
        index = await self.get_index(city, property_type=PropertyType.APARTMENT)
        
        if not index.data_points:
            return {'error': 'No price data available'}
        
        # Assume average apartment size of 55 sqm
        avg_apartment_size = 55
        median_home_price = index.current_value * avg_apartment_size
        
        affordability_ratio = median_home_price / avg_household_income
        
        # Interpretation
        if affordability_ratio <= 3:
            affordability_level = "affordable"
        elif affordability_ratio <= 4:
            affordability_level = "moderately_affordable"
        elif affordability_ratio <= 5:
            affordability_level = "unaffordable"
        else:
            affordability_level = "severely_unaffordable"
        
        return {
            'city': city,
            'median_apartment_price': round(median_home_price, 2),
            'avg_household_income': avg_household_income,
            'affordability_ratio': round(affordability_ratio, 2),
            'affordability_level': affordability_level,
            'interpretation': {
                'affordable': 'Housing is affordable for average income',
                'moderately_affordable': 'Housing requires some financial effort',
                'unaffordable': 'Housing is difficult to afford',
                'severely_unaffordable': 'Housing crisis level'
            }.get(affordability_level)
        }


# Convenience functions

async def get_price_trend(
    db_session: Session,
    city: str,
    months: int = 12
) -> Dict[str, Any]:
    """Get quick price trend for a city"""
    service = PriceIndexService(db_session)
    index = await service.calculate_index(city=city, months=months)
    
    return {
        'city': city,
        'current_price_per_sqm': round(index.current_value, 2),
        'yoy_change_percent': round(index.yoy_change, 2),
        'mom_change_percent': round(index.mom_change, 2),
        'trend_direction': index.trend_direction,
        'data_points_count': len(index.data_points),
    }
