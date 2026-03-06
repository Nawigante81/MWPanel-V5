"""
Office Reports Service - Raporty dla Właścicieli Biura

Kompleksowe raportowanie dla zarządzania biurem nieruchomości.
Wyniki, trendy, analiza efektywności.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class ReportPeriod(str, Enum):
    """Okresy raportowania"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class AgentRanking:
    """Ranking agenta"""
    position: int
    agent_id: str
    agent_name: str
    
    # Metryki
    transactions_count: int
    sales_value: float
    commission_earned: float
    
    # Efektywność
    conversion_rate: float  # Z leada do transakcji
    avg_time_to_sale_days: float
    
    # Trend
    vs_last_period: float  # Zmiana vs poprzedni okres (%)


@dataclass
class ListingPerformanceReport:
    """Wydajność ofert"""
    total_listings: int
    new_listings: int
    sold_listings: int
    withdrawn_listings: int
    
    # Czasy
    avg_days_on_market: float
    avg_days_to_sale: float
    
    # Konwersja
    inquiry_to_presentation_rate: float
    presentation_to_offer_rate: float
    offer_to_sale_rate: float
    
    # Ceny
    avg_price_reduction_percent: float
    price_reductions_count: int


@dataclass
class LeadConversionReport:
    """Konwersja leadów"""
    total_leads: int
    new_leads: int
    converted_leads: int
    lost_leads: int
    
    # Ścieżka konwersji
    inquiry_to_lead_rate: float
    lead_to_presentation_rate: float
    presentation_to_sale_rate: float
    
    # Źródła leadów
    leads_by_source: Dict[str, int]
    conversion_by_source: Dict[str, float]
    
    # Jakość leadów
    avg_lead_score: float
    high_quality_leads_percent: float


@dataclass
class FinancialReport:
    """Raport finansowy"""
    period: str
    
    # Przychody
    total_commission: float
    commission_from_sales: float
    commission_from_rentals: float
    other_income: float
    
    # Rozchody (jeśli śledzone)
    marketing_costs: float
    operational_costs: float
    salaries: float
    
    # Zysk
    gross_profit: float
    net_profit: float
    profit_margin: float
    
    # Płynność
    outstanding_commission: float  # Należne ale niezapłacone
    paid_commission: float


class OfficeReportsService:
    """
    Serwis raportów dla właścicieli biura.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    # ===== RAPORTY AGENTÓW =====
    
    async def get_agents_ranking(
        self,
        organization_id: str,
        period: ReportPeriod = ReportPeriod.MONTHLY,
        year: Optional[int] = None,
        month: Optional[int] = None,
        quarter: Optional[int] = None
    ) -> List[AgentRanking]:
        """Ranking agentów"""
        if year is None:
            year = datetime.utcnow().year
        
        # Określ zakres dat
        start_date, end_date = self._get_date_range(period, year, month, quarter)
        
        # Pobierz transakcje
        from app.services.commission_service import Transaction
        
        transactions = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date,
            Transaction.status == "completed"
        ).all()
        
        # Grupuj po agencie
        agent_stats = {}
        for t in transactions:
            agent_id = t.listing_agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    'transactions': 0,
                    'sales_value': 0.0,
                    'commission': 0.0
                }
            
            agent_stats[agent_id]['transactions'] += 1
            agent_stats[agent_id]['sales_value'] += t.sale_price
            agent_stats[agent_id]['commission'] += t.commission_amount * t.listing_agent_share_percent / 100
        
        # Pobierz dane agentów
        from app.db.models import User
        
        rankings = []
        for agent_id, stats in agent_stats.items():
            user = self.db.query(User).filter(User.id == agent_id).first()
            agent_name = user.email if user else agent_id  # Fallback
            
            rankings.append(AgentRanking(
                position=0,  # Ustawimy później
                agent_id=agent_id,
                agent_name=agent_name,
                transactions_count=stats['transactions'],
                sales_value=stats['sales_value'],
                commission_earned=stats['commission'],
                conversion_rate=0.0,  # TODO
                avg_time_to_sale_days=0.0,  # TODO
                vs_last_period=0.0  # TODO
            ))
        
        # Sortuj po prowizji i przypisz pozycje
        rankings.sort(key=lambda x: x.commission_earned, reverse=True)
        for i, r in enumerate(rankings, 1):
            r.position = i
        
        return rankings
    
    # ===== RAPORTY OFERT =====
    
    async def get_listing_performance(
        self,
        organization_id: str,
        period: ReportPeriod = ReportPeriod.MONTHLY,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> ListingPerformanceReport:
        """Wydajność ofert"""
        from app.services.listing_management import Listing, ListingStatus
        
        start_date, end_date = self._get_date_range(period, year, month)
        
        # Oferty
        total_listings = self.db.query(Listing).filter(
            Listing.organization_id == organization_id
        ).count()
        
        new_listings = self.db.query(Listing).filter(
            Listing.organization_id == organization_id,
            Listing.created_at >= start_date,
            Listing.created_at < end_date
        ).count()
        
        sold_listings = self.db.query(Listing).filter(
            Listing.organization_id == organization_id,
            Listing.status == ListingStatus.SOLD,
            Listing.status_changed_at >= start_date,
            Listing.status_changed_at < end_date
        ).count()
        
        withdrawn_listings = self.db.query(Listing).filter(
            Listing.organization_id == organization_id,
            Listing.status == ListingStatus.WITHDRAWN,
            Listing.status_changed_at >= start_date,
            Listing.status_changed_at < end_date
        ).count()
        
        # Średni czas sprzedaży
        sold = self.db.query(Listing).filter(
            Listing.organization_id == organization_id,
            Listing.status == ListingStatus.SOLD,
            Listing.status_changed_at >= start_date,
            Listing.status_changed_at < end_date
        ).all()
        
        avg_days = 0
        if sold:
            days = [(l.status_changed_at - l.created_at).days for l in sold if l.status_changed_at]
            avg_days = sum(days) / len(days) if days else 0
        
        return ListingPerformanceReport(
            total_listings=total_listings,
            new_listings=new_listings,
            sold_listings=sold_listings,
            withdrawn_listings=withdrawn_listings,
            avg_days_on_market=avg_days,
            avg_days_to_sale=avg_days,
            inquiry_to_presentation_rate=0.0,  # TODO
            presentation_to_offer_rate=0.0,  # TODO
            offer_to_sale_rate=0.0,  # TODO
            avg_price_reduction_percent=0.0,  # TODO
            price_reductions_count=0  # TODO
        )
    
    # ===== RAPORTY LEADÓW =====
    
    async def get_lead_conversion(
        self,
        organization_id: str,
        period: ReportPeriod = ReportPeriod.MONTHLY,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> LeadConversionReport:
        """Konwersja leadów"""
        from app.services.lead_management import Lead, LeadStatus, LeadSource
        
        start_date, end_date = self._get_date_range(period, year, month)
        
        # Leady
        total_leads = self.db.query(Lead).filter(
            Lead.organization_id == organization_id
        ).count()
        
        new_leads = self.db.query(Lead).filter(
            Lead.organization_id == organization_id,
            Lead.created_at >= start_date,
            Lead.created_at < end_date
        ).count()
        
        converted_leads = self.db.query(Lead).filter(
            Lead.organization_id == organization_id,
            Lead.status == LeadStatus.CLOSED_WON,
            Lead.converted_at >= start_date,
            Lead.converted_at < end_date
        ).count()
        
        lost_leads = self.db.query(Lead).filter(
            Lead.organization_id == organization_id,
            Lead.status == LeadStatus.CLOSED_LOST,
            Lead.updated_at >= start_date,
            Lead.updated_at < end_date
        ).count()
        
        # Źródła leadów
        sources = self.db.query(Lead.source, func.count(Lead.id)).filter(
            Lead.organization_id == organization_id,
            Lead.created_at >= start_date,
            Lead.created_at < end_date
        ).group_by(Lead.source).all()
        
        leads_by_source = {s.value if s else 'unknown': count for s, count in sources}
        
        return LeadConversionReport(
            total_leads=total_leads,
            new_leads=new_leads,
            converted_leads=converted_leads,
            lost_leads=lost_leads,
            inquiry_to_lead_rate=0.0,  # TODO
            lead_to_presentation_rate=0.0,  # TODO
            presentation_to_sale_rate=0.0,  # TODO
            leads_by_source=leads_by_source,
            conversion_by_source={},  # TODO
            avg_lead_score=0.0,  # TODO
            high_quality_leads_percent=0.0  # TODO
        )
    
    # ===== RAPORTY FINANSOWE =====
    
    async def get_financial_report(
        self,
        organization_id: str,
        period: ReportPeriod = ReportPeriod.MONTHLY,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> FinancialReport:
        """Raport finansowy"""
        from app.services.commission_service import Transaction
        
        start_date, end_date = self._get_date_range(period, year, month)
        
        period_str = f"{year}-{month:02d}" if month else str(year)
        
        # Transakcje
        transactions = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date,
            Transaction.status == "completed"
        ).all()
        
        total_commission = sum(t.commission_amount for t in transactions)
        
        commission_from_sales = sum(
            t.commission_amount for t in transactions
            if t.transaction_type == "sale"
        )
        
        commission_from_rentals = sum(
            t.commission_amount for t in transactions
            if t.transaction_type == "rent"
        )
        
        # Należne niezapłacone
        outstanding = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.commission_status.in_(["earned", "invoiced"])
        ).all()
        
        outstanding_amount = sum(
            t.commission_amount - t.listing_agent_paid_amount - (t.selling_agent_paid_amount or 0)
            for t in outstanding
        )
        
        # Zapłacone
        paid = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.commission_status == "paid"
        ).all()
        
        paid_amount = sum(t.commission_amount for t in paid)
        
        return FinancialReport(
            period=period_str,
            total_commission=total_commission,
            commission_from_sales=commission_from_sales,
            commission_from_rentals=commission_from_rentals,
            other_income=0.0,  # TODO
            marketing_costs=0.0,  # TODO
            operational_costs=0.0,  # TODO
            salaries=0.0,  # TODO
            gross_profit=total_commission,  # TODO: minus koszty
            net_profit=total_commission,  # TODO: minus wszystkie koszty
            profit_margin=0.0,  # TODO
            outstanding_commission=outstanding_amount,
            paid_commission=paid_amount
        )
    
    # ===== DASHBOARD WŁAŚCICIELA =====
    
    async def get_owner_dashboard(
        self,
        organization_id: str
    ) -> Dict[str, Any]:
        """Dashboard dla właściciela biura"""
        today = datetime.utcnow()
        
        # Ten miesiąc
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Dzisiaj
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Transakcje dzisiaj
        from app.services.commission_service import Transaction
        
        today_transactions = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.transaction_date >= today_start
        ).count()
        
        today_commission = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.transaction_date >= today_start
        ).with_entities(func.sum(Transaction.commission_amount)).scalar() or 0
        
        # Ten miesiąc
        month_transactions = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.transaction_date >= month_start
        ).count()
        
        month_commission = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.transaction_date >= month_start
        ).with_entities(func.sum(Transaction.commission_amount)).scalar() or 0
        
        # Aktywne oferty
        from app.services.listing_management import Listing, ListingStatus
        
        active_listings = self.db.query(Listing).filter(
            Listing.organization_id == organization_id,
            Listing.status == ListingStatus.ACTIVE
        ).count()
        
        # Nowe oferty dzisiaj
        new_listings_today = self.db.query(Listing).filter(
            Listing.organization_id == organization_id,
            Listing.created_at >= today_start
        ).count()
        
        # Aktywni agenci
        from app.db.models import User
        
        active_agents = self.db.query(User).filter(
            User.organization_id == organization_id,
            User.is_active == True
        ).count()
        
        # Oczekujące prezentacje dzisiaj
        from app.services.calendar_service import CalendarEvent, EventType
        
        presentations_today = self.db.query(CalendarEvent).filter(
            CalendarEvent.organization_id == organization_id,
            CalendarEvent.event_type == EventType.PRESENTATION,
            CalendarEvent.start_time >= today_start,
            CalendarEvent.start_time < today_start + timedelta(days=1)
        ).count()
        
        # Ranking agentów (miesiąc)
        top_agents = await self.get_agents_ranking(
            organization_id=organization_id,
            period=ReportPeriod.MONTHLY,
            year=today.year,
            month=today.month
        )
        
        return {
            'today': {
                'transactions': today_transactions,
                'commission': round(today_commission, 2),
                'new_listings': new_listings_today,
                'presentations': presentations_today,
            },
            'this_month': {
                'transactions': month_transactions,
                'commission': round(month_commission, 2),
                'active_listings': active_listings,
            },
            'team': {
                'active_agents': active_agents,
                'top_agents': [a.to_dict() for a in top_agents[:3]],
            },
            'alerts': [
                # TODO: Generuj alerty (np. oferty długo nie sprzedane, agenci bez wyników)
            ]
        }
    
    # ===== POMOCNICZE =====
    
    def _get_date_range(
        self,
        period: ReportPeriod,
        year: int,
        month: Optional[int] = None,
        quarter: Optional[int] = None
    ) -> tuple[datetime, datetime]:
        """Zwróć zakres dat dla okresu"""
        if period == ReportPeriod.DAILY:
            start = datetime(year, month or 1, 1)
            end = start + timedelta(days=1)
        
        elif period == ReportPeriod.WEEKLY:
            # Zakładamy tydzień zaczyna się w poniedziałek
            start = datetime(year, month or 1, 1)
            end = start + timedelta(weeks=1)
        
        elif period == ReportPeriod.MONTHLY:
            start = datetime(year, month or 1, 1)
            if month == 12:
                end = datetime(year + 1, 1, 1)
            else:
                end = datetime(year, (month or 1) + 1, 1)
        
        elif period == ReportPeriod.QUARTERLY:
            q = quarter or 1
            start_month = (q - 1) * 3 + 1
            start = datetime(year, start_month, 1)
            if q == 4:
                end = datetime(year + 1, 1, 1)
            else:
                end = datetime(year, start_month + 3, 1)
        
        elif period == ReportPeriod.YEARLY:
            start = datetime(year, 1, 1)
            end = datetime(year + 1, 1, 1)
        
        else:
            start = datetime(year, 1, 1)
            end = datetime(year + 1, 1, 1)
        
        return start, end
    
    async def generate_full_report(
        self,
        organization_id: str,
        period: ReportPeriod = ReportPeriod.MONTHLY,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generuj pełny raport dla właściciela"""
        if year is None:
            year = datetime.utcnow().year
        
        period_str = f"{year}-{month:02d}" if month else str(year)
        
        # Pobierz wszystkie raporty
        agents_ranking = await self.get_agents_ranking(organization_id, period, year, month)
        listing_perf = await self.get_listing_performance(organization_id, period, year, month)
        lead_conversion = await self.get_lead_conversion(organization_id, period, year, month)
        financial = await self.get_financial_report(organization_id, period, year, month)
        
        return {
            'report_title': f"Raport miesięczny - {period_str}",
            'generated_at': datetime.utcnow().isoformat(),
            'period': {
                'type': period.value,
                'year': year,
                'month': month,
            },
            'executive_summary': {
                'total_commission': round(financial.total_commission, 2),
                'total_transactions': listing_perf.sold_listings,
                'active_listings': listing_perf.total_listings,
                'new_leads': lead_conversion.new_leads,
                'top_performer': agents_ranking[0].agent_name if agents_ranking else None,
            },
            'agents': {
                'ranking': [a.to_dict() for a in agents_ranking[:10]],
                'total_agents': len(agents_ranking),
            },
            'listings': {
                'total': listing_perf.total_listings,
                'new': listing_perf.new_listings,
                'sold': listing_perf.sold_listings,
                'withdrawn': listing_perf.withdrawn_listings,
                'avg_days_on_market': round(listing_perf.avg_days_on_market, 1),
            },
            'leads': {
                'total': lead_conversion.total_leads,
                'new': lead_conversion.new_leads,
                'converted': lead_conversion.converted_leads,
                'by_source': lead_conversion.leads_by_source,
            },
            'financial': {
                'commission': round(financial.total_commission, 2),
                'from_sales': round(financial.commission_from_sales, 2),
                'from_rentals': round(financial.commission_from_rentals, 2),
                'outstanding': round(financial.outstanding_commission, 2),
            },
            'recommendations': await self._generate_recommendations(
                organization_id, agents_ranking, listing_perf, lead_conversion
            )
        }
    
    async def _generate_recommendations(
        self,
        organization_id: str,
        agents_ranking: List[AgentRanking],
        listing_perf: ListingPerformanceReport,
        lead_conversion: LeadConversionReport
    ) -> List[str]:
        """Generuj rekomendacje na podstawie danych"""
        recommendations = []
        
        # Analiza agentów
        if len(agents_ranking) > 1:
            top = agents_ranking[0]
            bottom = agents_ranking[-1]
            
            if top.commission_earned > bottom.commission_earned * 3:
                recommendations.append(
                    f"Duża różnica w wynikach - {top.agent_name} zarabia 3x więcej niż {bottom.agent_name}. "
                    "Rozważ mentoring lub szkolenie."
                )
        
        # Analiza ofert
        if listing_perf.avg_days_on_market > 90:
            recommendations.append(
                f"Średni czas sprzedaży ({listing_perf.avg_days_on_market:.0f} dni) jest wysoki. "
                "Sprawdź ceny ofert i jakość zdjęć."
            )
        
        if listing_perf.withdrawn_listings > listing_perf.sold_listings:
            recommendations.append(
                "Więcej ofert wycofanych niż sprzedanych. "
                "Przeanalizuj powody rezygnacji właścicieli."
            )
        
        # Analiza leadów
        if lead_conversion.new_leads < 10:
            recommendations.append(
                "Niski napływ nowych leadów. "
                "Zwiększ marketing lub aktywność na portalach."
            )
        
        return recommendations
