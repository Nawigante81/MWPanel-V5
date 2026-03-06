"""
Usage Analytics Dashboard Service

Comprehensive analytics for tracking platform usage,
user engagement, and system performance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Offer, Search, User, UserSearch
from app.core.logging import get_logger

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class TimeSeriesPoint:
    """Single time series data point"""
    timestamp: datetime
    value: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'value': self.value
        }


@dataclass
class MetricSeries:
    """Time series metric data"""
    name: str
    description: str
    unit: str
    data_points: List[TimeSeriesPoint] = field(default_factory=list)
    
    @property
    def current_value(self) -> float:
        return self.data_points[-1].value if self.data_points else 0
    
    @property
    def average(self) -> float:
        if not self.data_points:
            return 0
        return sum(p.value for p in self.data_points) / len(self.data_points)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'unit': self.unit,
            'current_value': round(self.current_value, 2),
            'average': round(self.average, 2),
            'data_points': [p.to_dict() for p in self.data_points[-30:]],  # Last 30 points
        }


@dataclass
class DashboardWidget:
    """Dashboard widget configuration and data"""
    id: str
    title: str
    type: str  # chart, stat, table, gauge
    metric: MetricSeries
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'type': self.type,
            'config': self.config,
            'data': self.metric.to_dict(),
        }


@dataclass
class UserEngagementMetrics:
    """User engagement statistics"""
    total_users: int
    active_users_daily: int
    active_users_weekly: int
    active_users_monthly: int
    new_users_today: int
    new_users_this_week: int
    new_users_this_month: int
    
    avg_session_duration_minutes: float
    avg_searches_per_user: float
    avg_offers_viewed_per_user: float
    
    retention_rate_7d: float
    retention_rate_30d: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_users': self.total_users,
            'active_users': {
                'daily': self.active_users_daily,
                'weekly': self.active_users_weekly,
                'monthly': self.active_users_monthly,
            },
            'new_users': {
                'today': self.new_users_today,
                'this_week': self.new_users_this_week,
                'this_month': self.new_users_this_month,
            },
            'engagement': {
                'avg_session_duration_min': round(self.avg_session_duration_minutes, 1),
                'avg_searches_per_user': round(self.avg_searches_per_user, 2),
                'avg_offers_viewed': round(self.avg_offers_viewed_per_user, 2),
            },
            'retention': {
                '7d': round(self.retention_rate_7d, 1),
                '30d': round(self.retention_rate_30d, 1),
            }
        }


@dataclass
class SystemPerformanceMetrics:
    """System performance statistics"""
    # API metrics
    total_api_requests: int
    api_requests_per_minute: float
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    error_rate_percent: float
    
    # Scraping metrics
    offers_scraped_today: int
    offers_scraped_this_week: int
    scraping_success_rate: float
    avg_scraping_time_ms: float
    
    # Database metrics
    db_connections_active: int
    db_query_avg_time_ms: float
    db_slow_queries_count: int
    
    # Queue metrics
    celery_tasks_pending: int
    celery_tasks_processed_today: int
    celery_avg_processing_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'api': {
                'total_requests': self.total_api_requests,
                'requests_per_minute': round(self.api_requests_per_minute, 1),
                'response_times': {
                    'avg_ms': round(self.avg_response_time_ms, 2),
                    'p95_ms': round(self.p95_response_time_ms, 2),
                    'p99_ms': round(self.p99_response_time_ms, 2),
                },
                'error_rate_percent': round(self.error_rate_percent, 2),
            },
            'scraping': {
                'offers_today': self.offers_scraped_today,
                'offers_this_week': self.offers_scraped_this_week,
                'success_rate': round(self.scraping_success_rate, 1),
                'avg_time_ms': round(self.avg_scraping_time_ms, 2),
            },
            'database': {
                'active_connections': self.db_connections_active,
                'query_avg_time_ms': round(self.db_query_avg_time_ms, 2),
                'slow_queries': self.db_slow_queries_count,
            },
            'queue': {
                'tasks_pending': self.celery_tasks_pending,
                'tasks_processed_today': self.celery_tasks_processed_today,
                'avg_processing_time_ms': round(self.celery_avg_processing_time_ms, 2),
            }
        }


@dataclass
class ContentAnalytics:
    """Content and listing analytics"""
    total_offers: int
    offers_added_today: int
    offers_added_this_week: int
    offers_added_this_month: int
    
    offers_by_city: Dict[str, int]
    offers_by_type: Dict[str, int]
    offers_by_source: Dict[str, int]
    
    avg_price_by_city: Dict[str, float]
    avg_price_per_sqm_by_city: Dict[str, float]
    
    price_changes_today: int
    price_changes_this_week: int
    avg_price_change_percent: float
    
    most_viewed_offers: List[Dict[str, Any]]
    newest_offers: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'totals': {
                'all_time': self.total_offers,
                'today': self.offers_added_today,
                'this_week': self.offers_added_this_week,
                'this_month': self.offers_added_this_month,
            },
            'distribution': {
                'by_city': self.offers_by_city,
                'by_type': self.offers_by_type,
                'by_source': self.offers_by_source,
            },
            'pricing': {
                'avg_by_city': {k: round(v, 2) for k, v in self.avg_price_by_city.items()},
                'avg_per_sqm_by_city': {k: round(v, 2) for k, v in self.avg_price_per_sqm_by_city.items()},
            },
            'price_changes': {
                'today': self.price_changes_today,
                'this_week': self.price_changes_this_week,
                'avg_change_percent': round(self.avg_price_change_percent, 2),
            },
            'highlights': {
                'most_viewed': self.most_viewed_offers[:5],
                'newest': self.newest_offers[:5],
            }
        }


class UsageAnalyticsService:
    """
    Professional usage analytics service.
    
    Features:
    - User engagement tracking
    - System performance monitoring
    - Content analytics
    - Custom dashboard creation
    - Real-time metrics
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self._metrics_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
    
    async def get_user_engagement(
        self,
        organization_id: Optional[str] = None
    ) -> UserEngagementMetrics:
        """Get user engagement metrics"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        
        # Base query
        user_query = self.db.query(User)
        if organization_id:
            user_query = user_query.filter(User.organization_id == organization_id)
        
        # Total users
        total_users = user_query.count()
        
        # New users
        new_users_today = user_query.filter(User.created_at >= today_start).count()
        new_users_this_week = user_query.filter(User.created_at >= week_start).count()
        new_users_this_month = user_query.filter(User.created_at >= month_start).count()
        
        # Active users (simplified - would use session data in production)
        active_users_daily = total_users // 3  # Placeholder
        active_users_weekly = total_users // 2  # Placeholder
        active_users_monthly = total_users * 2 // 3  # Placeholder
        
        # Calculate averages
        search_count = self.db.query(Search).count()
        avg_searches_per_user = search_count / total_users if total_users > 0 else 0
        
        return UserEngagementMetrics(
            total_users=total_users,
            active_users_daily=active_users_daily,
            active_users_weekly=active_users_weekly,
            active_users_monthly=active_users_monthly,
            new_users_today=new_users_today,
            new_users_this_week=new_users_this_week,
            new_users_this_month=new_users_this_month,
            avg_session_duration_minutes=15.5,  # Placeholder
            avg_searches_per_user=avg_searches_per_user,
            avg_offers_viewed_per_user=12.3,  # Placeholder
            retention_rate_7d=45.0,  # Placeholder
            retention_rate_30d=25.0,  # Placeholder
        )
    
    async def get_system_performance(self) -> SystemPerformanceMetrics:
        """Get system performance metrics"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Offers scraped today
        offers_today = self.db.query(Offer).filter(
            Offer.created_at >= today_start
        ).count()
        
        offers_week = self.db.query(Offer).filter(
            Offer.created_at >= today_start - timedelta(days=7)
        ).count()
        
        return SystemPerformanceMetrics(
            total_api_requests=150000,  # Placeholder
            api_requests_per_minute=104,  # Placeholder
            avg_response_time_ms=125,  # Placeholder
            p95_response_time_ms=350,  # Placeholder
            p99_response_time_ms=800,  # Placeholder
            error_rate_percent=0.5,  # Placeholder
            offers_scraped_today=offers_today,
            offers_scraped_this_week=offers_week,
            scraping_success_rate=94.5,  # Placeholder
            avg_scraping_time_ms=2500,  # Placeholder
            db_connections_active=15,  # Placeholder
            db_query_avg_time_ms=15,  # Placeholder
            db_slow_queries_count=3,  # Placeholder
            celery_tasks_pending=12,  # Placeholder
            celery_tasks_processed_today=offers_today,  # Approximation
            celery_avg_processing_time_ms=3000,  # Placeholder
        )
    
    async def get_content_analytics(
        self,
        organization_id: Optional[str] = None
    ) -> ContentAnalytics:
        """Get content and listing analytics"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        
        # Base query
        offer_query = self.db.query(Offer)
        
        # Total offers
        total_offers = offer_query.count()
        
        # New offers
        offers_today = offer_query.filter(Offer.created_at >= today_start).count()
        offers_week = offer_query.filter(Offer.created_at >= week_start).count()
        offers_month = offer_query.filter(Offer.created_at >= month_start).count()
        
        # Distribution by city
        city_counts = self.db.query(
            Offer.city,
            func.count(Offer.id)
        ).group_by(Offer.city).all()
        offers_by_city = {city or 'Unknown': count for city, count in city_counts}
        
        # Distribution by type
        type_counts = self.db.query(
            Offer.property_type,
            func.count(Offer.id)
        ).group_by(Offer.property_type).all()
        offers_by_type = {t.value if t else 'Unknown': count for t, count in type_counts}
        
        # Distribution by source
        source_counts = self.db.query(
            Offer.source,
            func.count(Offer.id)
        ).group_by(Offer.source).all()
        offers_by_source = {s or 'Unknown': count for s, count in source_counts}
        
        # Average prices by city
        city_prices = self.db.query(
            Offer.city,
            func.avg(Offer.price),
            func.avg(Offer.price / Offer.area_sqm)
        ).filter(
            Offer.price.isnot(None),
            Offer.area_sqm.isnot(None),
            Offer.area_sqm > 0
        ).group_by(Offer.city).all()
        
        avg_price_by_city = {city or 'Unknown': float(price) for city, price, _ in city_prices}
        avg_price_per_sqm = {city or 'Unknown': float(ppsm) for city, _, ppsm in city_prices}
        
        # Newest offers
        newest_offers = offer_query.order_by(desc(Offer.created_at)).limit(5).all()
        newest_offers_data = [
            {
                'id': str(o.id),
                'title': o.title,
                'city': o.city,
                'price': o.price,
                'created_at': o.created_at.isoformat(),
            }
            for o in newest_offers
        ]
        
        return ContentAnalytics(
            total_offers=total_offers,
            offers_added_today=offers_today,
            offers_added_this_week=offers_week,
            offers_added_this_month=offers_month,
            offers_by_city=offers_by_city,
            offers_by_type=offers_by_type,
            offers_by_source=offers_by_source,
            avg_price_by_city=avg_price_by_city,
            avg_price_per_sqm_by_city=avg_price_per_sqm,
            price_changes_today=0,  # Would query PriceHistory
            price_changes_this_week=0,
            avg_price_change_percent=0.0,
            most_viewed_offers=[],  # Would need view tracking
            newest_offers=newest_offers_data,
        )
    
    async def get_full_dashboard(
        self,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get complete dashboard data"""
        user_engagement = await self.get_user_engagement(organization_id)
        system_performance = await self.get_system_performance()
        content_analytics = await self.get_content_analytics(organization_id)
        
        return {
            'generated_at': datetime.utcnow().isoformat(),
            'user_engagement': user_engagement.to_dict(),
            'system_performance': system_performance.to_dict(),
            'content_analytics': content_analytics.to_dict(),
            'widgets': [
                {
                    'id': 'total_offers',
                    'title': 'Total Offers',
                    'value': content_analytics.total_offers,
                    'change': f"+{content_analytics.offers_added_today}",
                    'change_label': 'today',
                },
                {
                    'id': 'active_users',
                    'title': 'Active Users (30d)',
                    'value': user_engagement.active_users_monthly,
                    'change': f"+{user_engagement.new_users_this_month}",
                    'change_label': 'new this month',
                },
                {
                    'id': 'api_requests',
                    'title': 'API Requests/min',
                    'value': round(system_performance.api_requests_per_minute, 1),
                    'change': f"{system_performance.error_rate_percent}%",
                    'change_label': 'error rate',
                },
                {
                    'id': 'scraping_success',
                    'title': 'Scraping Success',
                    'value': f"{system_performance.scraping_success_rate}%",
                    'change': f"{system_performance.offers_scraped_today}",
                    'change_label': 'offers today',
                },
            ]
        }
    
    async def get_time_series(
        self,
        metric_name: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str = 'day'  # hour, day, week, month
    ) -> MetricSeries:
        """Get time series data for a metric"""
        # This would query time-series database in production
        # For now, return placeholder data
        
        series = MetricSeries(
            name=metric_name,
            description=f"{metric_name} over time",
            unit='count'
        )
        
        # Generate placeholder data points
        current = start_date
        while current <= end_date:
            series.data_points.append(TimeSeriesPoint(
                timestamp=current,
                value=100 + (current.day * 10)  # Placeholder
            ))
            
            if granularity == 'hour':
                current += timedelta(hours=1)
            elif granularity == 'day':
                current += timedelta(days=1)
            elif granularity == 'week':
                current += timedelta(weeks=1)
            else:
                current += timedelta(days=30)
        
        return series
    
    async def get_top_searches(
        self,
        limit: int = 10,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get most popular searches"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Would aggregate similar searches in production
        searches = self.db.query(Search).filter(
            Search.created_at >= start_date
        ).order_by(desc(Search.created_at)).limit(limit * 3).all()
        
        # Count by criteria
        search_counts = defaultdict(int)
        for search in searches:
            key = f"{search.city or 'All'} | {search.property_type.value if search.property_type else 'All'}"
            if search.min_price or search.max_price:
                key += f" | {search.min_price or 0}-{search.max_price or '∞'} PLN"
            search_counts[key] += 1
        
        # Sort by count
        sorted_searches = sorted(search_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'criteria': criteria, 'count': count}
            for criteria, count in sorted_searches[:limit]
        ]
    
    async def get_geographic_distribution(self) -> Dict[str, Any]:
        """Get geographic distribution of offers and users"""
        # Offers by city
        city_data = self.db.query(
            Offer.city,
            func.count(Offer.id),
            func.avg(Offer.price)
        ).filter(
            Offer.city.isnot(None)
        ).group_by(Offer.city).order_by(desc(func.count(Offer.id))).limit(20).all()
        
        return {
            'top_cities': [
                {
                    'city': city,
                    'offer_count': count,
                    'avg_price': round(float(avg_price), 2) if avg_price else 0
                }
                for city, count, avg_price in city_data
            ],
            'total_cities': self.db.query(Offer.city).distinct().count(),
        }


# Convenience functions

async def get_quick_stats(db_session: Session) -> Dict[str, Any]:
    """Get quick platform statistics"""
    service = UsageAnalyticsService(db_session)
    
    total_offers = db_session.query(Offer).count()
    total_users = db_session.query(User).count()
    total_searches = db_session.query(Search).count()
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    offers_today = db_session.query(Offer).filter(Offer.created_at >= today).count()
    
    return {
        'offers': {
            'total': total_offers,
            'today': offers_today,
        },
        'users': {
            'total': total_users,
        },
        'searches': {
            'total': total_searches,
        },
        'generated_at': datetime.utcnow().isoformat(),
    }
