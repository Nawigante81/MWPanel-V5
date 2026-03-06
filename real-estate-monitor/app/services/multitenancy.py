"""
Multi-tenant Architecture Service

Professional multi-tenant support for SaaS deployment.
Provides data isolation, tenant management, and resource quotas.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from contextvars import ContextVar

from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session, Query
from sqlalchemy.ext.declarative import declarative_base
import uuid

from app.core.logging import get_logger

logger = get_logger(__name__)

# Context variable for current tenant
tenant_context: ContextVar[Optional[str]] = ContextVar('tenant_context', default=None)


class TenantStatus(str, Enum):
    """Tenant account status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PlanType(str, Enum):
    """Subscription plan types"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


Base = declarative_base()


class Tenant(Base):
    """Tenant/Organization database model"""
    __tablename__ = 'tenants'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Contact info
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Address
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    
    # Subscription
    plan = Column(String(20), default=PlanType.FREE.value)
    status = Column(String(20), default=TenantStatus.TRIAL.value)
    
    # Billing
    billing_email = Column(String(255), nullable=True)
    billing_address = Column(Text, nullable=True)
    tax_id = Column(String(50), nullable=True)
    
    # Trial/subscription dates
    trial_started_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    subscription_started_at = Column(DateTime(timezone=True), nullable=True)
    subscription_ends_at = Column(DateTime(timezone=True), nullable=True)
    
    # Quotas and limits
    quotas = Column(JSONB, default=dict)  # Custom quotas override
    features = Column(JSONB, default=list)  # Enabled features
    
    # Branding
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), nullable=True)  # Hex color
    custom_domain = Column(String(255), nullable=True, unique=True)
    
    # Settings
    settings = Column(JSONB, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    
    __table_args__ = (
        Index('idx_tenants_status', 'status', 'plan'),
        Index('idx_tenants_custom_domain', 'custom_domain'),
    )


class TenantMember(Base):
    """Tenant membership (users belonging to tenant)"""
    __tablename__ = 'tenant_members'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)
    user_id = Column(String(100), ForeignKey('users.id'), nullable=False)
    
    # Role within tenant
    role = Column(String(50), default='member')  # owner, admin, manager, member
    
    # Permissions
    permissions = Column(JSONB, default=list)
    
    # Status
    is_active = Column(Boolean, default=True)
    invited_at = Column(DateTime(timezone=True), nullable=True)
    joined_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_tenant_members_tenant', 'tenant_id', 'is_active'),
        Index('idx_tenant_members_user', 'user_id'),
    )


@dataclass
class QuotaLimits:
    """Resource quota limits for a tenant"""
    max_users: int = 5
    max_searches: int = 10
    max_alerts: int = 5
    max_api_calls_per_day: int = 1000
    max_exports_per_month: int = 10
    max_webhooks: int = 3
    max_storage_mb: int = 100
    max_leads: int = 100
    
    # Feature flags
    enable_api_access: bool = False
    enable_webhooks: bool = False
    enable_exports: bool = False
    enable_advanced_analytics: bool = False
    enable_white_label: bool = False
    enable_sso: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'limits': {
                'max_users': self.max_users,
                'max_searches': self.max_searches,
                'max_alerts': self.max_alerts,
                'max_api_calls_per_day': self.max_api_calls_per_day,
                'max_exports_per_month': self.max_exports_per_month,
                'max_webhooks': self.max_webhooks,
                'max_storage_mb': self.max_storage_mb,
                'max_leads': self.max_leads,
            },
            'features': {
                'api_access': self.enable_api_access,
                'webhooks': self.enable_webhooks,
                'exports': self.enable_exports,
                'advanced_analytics': self.enable_advanced_analytics,
                'white_label': self.enable_white_label,
                'sso': self.enable_sso,
            }
        }


# Default quotas by plan
DEFAULT_QUOTAS = {
    PlanType.FREE: QuotaLimits(
        max_users=1,
        max_searches=3,
        max_alerts=1,
        max_api_calls_per_day=100,
        max_exports_per_month=1,
        max_webhooks=0,
        max_storage_mb=50,
        max_leads=20,
        enable_api_access=False,
        enable_webhooks=False,
        enable_exports=True,
        enable_advanced_analytics=False,
        enable_white_label=False,
        enable_sso=False,
    ),
    PlanType.STARTER: QuotaLimits(
        max_users=3,
        max_searches=10,
        max_alerts=5,
        max_api_calls_per_day=1000,
        max_exports_per_month=10,
        max_webhooks=2,
        max_storage_mb=500,
        max_leads=200,
        enable_api_access=True,
        enable_webhooks=True,
        enable_exports=True,
        enable_advanced_analytics=False,
        enable_white_label=False,
        enable_sso=False,
    ),
    PlanType.PROFESSIONAL: QuotaLimits(
        max_users=10,
        max_searches=50,
        max_alerts=20,
        max_api_calls_per_day=10000,
        max_exports_per_month=50,
        max_webhooks=10,
        max_storage_mb=5000,
        max_leads=1000,
        enable_api_access=True,
        enable_webhooks=True,
        enable_exports=True,
        enable_advanced_analytics=True,
        enable_white_label=False,
        enable_sso=False,
    ),
    PlanType.ENTERPRISE: QuotaLimits(
        max_users=100,
        max_searches=999999,
        max_alerts=999999,
        max_api_calls_per_day=100000,
        max_exports_per_month=999999,
        max_webhooks=100,
        max_storage_mb=50000,
        max_leads=10000,
        enable_api_access=True,
        enable_webhooks=True,
        enable_exports=True,
        enable_advanced_analytics=True,
        enable_white_label=True,
        enable_sso=True,
    ),
}


class TenantService:
    """
    Professional multi-tenant service.
    
    Features:
    - Tenant creation and management
    - Resource quota enforcement
    - Data isolation
    - Subscription management
    - Custom branding
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def create_tenant(
        self,
        name: str,
        slug: str,
        email: str,
        plan: PlanType = PlanType.FREE,
        **kwargs
    ) -> Tenant:
        """Create a new tenant"""
        # Check if slug exists
        existing = self.db.query(Tenant).filter(Tenant.slug == slug).first()
        if existing:
            raise ValueError(f"Tenant slug '{slug}' already exists")
        
        # Set trial dates
        trial_started_at = datetime.utcnow()
        trial_ends_at = trial_started_at + timedelta(days=14)  # 14-day trial
        
        tenant = Tenant(
            name=name,
            slug=slug,
            email=email,
            plan=plan.value,
            status=TenantStatus.TRIAL.value,
            trial_started_at=trial_started_at,
            trial_ends_at=trial_ends_at,
            quotas=kwargs.get('quotas', {}),
            features=kwargs.get('features', []),
            settings=kwargs.get('settings', {}),
        )
        
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        
        logger.info(f"Created tenant '{name}' (ID: {tenant.id})")
        
        return tenant
    
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug"""
        return self.db.query(Tenant).filter(Tenant.slug == slug).first()
    
    async def get_tenant_by_domain(self, domain: str) -> Optional[Tenant]:
        """Get tenant by custom domain"""
        return self.db.query(Tenant).filter(Tenant.custom_domain == domain).first()
    
    async def update_tenant(
        self,
        tenant_id: str,
        **kwargs
    ) -> Optional[Tenant]:
        """Update tenant information"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        for key, value in kwargs.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)
        
        tenant.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(tenant)
        
        return tenant
    
    async def get_quotas(self, tenant_id: str) -> QuotaLimits:
        """Get effective quotas for a tenant"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return QuotaLimits()
        
        # Get base quotas for plan
        plan = PlanType(tenant.plan)
        base_quotas = DEFAULT_QUOTAS.get(plan, DEFAULT_QUOTAS[PlanType.FREE])
        
        # Apply custom overrides
        custom_quotas = tenant.quotas or {}
        
        for key, value in custom_quotas.items():
            if hasattr(base_quotas, key):
                setattr(base_quotas, key, value)
        
        return base_quotas
    
    async def check_quota(
        self,
        tenant_id: str,
        resource: str,
        current_usage: int = 0
    ) -> tuple[bool, int, int]:
        """
        Check if tenant is within quota for a resource.
        
        Returns:
            Tuple of (within_quota, current_usage, limit)
        """
        quotas = await self.get_quotas(tenant_id)
        
        limit = getattr(quotas, f'max_{resource}', 0)
        
        return current_usage < limit, current_usage, limit
    
    async def get_usage_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get current usage statistics for a tenant"""
        from app.db.models import User, Search, Offer, Lead
        
        # Count resources
        user_count = self.db.query(User).filter(
            User.organization_id == tenant_id
        ).count()
        
        search_count = self.db.query(Search).filter(
            Search.organization_id == tenant_id
        ).count()
        
        offer_count = self.db.query(Offer).filter(
            Offer.organization_id == tenant_id
        ).count()
        
        lead_count = self.db.query(Lead).filter(
            Lead.organization_id == tenant_id
        ).count()
        
        quotas = await self.get_quotas(tenant_id)
        
        return {
            'users': {
                'current': user_count,
                'limit': quotas.max_users,
                'percentage': (user_count / quotas.max_users * 100) if quotas.max_users > 0 else 0,
            },
            'searches': {
                'current': search_count,
                'limit': quotas.max_searches,
                'percentage': (search_count / quotas.max_searches * 100) if quotas.max_searches > 0 else 0,
            },
            'offers': {
                'current': offer_count,
                'limit': None,  # Unlimited
            },
            'leads': {
                'current': lead_count,
                'limit': quotas.max_leads,
                'percentage': (lead_count / quotas.max_leads * 100) if quotas.max_leads > 0 else 0,
            },
        }
    
    async def add_member(
        self,
        tenant_id: str,
        user_id: str,
        role: str = 'member',
        permissions: Optional[List[str]] = None
    ) -> TenantMember:
        """Add a user to a tenant"""
        # Check quota
        current_members = self.db.query(TenantMember).filter(
            TenantMember.tenant_id == tenant_id,
            TenantMember.is_active == True
        ).count()
        
        quotas = await self.get_quotas(tenant_id)
        if current_members >= quotas.max_users:
            raise ValueError("User quota exceeded for this tenant")
        
        member = TenantMember(
            tenant_id=uuid.UUID(tenant_id),
            user_id=user_id,
            role=role,
            permissions=permissions or [],
        )
        
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        
        return member
    
    async def remove_member(
        self,
        tenant_id: str,
        user_id: str
    ) -> bool:
        """Remove a user from a tenant"""
        member = self.db.query(TenantMember).filter(
            TenantMember.tenant_id == tenant_id,
            TenantMember.user_id == user_id
        ).first()
        
        if not member:
            return False
        
        member.is_active = False
        self.db.commit()
        
        return True
    
    async def upgrade_plan(
        self,
        tenant_id: str,
        new_plan: PlanType
    ) -> Optional[Tenant]:
        """Upgrade tenant to a new plan"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        old_plan = tenant.plan
        tenant.plan = new_plan.value
        tenant.status = TenantStatus.ACTIVE.value
        tenant.subscription_started_at = datetime.utcnow()
        
        # Set subscription end (monthly billing)
        tenant.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
        
        self.db.commit()
        
        logger.info(f"Tenant {tenant_id} upgraded from {old_plan} to {new_plan.value}")
        
        return tenant
    
    async def suspend_tenant(
        self,
        tenant_id: str,
        reason: str
    ) -> Optional[Tenant]:
        """Suspend a tenant account"""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None
        
        tenant.status = TenantStatus.SUSPENDED.value
        tenant.settings['suspension_reason'] = reason
        tenant.settings['suspended_at'] = datetime.utcnow().isoformat()
        
        self.db.commit()
        
        logger.warning(f"Tenant {tenant_id} suspended: {reason}")
        
        return tenant


class TenantMiddleware:
    """Middleware for handling tenant context in requests"""
    
    def __init__(self, tenant_service: TenantService):
        self.tenant_service = tenant_service
    
    async def set_tenant_from_request(self, request):
        """Set tenant context from request"""
        # Try to get tenant from header
        tenant_slug = request.headers.get('X-Tenant-Slug')
        
        if tenant_slug:
            tenant = await self.tenant_service.get_tenant_by_slug(tenant_slug)
            if tenant:
                tenant_context.set(str(tenant.id))
                return
        
        # Try to get from custom domain
        host = request.headers.get('Host', '')
        tenant = await self.tenant_service.get_tenant_by_domain(host)
        if tenant:
            tenant_context.set(str(tenant.id))
            return
        
        # Try to get from user
        if hasattr(request, 'user') and request.user:
            if request.user.organization_id:
                tenant_context.set(request.user.organization_id)
                return
        
        # No tenant identified
        tenant_context.set(None)
    
    def get_current_tenant_id(self) -> Optional[str]:
        """Get current tenant ID from context"""
        return tenant_context.get()


def with_tenant_scope(query: Query, tenant_id_column: str = 'organization_id') -> Query:
    """
    Apply tenant scope to a query.
    
    Usage:
        query = db.query(Offer)
        query = with_tenant_scope(query)
    """
    tenant_id = tenant_context.get()
    if tenant_id:
        return query.filter(getattr(query.column_descriptions[0]['type'], tenant_id_column) == tenant_id)
    return query


# Decorator for tenant-aware functions

def tenant_aware(func):
    """Decorator to make a function tenant-aware"""
    async def wrapper(*args, **kwargs):
        tenant_id = kwargs.get('organization_id') or tenant_context.get()
        if tenant_id:
            tenant_context.set(tenant_id)
        return await func(*args, **kwargs)
    return wrapper


# Convenience functions

async def create_default_tenant(db_session: Session, admin_email: str) -> Tenant:
    """Create default tenant for single-tenant deployment"""
    service = TenantService(db_session)
    
    return await service.create_tenant(
        name="Default Organization",
        slug="default",
        email=admin_email,
        plan=PlanType.ENTERPRISE
    )
