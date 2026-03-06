"""
Commission Service - System Prowizji i Rozliczeń

Zarządzanie prowizjami, podziałem, celami sprzedażowymi,
bonusami i raportowaniem dla agentów.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import uuid

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, 
    Integer, Float, Boolean, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session
from sqlalchemy import func

from app.core.logging import get_logger

logger = get_logger(__name__)


class TransactionStatus(str, Enum):
    """Status transakcji"""
    PENDING = "pending"                    # Oczekuje na finalizację
    COMPLETED = "completed"                # Zakończona
    CANCELLED = "cancelled"                # Anulowana
    DISPUTED = "disputed"                  # Sporna


class CommissionStatus(str, Enum):
    """Status prowizji"""
    PENDING = "pending"                    # Nienależna jeszcze
    EARNED = "earned"                      # Należna (po podpisaniu umowy)
    INVOICED = "invoiced"                  # Zafakturowana
    PAID = "paid"                          # Wypłacona
    WITHHELD = "withheld"                  # Wstrzymana (spór, reklamacja)


class Transaction(Base):
    """Transakcja sprzedaży/wynajmu"""
    __tablename__ = 'transactions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Powiązania
    listing_id = Column(UUID(as_uuid=True), ForeignKey('listings.id'), nullable=False)
    buyer_client_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=True)
    
    # Agenci
    listing_agent_id = Column(String(100), nullable=False)  # Agent wprowadzający
    selling_agent_id = Column(String(100), nullable=True)   # Agent sprzedający (jeśli inny)
    
    # Szczegóły transakcji
    transaction_type = Column(String(20), default="sale")  # sale, rent
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    sale_price = Column(Float, nullable=False)
    
    # Prowizja
    commission_percent = Column(Float, default=3.0)
    commission_amount = Column(Float, nullable=False)
    commission_status = Column(SQLEnum(CommissionStatus), default=CommissionStatus.PENDING)
    
    # Podział prowizji
    listing_agent_share_percent = Column(Float, default=50.0)
    selling_agent_share_percent = Column(Float, default=50.0)
    office_share_percent = Column(Float, default=0.0)  # Dla biura (jeśli inaczej)
    
    # Wypłaty
    listing_agent_paid = Column(Boolean, default=False)
    listing_agent_paid_at = Column(DateTime(timezone=True), nullable=True)
    listing_agent_paid_amount = Column(Float, default=0.0)
    
    selling_agent_paid = Column(Boolean, default=False)
    selling_agent_paid_at = Column(DateTime(timezone=True), nullable=True)
    selling_agent_paid_amount = Column(Float, default=0.0)
    
    # Status
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING)
    
    # Organizacja
    organization_id = Column(String(100), nullable=True, index=True)
    
    # Notatki
    notes = Column(Text, nullable=True)


class AgentTarget(Base):
    """Cele sprzedażowe agenta"""
    __tablename__ = 'agent_targets'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(100), nullable=False, index=True)
    
    # Okres
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)  # Jeśli null - cel roczny
    quarter = Column(Integer, nullable=True)  # Jeśli null - cel kwartalny
    
    # Cele
    target_transactions = Column(Integer, default=0)  # Liczba transakcji
    target_commission = Column(Float, default=0.0)  # Wartość prowizji
    target_sales_value = Column(Float, default=0.0)  # Wartość sprzedaży
    
    # Bonusy
    bonus_threshold = Column(Float, nullable=True)  # Próg do bonusu
    bonus_amount = Column(Float, default=0.0)
    
    # Organizacja
    organization_id = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AgentBonus(Base):
    """Bonusy dla agentów"""
    __tablename__ = 'agent_bonuses'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(100), nullable=False)
    
    # Szczegóły bonusu
    bonus_type = Column(String(50), nullable=False)  # target_achieved, top_seller, referral, etc.
    description = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    
    # Status
    status = Column(String(20), default="pending")  # pending, approved, paid
    
    # Daty
    earned_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    # Organizacja
    organization_id = Column(String(100), nullable=True)


@dataclass
class AgentPerformance:
    """Wyniki agenta"""
    agent_id: str
    agent_name: str
    
    # Okres
    period: str  # "2024-01" lub "2024-Q1"
    
    # Transakcje
    transactions_count: int
    transactions_value: float
    commission_earned: float
    commission_paid: float
    commission_pending: float
    
    # Cele
    target_transactions: int
    target_commission: float
    target_achieved_percent: float
    
    # Bonusy
    bonuses_earned: float
    bonuses_paid: float
    
    # Ranking
    rank_in_office: int
    total_agents: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'agent_name': self.agent_name,
            'period': self.period,
            'transactions': {
                'count': self.transactions_count,
                'value': round(self.transactions_value, 2),
            },
            'commission': {
                'earned': round(self.commission_earned, 2),
                'paid': round(self.commission_paid, 2),
                'pending': round(self.commission_pending, 2),
            },
            'target': {
                'transactions': self.target_transactions,
                'commission': round(self.target_commission, 2),
                'achieved_percent': round(self.target_achieved_percent, 1),
            },
            'bonuses': {
                'earned': round(self.bonuses_earned, 2),
                'paid': round(self.bonuses_paid, 2),
            },
            'ranking': {
                'position': self.rank_in_office,
                'total': self.total_agents,
            }
        }


@dataclass
class OfficePerformance:
    """Wyniki biura"""
    organization_id: str
    period: str
    
    # Ogólne
    total_transactions: int
    total_sales_value: float
    total_commission: float
    
    # Średnie
    avg_transactions_per_agent: float
    avg_commission_per_agent: float
    
    # Top agenci
    top_agents: List[Dict[str, Any]]
    
    # Porównanie z poprzednim okresem
    vs_last_period_percent: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'period': self.period,
            'totals': {
                'transactions': self.total_transactions,
                'sales_value': round(self.total_sales_value, 2),
                'commission': round(self.total_commission, 2),
            },
            'averages': {
                'transactions_per_agent': round(self.avg_transactions_per_agent, 1),
                'commission_per_agent': round(self.avg_commission_per_agent, 2),
            },
            'top_agents': self.top_agents[:5],
            'growth_vs_last_period': round(self.vs_last_period_percent, 1),
        }


class CommissionService:
    """
    Serwis zarządzania prowizjami i rozliczeniami.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    # ===== TRANSAKCJE =====
    
    async def create_transaction(
        self,
        listing_id: uuid.UUID,
        sale_price: float,
        transaction_date: datetime,
        listing_agent_id: str,
        selling_agent_id: Optional[str] = None,
        commission_percent: float = 3.0,
        transaction_type: str = "sale",
        organization_id: Optional[str] = None,
        **kwargs
    ) -> Transaction:
        """Zarejestruj nową transakcję"""
        # Pobierz ofertę
        from app.services.listing_management import ListingManagementService
        
        listing_service = ListingManagementService(self.db)
        listing = await listing_service.get_listing(listing_id)
        
        if not listing:
            raise ValueError(f"Listing {listing_id} not found")
        
        # Oblicz prowizję
        commission_amount = sale_price * commission_percent / 100
        
        # Jeśli ten sam agent - 100% dla niego
        if not selling_agent_id or selling_agent_id == listing_agent_id:
            listing_agent_share = 100.0
            selling_agent_share = 0.0
        else:
            # Podział 50/50 (można konfigurować)
            listing_agent_share = 50.0
            selling_agent_share = 50.0
        
        transaction = Transaction(
            listing_id=listing_id,
            transaction_type=transaction_type,
            transaction_date=transaction_date,
            sale_price=sale_price,
            commission_percent=commission_percent,
            commission_amount=commission_amount,
            listing_agent_id=listing_agent_id,
            selling_agent_id=selling_agent_id,
            listing_agent_share_percent=listing_agent_share,
            selling_agent_share_percent=selling_agent_share,
            organization_id=organization_id,
            **kwargs
        )
        
        self.db.add(transaction)
        
        # Zmień status oferty na sprzedaną
        await listing_service.change_status(
            listing_id=listing_id,
            new_status=ListingStatus.SOLD if transaction_type == "sale" else ListingStatus.RENTED,
            changed_by=listing_agent_id,
            reason=f"Transakcja zakończona, cena: {sale_price:,.2f} PLN"
        )
        
        self.db.commit()
        self.db.refresh(transaction)
        
        logger.info(f"Created transaction: {transaction.id}, commission: {commission_amount:,.2f} PLN")
        
        return transaction
    
    async def get_transaction(self, transaction_id: uuid.UUID) -> Optional[Transaction]:
        """Pobierz transakcję"""
        return self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    async def mark_commission_earned(
        self,
        transaction_id: uuid.UUID,
        earned_date: Optional[datetime] = None
    ) -> Optional[Transaction]:
        """Oznacz prowizję jako należną (po podpisaniu umowy)"""
        transaction = await self.get_transaction(transaction_id)
        if not transaction:
            return None
        
        transaction.commission_status = CommissionStatus.EARNED
        transaction.status = TransactionStatus.COMPLETED
        
        self.db.commit()
        
        logger.info(f"Commission earned for transaction {transaction_id}")
        
        return transaction
    
    async def pay_commission(
        self,
        transaction_id: uuid.UUID,
        agent_type: str,  # listing, selling
        paid_amount: float,
        paid_by: str
    ) -> Optional[Transaction]:
        """Wypłać prowizję agentowi"""
        transaction = await self.get_transaction(transaction_id)
        if not transaction:
            return None
        
        if agent_type == "listing":
            transaction.listing_agent_paid = True
            transaction.listing_agent_paid_at = datetime.utcnow()
            transaction.listing_agent_paid_amount = paid_amount
        elif agent_type == "selling" and transaction.selling_agent_id:
            transaction.selling_agent_paid = True
            transaction.selling_agent_paid_at = datetime.utcnow()
            transaction.selling_agent_paid_amount = paid_amount
        
        # Sprawdź czy wszystkie prowizje wypłacone
        if transaction.listing_agent_paid:
            if not transaction.selling_agent_id or transaction.selling_agent_paid:
                transaction.commission_status = CommissionStatus.PAID
        
        self.db.commit()
        
        logger.info(f"Commission paid for transaction {transaction_id}, agent: {agent_type}")
        
        return transaction
    
    # ===== CELE =====
    
    async def set_target(
        self,
        agent_id: str,
        year: int,
        target_transactions: int = 0,
        target_commission: float = 0.0,
        month: Optional[int] = None,
        quarter: Optional[int] = None,
        bonus_threshold: Optional[float] = None,
        bonus_amount: float = 0.0,
        organization_id: Optional[str] = None
    ) -> AgentTarget:
        """Ustaw cel sprzedażowy dla agenta"""
        # Sprawdź czy cel już istnieje
        existing = self.db.query(AgentTarget).filter(
            AgentTarget.agent_id == agent_id,
            AgentTarget.year == year,
            AgentTarget.month == month,
            AgentTarget.quarter == quarter
        ).first()
        
        if existing:
            existing.target_transactions = target_transactions
            existing.target_commission = target_commission
            existing.bonus_threshold = bonus_threshold
            existing.bonus_amount = bonus_amount
            self.db.commit()
            return existing
        
        target = AgentTarget(
            agent_id=agent_id,
            year=year,
            month=month,
            quarter=quarter,
            target_transactions=target_transactions,
            target_commission=target_commission,
            bonus_threshold=bonus_threshold,
            bonus_amount=bonus_amount,
            organization_id=organization_id
        )
        
        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        
        return target
    
    # ===== BONUSY =====
    
    async def award_bonus(
        self,
        agent_id: str,
        bonus_type: str,
        description: str,
        amount: float,
        organization_id: Optional[str] = None
    ) -> AgentBonus:
        """Przyznaj bonus agentowi"""
        bonus = AgentBonus(
            agent_id=agent_id,
            bonus_type=bonus_type,
            description=description,
            amount=amount,
            organization_id=organization_id
        )
        
        self.db.add(bonus)
        self.db.commit()
        self.db.refresh(bonus)
        
        logger.info(f"Bonus awarded to {agent_id}: {amount:,.2f} PLN - {description}")
        
        return bonus
    
    async def pay_bonus(
        self,
        bonus_id: uuid.UUID,
        paid_by: str
    ) -> Optional[AgentBonus]:
        """Wypłać bonus"""
        bonus = self.db.query(AgentBonus).filter(AgentBonus.id == bonus_id).first()
        if not bonus:
            return None
        
        bonus.status = "paid"
        bonus.paid_at = datetime.utcnow()
        
        self.db.commit()
        
        return bonus
    
    # ===== RAPORTY =====
    
    async def get_agent_performance(
        self,
        agent_id: str,
        year: int,
        month: Optional[int] = None
    ) -> AgentPerformance:
        """Pobierz wyniki agenta"""
        # Okres
        if month:
            period = f"{year}-{month:02d}"
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
        else:
            period = str(year)
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
        
        # Transakcje
        transactions = self.db.query(Transaction).filter(
            Transaction.listing_agent_id == agent_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date
        ).all()
        
        transactions_count = len(transactions)
        transactions_value = sum(t.sale_price for t in transactions)
        commission_earned = sum(t.commission_amount for t in transactions)
        commission_paid = sum(
            t.listing_agent_paid_amount + (t.selling_agent_paid_amount if t.selling_agent_id == agent_id else 0)
            for t in transactions
        )
        commission_pending = commission_earned - commission_paid
        
        # Cele
        target = self.db.query(AgentTarget).filter(
            AgentTarget.agent_id == agent_id,
            AgentTarget.year == year,
            AgentTarget.month == month
        ).first()
        
        target_transactions = target.target_transactions if target else 0
        target_commission = target.target_commission if target else 0
        
        target_achieved = (commission_earned / target_commission * 100) if target_commission > 0 else 0
        
        # Bonusy
        bonuses = self.db.query(AgentBonus).filter(
            AgentBonus.agent_id == agent_id,
            AgentBonus.earned_at >= start_date,
            AgentBonus.earned_at < end_date
        ).all()
        
        bonuses_earned = sum(b.amount for b in bonuses)
        bonuses_paid = sum(b.amount for b in bonuses if b.status == "paid")
        
        # Ranking (w biurze)
        # TODO: Implementacja rankingu
        
        return AgentPerformance(
            agent_id=agent_id,
            agent_name="",  # Pobierz z bazy
            period=period,
            transactions_count=transactions_count,
            transactions_value=transactions_value,
            commission_earned=commission_earned,
            commission_paid=commission_paid,
            commission_pending=commission_pending,
            target_transactions=target_transactions,
            target_commission=target_commission,
            target_achieved_percent=target_achieved,
            bonuses_earned=bonuses_earned,
            bonuses_paid=bonuses_paid,
            rank_in_office=0,
            total_agents=0
        )
    
    async def get_office_performance(
        self,
        organization_id: str,
        year: int,
        month: Optional[int] = None
    ) -> OfficePerformance:
        """Pobierz wyniki biura"""
        if month:
            period = f"{year}-{month:02d}"
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
        else:
            period = str(year)
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
        
        # Transakcje
        transactions = self.db.query(Transaction).filter(
            Transaction.organization_id == organization_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date
        ).all()
        
        total_transactions = len(transactions)
        total_sales_value = sum(t.sale_price for t in transactions)
        total_commission = sum(t.commission_amount for t in transactions)
        
        # Agenci
        agents = self.db.query(Transaction.listing_agent_id).filter(
            Transaction.organization_id == organization_id
        ).distinct().all()
        
        agent_count = len(agents)
        
        avg_transactions = total_transactions / agent_count if agent_count > 0 else 0
        avg_commission = total_commission / agent_count if agent_count > 0 else 0
        
        # Top agenci
        agent_commissions = {}
        for t in transactions:
            if t.listing_agent_id not in agent_commissions:
                agent_commissions[t.listing_agent_id] = 0
            agent_commissions[t.listing_agent_id] += t.commission_amount * t.listing_agent_share_percent / 100
        
        top_agents = sorted(
            [{'agent_id': k, 'commission': v} for k, v in agent_commissions.items()],
            key=lambda x: x['commission'],
            reverse=True
        )
        
        # Porównanie z poprzednim okresem
        # TODO: Implementacja
        
        return OfficePerformance(
            organization_id=organization_id,
            period=period,
            total_transactions=total_transactions,
            total_sales_value=total_sales_value,
            total_commission=total_commission,
            avg_transactions_per_agent=avg_transactions,
            avg_commission_per_agent=avg_commission,
            top_agents=top_agents,
            vs_last_period_percent=0.0
        )
    
    async def get_agent_dashboard_summary(
        self,
        agent_id: str,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Podsumowanie dla dashboardu agenta"""
        today = datetime.utcnow()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Ten miesiąc
        month_transactions = self.db.query(Transaction).filter(
            Transaction.listing_agent_id == agent_id,
            Transaction.transaction_date >= month_start
        ).all()
        
        month_commission = sum(t.commission_amount for t in month_transactions)
        
        # Ten rok
        year_transactions = self.db.query(Transaction).filter(
            Transaction.listing_agent_id == agent_id,
            Transaction.transaction_date >= year_start
        ).all()
        
        year_commission = sum(t.commission_amount for t in year_transactions)
        
        # Oczekujące wypłaty
        pending = self.db.query(Transaction).filter(
            Transaction.listing_agent_id == agent_id,
            Transaction.commission_status.in_([CommissionStatus.EARNED, CommissionStatus.INVOICED]),
            Transaction.listing_agent_paid == False
        ).all()
        
        pending_amount = sum(
            t.commission_amount * t.listing_agent_share_percent / 100
            for t in pending
        )
        
        # Cel miesięczny
        target = self.db.query(AgentTarget).filter(
            AgentTarget.agent_id == agent_id,
            AgentTarget.year == today.year,
            AgentTarget.month == today.month
        ).first()
        
        target_amount = target.target_commission if target else 0
        target_progress = (month_commission / target_amount * 100) if target_amount > 0 else 0
        
        return {
            'this_month': {
                'transactions': len(month_transactions),
                'commission': round(month_commission, 2),
                'target': round(target_amount, 2),
                'target_progress': round(target_progress, 1),
            },
            'this_year': {
                'transactions': len(year_transactions),
                'commission': round(year_commission, 2),
            },
            'pending_payout': {
                'amount': round(pending_amount, 2),
                'transactions': len(pending),
            },
            'next_payout_date': (today + timedelta(days=30)).strftime('%Y-%m-%d'),  # Wypłata miesięczna
        }
