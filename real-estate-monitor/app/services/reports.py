"""
Weekly and monthly reporting service.
Generates summary reports for users.
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import Offer, PriceHistory, Source
from app.services.notifications import get_notification_manager

logger = get_logger("reports")


class ReportGenerator:
    """Generate weekly and monthly reports."""
    
    async def generate_weekly_report(
        self,
        session: AsyncSession,
        user_id: str,
        week_start: Optional[datetime] = None
    ) -> dict:
        """
        Generate weekly summary report.
        
        Returns:
            Report data dict
        """
        if week_start is None:
            # Last Monday
            today = datetime.utcnow().date()
            week_start = datetime.combine(
                today - timedelta(days=today.weekday()),
                datetime.min.time()
            )
        
        week_end = week_start + timedelta(days=7)
        
        # Get new offers this week
        new_offers = await session.execute(
            select(Offer)
            .where(Offer.first_seen >= week_start)
            .where(Offer.first_seen < week_end)
            .order_by(desc(Offer.first_seen))
        )
        new_offers = new_offers.scalars().all()
        
        # Get price drops this week
        price_drops = await session.execute(
            select(PriceHistory)
            .where(PriceHistory.recorded_at >= week_start)
            .where(PriceHistory.recorded_at < week_end)
            .where(PriceHistory.price_change_percent < 0)
        )
        price_drops = price_drops.scalars().all()
        
        # Calculate statistics
        avg_price = await session.scalar(
            select(func.avg(Offer.price))
            .where(Offer.first_seen >= week_start)
            .where(Offer.first_seen < week_end)
        )
        
        # Top cities
        city_counts = await session.execute(
            select(Offer.city, func.count(Offer.id))
            .where(Offer.first_seen >= week_start)
            .where(Offer.city.isnot(None))
            .group_by(Offer.city)
            .order_by(desc(func.count(Offer.id)))
            .limit(5)
        )
        top_cities = {city: count for city, count in city_counts.all()}
        
        # Build report
        report = {
            "period": {
                "start": week_start.isoformat(),
                "end": week_end.isoformat(),
            },
            "summary": {
                "total_new_offers": len(new_offers),
                "total_price_drops": len(price_drops),
                "avg_price": round(float(avg_price), 2) if avg_price else None,
            },
            "top_cities": top_cities,
            "new_offers": [
                {
                    "id": str(o.id),
                    "title": o.title,
                    "price": float(o.price) if o.price else None,
                    "city": o.city,
                    "url": o.url,
                }
                for o in new_offers[:10]  # Top 10
            ],
            "price_drops": [
                {
                    "offer_id": str(p.offer_id),
                    "price": float(p.price),
                    "change_percent": p.price_change_percent,
                }
                for p in price_drops[:5]  # Top 5
            ],
        }
        
        return report
    
    async def generate_monthly_report(
        self,
        session: AsyncSession,
        user_id: str,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> dict:
        """Generate monthly summary report."""
        if year is None or month is None:
            today = datetime.utcnow()
            year = today.year
            month = today.month
        
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)
        
        # Similar to weekly but for month
        new_offers_count = await session.scalar(
            select(func.count(Offer.id))
            .where(Offer.first_seen >= month_start)
            .where(Offer.first_seen < month_end)
        )
        
        avg_price = await session.scalar(
            select(func.avg(Offer.price))
            .where(Offer.first_seen >= month_start)
        )
        
        # Price trends
        price_trends = await self._calculate_price_trends(
            session, month_start, month_end
        )
        
        report = {
            "period": {
                "year": year,
                "month": month,
                "start": month_start.isoformat(),
                "end": month_end.isoformat(),
            },
            "summary": {
                "total_new_offers": new_offers_count,
                "avg_price": round(float(avg_price), 2) if avg_price else None,
            },
            "price_trends": price_trends,
        }
        
        return report
    
    async def _calculate_price_trends(
        self,
        session: AsyncSession,
        start: datetime,
        end: datetime
    ) -> dict:
        """Calculate price trends for the period."""
        # Get average price by week
        weekly_avg = await session.execute(
            select(
                func.date_trunc('week', Offer.first_seen),
                func.avg(Offer.price)
            )
            .where(Offer.first_seen >= start)
            .where(Offer.first_seen < end)
            .group_by(func.date_trunc('week', Offer.first_seen))
            .order_by(func.date_trunc('week', Offer.first_seen))
        )
        
        weekly_data = weekly_avg.all()
        
        if len(weekly_data) >= 2:
            first_week_price = float(weekly_data[0][1])
            last_week_price = float(weekly_data[-1][1])
            
            change_percent = ((last_week_price - first_week_price) / first_week_price) * 100
            
            return {
                "first_week_avg": round(first_week_price, 2),
                "last_week_avg": round(last_week_price, 2),
                "change_percent": round(change_percent, 2),
                "trend": "increasing" if change_percent > 0 else "decreasing" if change_percent < 0 else "stable",
            }
        
        return {"trend": "unknown"}
    
    def format_report_email(self, report: dict) -> str:
        """Format report as HTML email."""
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h1>Weekly Report: {report['period']['start'][:10]} to {report['period']['end'][:10]}</h1>
            
            <h2>Summary</h2>
            <ul>
                <li>New offers: <strong>{report['summary']['total_new_offers']}</strong></li>
                <li>Price drops: <strong>{report['summary']['total_price_drops']}</strong></li>
                <li>Average price: <strong>{report['summary']['avg_price']:,.0f} PLN</strong></li>
            </ul>
            
            <h2>Top Cities</h2>
            <ul>
        """
        
        for city, count in report['top_cities'].items():
            html += f"<li>{city}: {count} offers</li>"
        
        html += """
            </ul>
            
            <h2>Latest Offers</h2>
            <table border="1" cellpadding="5" style="border-collapse: collapse;">
                <tr>
                    <th>Title</th>
                    <th>Price</th>
                    <th>City</th>
                </tr>
        """
        
        for offer in report['new_offers'][:5]:
            html += f"""
                <tr>
                    <td><a href="{offer['url']}">{offer['title'][:50]}</a></td>
                    <td>{offer['price']:,.0f} PLN</td>
                    <td>{offer['city']}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html


class ScheduledReports:
    """Scheduled report generation and delivery."""
    
    async def send_weekly_reports(self):
        """Send weekly reports to all users."""
        from app.db import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            generator = ReportGenerator()
            notifier = get_notification_manager()
            
            # Get all users with reports enabled
            # TODO: Query users from database
            users = ["default_user"]  # Placeholder
            
            for user_id in users:
                try:
                    report = await generator.generate_weekly_report(
                        session, user_id
                    )
                    
                    # Send email
                    if notifier.email_enabled:
                        html = generator.format_report_email(report)
                        # TODO: Send email
                    
                    logger.info(f"Sent weekly report to {user_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send report to {user_id}: {e}")


# Global instance
_report_generator: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """Get or create report generator."""
    global _report_generator
    
    if _report_generator is None:
        _report_generator = ReportGenerator()
    
    return _report_generator
