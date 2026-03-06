"""
Lead Management System

Professional CRM functionality for tracking potential clients,
managing sales pipeline, and converting leads to customers.
Designed for real estate agents and professionals.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import uuid

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, 
    Integer, Float, Enum as SQLEnum, Boolean, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session
from sqlalchemy import func

from app.db.base import Base
from app.core.logging import get_logger
from app.services.audit_logger import AuditLogger, AuditAction, AuditContext

logger = get_logger(__name__)


class LeadStatus(str, Enum):
    """Lead status in sales pipeline"""
    NEW = "new"                    # New lead, not yet contacted
    CONTACTED = "contacted"        # Initial contact made
    QUALIFIED = "qualified"        # Qualified as potential buyer
    VIEWING_SCHEDULED = "viewing_scheduled"  # Property viewing scheduled
    VIEWING_COMPLETED = "viewing_completed"  # Viewing completed
    OFFER_MADE = "offer_made"      # Offer submitted
    NEGOTIATING = "negotiating"    # In negotiation
    CLOSED_WON = "closed_won"      # Deal closed successfully
    CLOSED_LOST = "closed_lost"    # Deal lost
    ON_HOLD = "on_hold"            # Temporarily on hold
    DISQUALIFIED = "disqualified"  # Not a viable lead


class LeadSource(str, Enum):
    """Source of the lead"""
    WEBSITE = "website"
    REFERRAL = "referral"
    SOCIAL_MEDIA = "social_media"
    PORTAL_OTODOM = "portal_otodom"
    PORTAL_OLX = "portal_olx"
    PORTAL_ALLEGRO = "portal_allegro"
    FACEBOOK = "facebook"
    GOOGLE_ADS = "google_ads"
    WALK_IN = "walk_in"
    PHONE_INQUIRY = "phone_inquiry"
    EMAIL_INQUIRY = "email_inquiry"
    EVENT = "event"
    PARTNER = "partner"
    OTHER = "other"


class LeadPriority(str, Enum):
    """Lead priority level"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    HOT = 4


class ContactMethod(str, Enum):
    """Preferred contact method"""
    PHONE = "phone"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    IN_PERSON = "in_person"


class Lead(Base):
    """Lead database model"""
    __tablename__ = 'leads'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Basic information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    
    # Status and source
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW, index=True)
    source = Column(SQLEnum(LeadSource), nullable=False)
    priority = Column(SQLEnum(LeadPriority), default=LeadPriority.MEDIUM)
    
    # Assignment
    assigned_agent_id = Column(String(100), ForeignKey('users.id'), nullable=True)
    assigned_agent = relationship("User", back_populates="leads")
    
    # Requirements
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    preferred_location = Column(String(255), nullable=True)
    property_type = Column(String(50), nullable=True)
    min_rooms = Column(Integer, nullable=True)
    max_rooms = Column(Integer, nullable=True)
    min_area = Column(Float, nullable=True)
    max_area = Column(Float, nullable=True)
    requirements_notes = Column(Text, nullable=True)
    
    # Contact preferences
    preferred_contact_method = Column(SQLEnum(ContactMethod), default=ContactMethod.PHONE)
    best_time_to_contact = Column(String(50), nullable=True)
    
    # Timeline
    desired_move_in_date = Column(DateTime(timezone=True), nullable=True)
    urgency_level = Column(String(20), nullable=True)  # immediate, 1_month, 3_months, flexible
    
    # Scoring and qualification
    score = Column(Integer, default=0)  # 0-100 lead score
    qualification_data = Column(JSONB, default=dict)
    
    # Related offers
    interested_offers = Column(JSONB, default=list)  # List of offer IDs
    
    # Communication history
    last_contact_date = Column(DateTime(timezone=True), nullable=True)
    next_follow_up_date = Column(DateTime(timezone=True), nullable=True)
    contact_count = Column(Integer, default=0)
    
    # Organization
    organization_id = Column(String(100), nullable=True, index=True)
    
    # Tags and metadata
    tags = Column(JSONB, default=list)
    custom_fields = Column(JSONB, default=dict)
    
    # Conversion tracking
    converted_at = Column(DateTime(timezone=True), nullable=True)
    converted_offer_id = Column(String(100), nullable=True)
    conversion_value = Column(Float, nullable=True)
    
    # GDPR consent
    marketing_consent = Column(Boolean, default=False)
    marketing_consent_date = Column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index('idx_leads_status_agent', 'status', 'assigned_agent_id'),
        Index('idx_leads_org_status', 'organization_id', 'status'),
        Index('idx_leads_follow_up', 'next_follow_up_date'),
        Index('idx_leads_score', 'score'),
    )


class LeadActivity(Base):
    """Activity log for lead interactions"""
    __tablename__ = 'lead_activities'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=False)
    lead = relationship("Lead", backref="activities")
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(String(100), nullable=False)
    
    activity_type = Column(String(50), nullable=False)  # call, email, meeting, note, status_change
    description = Column(Text, nullable=False)
    
    # For calls/meetings
    duration_minutes = Column(Integer, nullable=True)
    outcome = Column(String(50), nullable=True)  # positive, neutral, negative, no_answer
    
    # Follow-up
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(DateTime(timezone=True), nullable=True)
    
    # Related offer
    related_offer_id = Column(String(100), nullable=True)
    
    # Metadata
    metadata = Column(JSONB, default=dict)


class LeadNote(Base):
    """Notes attached to leads"""
    __tablename__ = 'lead_notes'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=False)
    lead = relationship("Lead", backref="notes")
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=False)
    
    content = Column(Text, nullable=False)
    is_private = Column(Boolean, default=False)  # Only visible to creator
    
    # Categorization
    category = Column(String(50), nullable=True)  # general, financial, preferences, concerns


@dataclass
class LeadScoreFactors:
    """Factors used to calculate lead score"""
    budget_clarity: int = 0  # 0-20
    timeline_urgency: int = 0  # 0-20
    contact_responsiveness: int = 0  # 0-20
    requirements_specificity: int = 0  # 0-20
    engagement_level: int = 0  # 0-20
    
    def total(self) -> int:
        return min(100, sum([
            self.budget_clarity,
            self.timeline_urgency,
            self.contact_responsiveness,
            self.requirements_specificity,
            self.engagement_level
        ]))


class LeadManagementService:
    """
    Professional lead management service.
    
    Features:
    - Complete sales pipeline management
    - Lead scoring and qualification
    - Activity tracking
    - Automated follow-up reminders
    - Conversion analytics
    """
    
    def __init__(self, db_session: Session, audit_logger: Optional[AuditLogger] = None):
        self.db = db_session
        self.audit_logger = audit_logger
        
    # Lead CRUD Operations
    
    async def create_lead(
        self,
        first_name: str,
        last_name: str,
        source: LeadSource,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        assigned_agent_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        **kwargs
    ) -> Lead:
        """Create a new lead"""
        lead = Lead(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            source=source,
            assigned_agent_id=assigned_agent_id,
            organization_id=organization_id,
            **kwargs
        )
        
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        
        # Log activity
        await self._log_activity(
            lead_id=lead.id,
            activity_type='lead_created',
            description=f"Lead created from {source.value}",
            created_by=assigned_agent_id or 'system'
        )
        
        # Audit log
        if self.audit_logger:
            await self.audit_logger.log(
                action=AuditAction.LEAD_CREATED,
                resource_type='lead',
                resource_id=str(lead.id),
                new_values={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'source': source.value
                }
            )
        
        logger.info(f"Created lead {lead.id} for {first_name} {last_name}")
        return lead
    
    async def get_lead(self, lead_id: uuid.UUID) -> Optional[Lead]:
        """Get a lead by ID"""
        return self.db.query(Lead).filter(Lead.id == lead_id).first()
    
    async def update_lead(
        self,
        lead_id: uuid.UUID,
        updated_by: str,
        **kwargs
    ) -> Optional[Lead]:
        """Update lead information"""
        lead = await self.get_lead(lead_id)
        if not lead:
            return None
        
        # Track old values for audit
        old_values = {
            k: getattr(lead, k) for k in kwargs.keys()
            if hasattr(lead, k)
        }
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(lead, key):
                setattr(lead, key, value)
        
        lead.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(lead)
        
        # Log activity
        await self._log_activity(
            lead_id=lead.id,
            activity_type='lead_updated',
            description=f"Lead information updated",
            created_by=updated_by
        )
        
        # Audit log
        if self.audit_logger:
            await self.audit_logger.log(
                action=AuditAction.LEAD_UPDATED,
                resource_type='lead',
                resource_id=str(lead.id),
                old_values=old_values,
                new_values=kwargs
            )
        
        return lead
    
    async def change_status(
        self,
        lead_id: uuid.UUID,
        new_status: LeadStatus,
        changed_by: str,
        notes: Optional[str] = None
    ) -> Optional[Lead]:
        """Change lead status in pipeline"""
        lead = await self.get_lead(lead_id)
        if not lead:
            return None
        
        old_status = lead.status
        lead.status = new_status
        lead.updated_at = datetime.utcnow()
        
        # Track conversion
        if new_status == LeadStatus.CLOSED_WON:
            lead.converted_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(lead)
        
        # Log activity
        description = f"Status changed from {old_status.value} to {new_status.value}"
        if notes:
            description += f": {notes}"
        
        await self._log_activity(
            lead_id=lead.id,
            activity_type='status_change',
            description=description,
            created_by=changed_by
        )
        
        # Audit log
        if self.audit_logger:
            await self.audit_logger.log(
                action=AuditAction.LEAD_UPDATED,
                resource_type='lead',
                resource_id=str(lead.id),
                old_values={'status': old_status.value},
                new_values={'status': new_status.value}
            )
        
        logger.info(f"Lead {lead_id} status: {old_status.value} -> {new_status.value}")
        return lead
    
    async def delete_lead(self, lead_id: uuid.UUID, deleted_by: str) -> bool:
        """Soft delete a lead (or hard delete if needed)"""
        lead = await self.get_lead(lead_id)
        if not lead:
            return False
        
        # Soft delete by changing status
        lead.status = LeadStatus.DISQUALIFIED
        lead.updated_at = datetime.utcnow()
        
        # Add deletion note
        await self._log_activity(
            lead_id=lead.id,
            activity_type='lead_deleted',
            description=f"Lead deleted by {deleted_by}",
            created_by=deleted_by
        )
        
        self.db.commit()
        
        logger.info(f"Lead {lead_id} deleted by {deleted_by}")
        return True
    
    # Lead Scoring
    
    async def calculate_lead_score(self, lead_id: uuid.UUID) -> int:
        """Calculate lead score based on various factors"""
        lead = await self.get_lead(lead_id)
        if not lead:
            return 0
        
        factors = LeadScoreFactors()
        
        # Budget clarity (0-20)
        if lead.budget_min and lead.budget_max:
            factors.budget_clarity = 20
        elif lead.budget_max:
            factors.budget_clarity = 15
        elif lead.budget_min:
            factors.budget_clarity = 10
        
        # Timeline urgency (0-20)
        if lead.urgency_level == 'immediate':
            factors.timeline_urgency = 20
        elif lead.urgency_level == '1_month':
            factors.timeline_urgency = 15
        elif lead.urgency_level == '3_months':
            factors.timeline_urgency = 10
        
        # Contact responsiveness (0-20)
        if lead.contact_count > 5:
            factors.contact_responsiveness = 20
        elif lead.contact_count > 2:
            factors.contact_responsiveness = 15
        elif lead.contact_count > 0:
            factors.contact_responsiveness = 10
        
        # Requirements specificity (0-20)
        specific_fields = [
            lead.preferred_location,
            lead.property_type,
            lead.min_rooms,
            lead.min_area
        ]
        filled_fields = sum(1 for f in specific_fields if f is not None)
        factors.requirements_specificity = min(20, filled_fields * 5)
        
        # Engagement level (0-20)
        if lead.interested_offers:
            factors.engagement_level = min(20, len(lead.interested_offers) * 5)
        
        # Calculate total score
        score = factors.total()
        
        # Update lead score
        lead.score = score
        lead.qualification_data = {
            'factors': {
                'budget_clarity': factors.budget_clarity,
                'timeline_urgency': factors.timeline_urgency,
                'contact_responsiveness': factors.contact_responsiveness,
                'requirements_specificity': factors.requirements_specificity,
                'engagement_level': factors.engagement_level,
            },
            'calculated_at': datetime.utcnow().isoformat()
        }
        
        self.db.commit()
        
        return score
    
    # Activity Management
    
    async def _log_activity(
        self,
        lead_id: uuid.UUID,
        activity_type: str,
        description: str,
        created_by: str,
        **kwargs
    ) -> LeadActivity:
        """Log an activity for a lead"""
        activity = LeadActivity(
            lead_id=lead_id,
            activity_type=activity_type,
            description=description,
            created_by=created_by,
            **kwargs
        )
        
        self.db.add(activity)
        self.db.commit()
        
        # Update lead's last contact date
        lead = await self.get_lead(lead_id)
        if lead:
            lead.last_contact_date = datetime.utcnow()
            lead.contact_count += 1
            self.db.commit()
        
        return activity
    
    async def add_activity(
        self,
        lead_id: uuid.UUID,
        activity_type: str,
        description: str,
        created_by: str,
        duration_minutes: Optional[int] = None,
        outcome: Optional[str] = None,
        follow_up_required: bool = False,
        follow_up_date: Optional[datetime] = None,
        related_offer_id: Optional[str] = None
    ) -> LeadActivity:
        """Add an activity to a lead"""
        return await self._log_activity(
            lead_id=lead_id,
            activity_type=activity_type,
            description=description,
            created_by=created_by,
            duration_minutes=duration_minutes,
            outcome=outcome,
            follow_up_required=follow_up_required,
            follow_up_date=follow_up_date,
            related_offer_id=related_offer_id
        )
    
    async def add_note(
        self,
        lead_id: uuid.UUID,
        content: str,
        created_by: str,
        category: Optional[str] = None,
        is_private: bool = False
    ) -> LeadNote:
        """Add a note to a lead"""
        note = LeadNote(
            lead_id=lead_id,
            content=content,
            created_by=created_by,
            category=category,
            is_private=is_private
        )
        
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        
        return note
    
    # Query and Search
    
    async def search_leads(
        self,
        organization_id: Optional[str] = None,
        status: Optional[LeadStatus] = None,
        assigned_agent_id: Optional[str] = None,
        source: Optional[LeadSource] = None,
        priority: Optional[LeadPriority] = None,
        min_score: Optional[int] = None,
        tags: Optional[List[str]] = None,
        search_query: Optional[str] = None,
        follow_up_due: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Lead]:
        """Search and filter leads"""
        query = self.db.query(Lead)
        
        if organization_id:
            query = query.filter(Lead.organization_id == organization_id)
        if status:
            query = query.filter(Lead.status == status)
        if assigned_agent_id:
            query = query.filter(Lead.assigned_agent_id == assigned_agent_id)
        if source:
            query = query.filter(Lead.source == source)
        if priority:
            query = query.filter(Lead.priority == priority)
        if min_score:
            query = query.filter(Lead.score >= min_score)
        if tags:
            query = query.filter(Lead.tags.contains(tags))
        if follow_up_due:
            query = query.filter(
                Lead.next_follow_up_date <= datetime.utcnow()
            )
        
        if search_query:
            search_filter = f"%{search_query}%"
            query = query.filter(
                (Lead.first_name.ilike(search_filter)) |
                (Lead.last_name.ilike(search_filter)) |
                (Lead.email.ilike(search_filter)) |
                (Lead.phone.ilike(search_filter))
            )
        
        return query.order_by(Lead.score.desc()).offset(offset).limit(limit).all()
    
    async def get_pipeline_stats(
        self,
        organization_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get pipeline statistics"""
        query = self.db.query(Lead)
        
        if organization_id:
            query = query.filter(Lead.organization_id == organization_id)
        if agent_id:
            query = query.filter(Lead.assigned_agent_id == agent_id)
        
        # Status counts
        status_counts = query.with_entities(
            Lead.status,
            func.count(Lead.id)
        ).group_by(Lead.status).all()
        
        # Total leads
        total_leads = query.count()
        
        # New leads this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        new_this_month = query.filter(Lead.created_at >= month_start).count()
        
        # Converted leads
        converted = query.filter(Lead.status == LeadStatus.CLOSED_WON).count()
        
        # Conversion rate
        conversion_rate = (converted / total_leads * 100) if total_leads > 0 else 0
        
        # Average deal value
        avg_deal_value = query.filter(
            Lead.conversion_value.isnot(None)
        ).with_entities(
            func.avg(Lead.conversion_value)
        ).scalar() or 0
        
        # Follow-ups due
        follow_ups_due = query.filter(
            Lead.next_follow_up_date <= datetime.utcnow()
        ).count()
        
        return {
            'total_leads': total_leads,
            'new_this_month': new_this_month,
            'converted': converted,
            'conversion_rate': round(conversion_rate, 2),
            'avg_deal_value': round(avg_deal_value, 2),
            'follow_ups_due': follow_ups_due,
            'status_breakdown': {
                status.value: count for status, count in status_counts
            }
        }
    
    async def get_follow_up_reminders(
        self,
        agent_id: str,
        days_ahead: int = 7
    ) -> List[Lead]:
        """Get leads requiring follow-up"""
        end_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        return self.db.query(Lead).filter(
            Lead.assigned_agent_id == agent_id,
            Lead.next_follow_up_date <= end_date,
            Lead.status.notin_([
                LeadStatus.CLOSED_WON,
                LeadStatus.CLOSED_LOST,
                LeadStatus.DISQUALIFIED
            ])
        ).order_by(Lead.next_follow_up_date).all()
    
    # Lead Assignment
    
    async def assign_lead(
        self,
        lead_id: uuid.UUID,
        agent_id: str,
        assigned_by: str
    ) -> Optional[Lead]:
        """Assign lead to an agent"""
        lead = await self.get_lead(lead_id)
        if not lead:
            return None
        
        old_agent = lead.assigned_agent_id
        lead.assigned_agent_id = agent_id
        lead.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        await self._log_activity(
            lead_id=lead.id,
            activity_type='lead_assigned',
            description=f"Lead assigned from {old_agent or 'unassigned'} to {agent_id}",
            created_by=assigned_by
        )
        
        return lead
    
    async def auto_assign_lead(
        self,
        lead_id: uuid.UUID,
        organization_id: str
    ) -> Optional[Lead]:
        """Auto-assign lead to least busy agent"""
        # Find agent with fewest active leads
        from sqlalchemy import func
        
        agent_loads = self.db.query(
            Lead.assigned_agent_id,
            func.count(Lead.id).label('lead_count')
        ).filter(
            Lead.organization_id == organization_id,
            Lead.status.notin_([
                LeadStatus.CLOSED_WON,
                LeadStatus.CLOSED_LOST,
                LeadStatus.DISQUALIFIED
            ])
        ).group_by(Lead.assigned_agent_id).all()
        
        if not agent_loads:
            return None
        
        # Get agent with minimum load
        best_agent = min(agent_loads, key=lambda x: x[1])
        
        return await self.assign_lead(
            lead_id=lead_id,
            agent_id=best_agent[0],
            assigned_by='system'
        )
