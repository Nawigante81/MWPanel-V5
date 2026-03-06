"""
Scheduled Reports & Exports Service

Automated report generation and delivery system.
Supports multiple formats (PDF, Excel, CSV) and delivery methods.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import json
import io
import csv

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session
import uuid

from app.core.logging import get_logger

logger = get_logger(__name__)


class ReportFormat(str, Enum):
    """Report output formats"""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class ReportType(str, Enum):
    """Types of reports"""
    NEW_OFFERS = "new_offers"
    PRICE_CHANGES = "price_changes"
    MARKET_SUMMARY = "market_summary"
    LEAD_PIPELINE = "lead_pipeline"
    INVESTMENT_ANALYSIS = "investment_analysis"
    CUSTOM_SEARCH = "custom_search"
    ACTIVITY_SUMMARY = "activity_summary"


class DeliveryMethod(str, Enum):
    """Report delivery methods"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    DOWNLOAD = "download"
    SLACK = "slack"
    TEAMS = "teams"


class ScheduleFrequency(str, Enum):
    """Report schedule frequencies"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ScheduledReport(Base):
    """Scheduled report database model"""
    __tablename__ = 'scheduled_reports'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Report configuration
    report_type = Column(String(50), nullable=False)
    format = Column(String(20), nullable=False)
    
    # Schedule
    frequency = Column(String(20), nullable=False)
    schedule_config = Column(JSONB, default=dict)  # day_of_week, hour, minute, etc.
    timezone = Column(String(50), default='UTC')
    
    # Filters and parameters
    filters = Column(JSONB, default=dict)
    parameters = Column(JSONB, default=dict)
    
    # Delivery
    delivery_method = Column(String(20), nullable=False)
    delivery_config = Column(JSONB, default=dict)  # email, webhook URL, etc.
    
    # Status
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, default=0)
    
    # Ownership
    created_by = Column(String(100), nullable=False)
    organization_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)


class ReportExecution(Base):
    """Report execution history"""
    __tablename__ = 'report_executions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey('scheduled_reports.id'))
    
    # Execution details
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default='running')  # running, completed, failed
    
    # Results
    record_count = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    file_path = Column(String(500), nullable=True)
    download_url = Column(String(500), nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Delivery tracking
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    delivery_status = Column(String(20), nullable=True)


@dataclass
class ReportData:
    """Report data container"""
    title: str
    generated_at: datetime
    columns: List[str]
    rows: List[Dict[str, Any]]
    summary: Dict[str, Any] = field(default_factory=dict)
    
    def to_csv(self) -> str:
        """Export to CSV format"""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.columns)
        writer.writeheader()
        writer.writerows(self.rows)
        return output.getvalue()
    
    def to_json(self) -> str:
        """Export to JSON format"""
        return json.dumps({
            'title': self.title,
            'generated_at': self.generated_at.isoformat(),
            'columns': self.columns,
            'data': self.rows,
            'summary': self.summary
        }, indent=2, default=str)


class ReportGenerator:
    """Base class for report generators"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def generate(self, filters: Dict[str, Any], parameters: Dict[str, Any]) -> ReportData:
        """Generate report data - to be implemented by subclasses"""
        raise NotImplementedError


class NewOffersReportGenerator(ReportGenerator):
    """Generate report of new offers"""
    
    async def generate(self, filters: Dict[str, Any], parameters: Dict[str, Any]) -> ReportData:
        from app.db.models import Offer
        
        since = filters.get('since', datetime.utcnow() - timedelta(days=1))
        
        query = self.db.query(Offer).filter(Offer.created_at >= since)
        
        if filters.get('city'):
            query = query.filter(Offer.city == filters['city'])
        if filters.get('min_price'):
            query = query.filter(Offer.price >= filters['min_price'])
        if filters.get('max_price'):
            query = query.filter(Offer.price <= filters['max_price'])
        
        offers = query.order_by(Offer.created_at.desc()).all()
        
        rows = []
        for offer in offers:
            rows.append({
                'id': str(offer.id),
                'title': offer.title,
                'city': offer.city,
                'district': offer.district,
                'price': offer.price,
                'area_sqm': offer.area_sqm,
                'rooms': offer.rooms,
                'price_per_sqm': round(offer.price / offer.area_sqm, 2) if offer.area_sqm else None,
                'source': offer.source,
                'created_at': offer.created_at.isoformat(),
                'url': offer.url,
            })
        
        return ReportData(
            title=f"New Offers Report - {since.strftime('%Y-%m-%d')}",
            generated_at=datetime.utcnow(),
            columns=['id', 'title', 'city', 'district', 'price', 'area_sqm', 'rooms', 
                    'price_per_sqm', 'source', 'created_at', 'url'],
            rows=rows,
            summary={
                'total_offers': len(rows),
                'avg_price': round(sum(r['price'] for r in rows) / len(rows), 2) if rows else 0,
                'sources': list(set(r['source'] for r in rows)),
            }
        )


class PriceChangesReportGenerator(ReportGenerator):
    """Generate report of price changes"""
    
    async def generate(self, filters: Dict[str, Any], parameters: Dict[str, Any]) -> ReportData:
        from app.db.models import Offer, PriceHistory
        
        since = filters.get('since', datetime.utcnow() - timedelta(days=7))
        
        # Get recent price changes
        changes = self.db.query(PriceHistory).filter(
            PriceHistory.changed_at >= since
        ).order_by(PriceHistory.changed_at.desc()).all()
        
        rows = []
        for change in changes:
            offer = self.db.query(Offer).filter(Offer.id == change.offer_id).first()
            if offer:
                price_change_pct = ((change.new_price - change.old_price) / change.old_price * 100) if change.old_price else 0
                
                rows.append({
                    'offer_id': str(offer.id),
                    'title': offer.title,
                    'city': offer.city,
                    'old_price': change.old_price,
                    'new_price': change.new_price,
                    'price_change': change.new_price - change.old_price,
                    'price_change_percent': round(price_change_pct, 2),
                    'changed_at': change.changed_at.isoformat(),
                    'url': offer.url,
                })
        
        return ReportData(
            title=f"Price Changes Report - {since.strftime('%Y-%m-%d')}",
            generated_at=datetime.utcnow(),
            columns=['offer_id', 'title', 'city', 'old_price', 'new_price', 
                    'price_change', 'price_change_percent', 'changed_at', 'url'],
            rows=rows,
            summary={
                'total_changes': len(rows),
                'price_drops': sum(1 for r in rows if r['price_change'] < 0),
                'price_increases': sum(1 for r in rows if r['price_change'] > 0),
                'avg_change_percent': round(sum(r['price_change_percent'] for r in rows) / len(rows), 2) if rows else 0,
            }
        )


class ScheduledReportService:
    """
    Professional scheduled reports service.
    
    Features:
    - Automated report generation
    - Multiple output formats
    - Flexible scheduling
    - Multiple delivery methods
    - Execution tracking
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.generators: Dict[ReportType, ReportGenerator] = {
            ReportType.NEW_OFFERS: NewOffersReportGenerator(db_session),
            ReportType.PRICE_CHANGES: PriceChangesReportGenerator(db_session),
        }
    
    async def create_schedule(
        self,
        name: str,
        report_type: ReportType,
        format: ReportFormat,
        frequency: ScheduleFrequency,
        delivery_method: DeliveryMethod,
        created_by: str,
        description: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
        delivery_config: Optional[Dict[str, Any]] = None,
        organization_id: Optional[str] = None,
        timezone: str = 'UTC'
    ) -> ScheduledReport:
        """Create a new scheduled report"""
        
        # Calculate next run time
        next_run = self._calculate_next_run(frequency, schedule_config or {}, timezone)
        
        report = ScheduledReport(
            name=name,
            description=description,
            report_type=report_type.value,
            format=format.value,
            frequency=frequency.value,
            schedule_config=schedule_config or {},
            timezone=timezone,
            filters=filters or {},
            parameters=parameters or {},
            delivery_method=delivery_method.value,
            delivery_config=delivery_config or {},
            created_by=created_by,
            organization_id=organization_id,
            next_run_at=next_run
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        logger.info(f"Created scheduled report '{name}' (ID: {report.id})")
        
        return report
    
    def _calculate_next_run(
        self,
        frequency: ScheduleFrequency,
        config: Dict[str, Any],
        timezone: str
    ) -> datetime:
        """Calculate next run time based on schedule"""
        now = datetime.utcnow()
        
        if frequency == ScheduleFrequency.HOURLY:
            return now + timedelta(hours=1)
        
        elif frequency == ScheduleFrequency.DAILY:
            hour = config.get('hour', 8)
            minute = config.get('minute', 0)
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
        
        elif frequency == ScheduleFrequency.WEEKLY:
            day_of_week = config.get('day_of_week', 1)  # Monday
            hour = config.get('hour', 8)
            minute = config.get('minute', 0)
            
            days_ahead = day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            
            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run
        
        elif frequency == ScheduleFrequency.MONTHLY:
            day_of_month = config.get('day_of_month', 1)
            hour = config.get('hour', 8)
            minute = config.get('minute', 0)
            
            if now.day >= day_of_month:
                # Next month
                if now.month == 12:
                    next_run = now.replace(year=now.year + 1, month=1, day=day_of_month)
                else:
                    next_run = now.replace(month=now.month + 1, day=day_of_month)
            else:
                next_run = now.replace(day=day_of_month)
            
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run
        
        return now + timedelta(days=1)
    
    async def execute_report(self, report_id: str) -> Optional[ReportExecution]:
        """Execute a scheduled report"""
        report = self.db.query(ScheduledReport).filter(
            ScheduledReport.id == report_id
        ).first()
        
        if not report or not report.is_active:
            return None
        
        # Create execution record
        execution = ReportExecution(
            report_id=uuid.UUID(report_id),
            status='running'
        )
        self.db.add(execution)
        self.db.commit()
        
        try:
            # Get generator
            report_type = ReportType(report.report_type)
            generator = self.generators.get(report_type)
            
            if not generator:
                raise ValueError(f"Unknown report type: {report_type}")
            
            # Generate report
            report_data = await generator.generate(
                filters=report.filters,
                parameters=report.parameters
            )
            
            # Export to requested format
            format = ReportFormat(report.format)
            file_content = self._export_report(report_data, format)
            
            # Save file
            file_path = f"/tmp/reports/{report_id}_{execution.id}.{format.value}"
            import os
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w' if isinstance(file_content, str) else 'wb') as f:
                f.write(file_content)
            
            # Update execution
            execution.status = 'completed'
            execution.completed_at = datetime.utcnow()
            execution.record_count = len(report_data.rows)
            execution.file_size_bytes = len(file_content) if isinstance(file_content, bytes) else len(file_content.encode())
            execution.file_path = file_path
            
            # Update report
            report.last_run_at = datetime.utcnow()
            report.run_count += 1
            report.next_run_at = self._calculate_next_run(
                ScheduleFrequency(report.frequency),
                report.schedule_config,
                report.timezone
            )
            
            self.db.commit()
            
            # Deliver report
            await self._deliver_report(report, execution, file_content)
            
            logger.info(f"Report {report_id} executed successfully")
            
        except Exception as e:
            execution.status = 'failed'
            execution.completed_at = datetime.utcnow()
            execution.error_message = str(e)
            self.db.commit()
            
            logger.error(f"Report {report_id} execution failed: {e}")
        
        return execution
    
    def _export_report(self, data: ReportData, format: ReportFormat) -> str:
        """Export report to specified format"""
        if format == ReportFormat.CSV:
            return data.to_csv()
        elif format == ReportFormat.JSON:
            return data.to_json()
        elif format == ReportFormat.EXCEL:
            # Would use pandas/openpyxl in production
            return data.to_csv()  # Fallback
        elif format == ReportFormat.HTML:
            # Simple HTML table
            html = f"<h1>{data.title}</h1>"
            html += f"<p>Generated: {data.generated_at}</p>"
            html += "<table border='1'><tr>"
            for col in data.columns:
                html += f"<th>{col}</th>"
            html += "</tr>"
            for row in data.rows:
                html += "<tr>"
                for col in data.columns:
                    html += f"<td>{row.get(col, '')}</td>"
                html += "</tr>"
            html += "</table>"
            return html
        else:
            return data.to_json()
    
    async def _deliver_report(
        self,
        report: ScheduledReport,
        execution: ReportExecution,
        file_content: str
    ):
        """Deliver report via configured method"""
        delivery_method = DeliveryMethod(report.delivery_method)
        
        if delivery_method == DeliveryMethod.EMAIL:
            await self._deliver_email(report, execution, file_content)
        elif delivery_method == DeliveryMethod.WEBHOOK:
            await self._deliver_webhook(report, execution, file_content)
        elif delivery_method == DeliveryMethod.DOWNLOAD:
            # Generate download URL
            execution.download_url = f"/api/reports/download/{execution.id}"
            self.db.commit()
        
        execution.delivered_at = datetime.utcnow()
        execution.delivery_status = 'delivered'
        self.db.commit()
    
    async def _deliver_email(
        self,
        report: ScheduledReport,
        execution: ReportExecution,
        file_content: str
    ):
        """Deliver report via email"""
        email_config = report.delivery_config
        to_email = email_config.get('to')
        
        if not to_email:
            return
        
        # Would integrate with email service
        logger.info(f"Would send report {report.id} to {to_email}")
    
    async def _deliver_webhook(
        self,
        report: ScheduledReport,
        execution: ReportExecution,
        file_content: str
    ):
        """Deliver report via webhook"""
        webhook_url = report.delivery_config.get('url')
        
        if not webhook_url:
            return
        
        # Would make HTTP POST request
        logger.info(f"Would POST report {report.id} to {webhook_url}")
    
    async def get_pending_reports(self) -> List[ScheduledReport]:
        """Get reports that are due to run"""
        return self.db.query(ScheduledReport).filter(
            ScheduledReport.is_active == True,
            ScheduledReport.next_run_at <= datetime.utcnow()
        ).all()
    
    async def run_due_reports(self):
        """Execute all reports that are due"""
        pending = await self.get_pending_reports()
        
        for report in pending:
            await self.execute_report(str(report.id))


# Celery task for scheduled reports

from celery import shared_task

@shared_task
def run_scheduled_reports():
    """Celery task to run due scheduled reports"""
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        service = ScheduledReportService(db)
        import asyncio
        asyncio.run(service.run_due_reports())
    finally:
        db.close()
