"""
API Keys Management Service

Professional API key management with usage tracking,
rate limiting, and access control.
"""

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field

from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.declarative import declarative_base
import uuid

from app.core.logging import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class APIKeyScope(str, Enum):
    """Available API scopes/permissions"""
    READ_OFFERS = "read:offers"
    WRITE_OFFERS = "write:offers"
    READ_SEARCHES = "read:searches"
    WRITE_SEARCHES = "write:searches"
    READ_LEADS = "read:leads"
    WRITE_LEADS = "write:leads"
    READ_ANALYTICS = "read:analytics"
    READ_EXPORTS = "read:exports"
    WEBHOOKS = "webhooks"
    ADMIN = "admin"


class APIKeyStatus(str, Enum):
    """API key status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class APIKey(Base):
    """API Key database model"""
    __tablename__ = 'api_keys'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Key identification
    key_prefix = Column(String(16), nullable=False, index=True)
    key_hash = Column(String(64), nullable=False, unique=True)
    
    # Ownership
    user_id = Column(String(100), ForeignKey('users.id'), nullable=False)
    organization_id = Column(String(100), nullable=True, index=True)
    
    # Metadata
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    
    # Scopes and permissions
    scopes = Column(JSONB, default=list)
    allowed_ips = Column(JSONB, nullable=True)  # IP whitelist
    allowed_origins = Column(JSONB, nullable=True)  # CORS origins
    
    # Status and dates
    status = Column(String(20), default=APIKeyStatus.ACTIVE.value)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(255), nullable=True)
    
    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)
    
    # Usage tracking
    total_requests = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_api_keys_user', 'user_id', 'status'),
        Index('idx_api_keys_org', 'organization_id', 'status'),
    )


class APIKeyUsage(Base):
    """API key usage log"""
    __tablename__ = 'api_key_usage'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey('api_keys.id'), nullable=False)
    
    # Request details
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    
    # Response details
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Client info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Request metadata
    request_size_bytes = Column(Integer, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)
    
    # Error tracking
    error_message = Column(String(500), nullable=True)
    
    __table_args__ = (
        Index('idx_api_usage_key_time', 'api_key_id', 'timestamp'),
        Index('idx_api_usage_endpoint', 'endpoint', 'timestamp'),
    )


@dataclass
class APIKeyCredentials:
    """API key credentials (shown only once at creation)"""
    key_id: str
    api_key: str  # Full API key (only shown once)
    name: str
    scopes: List[str]
    expires_at: Optional[datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'key_id': self.key_id,
            'api_key': self.api_key,  # Only shown once!
            'name': self.name,
            'scopes': self.scopes,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'warning': 'This API key will only be shown once. Store it securely!'
        }


@dataclass
class APIKeyInfo:
    """Public API key information"""
    key_id: str
    name: str
    description: Optional[str]
    scopes: List[str]
    status: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    total_requests: int
    rate_limits: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'key_id': self.key_id,
            'name': self.name,
            'description': self.description,
            'scopes': self.scopes,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'total_requests': self.total_requests,
            'rate_limits': self.rate_limits,
        }


@dataclass
class UsageStatistics:
    """API usage statistics"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time_ms: float
    requests_by_endpoint: Dict[str, int]
    requests_by_day: Dict[str, int]
    error_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'average_response_time_ms': round(self.average_response_time_ms, 2),
            'requests_by_endpoint': self.requests_by_endpoint,
            'requests_by_day': self.requests_by_day,
            'error_rate': round(self.error_rate, 2),
        }


class APIKeyService:
    """
    Professional API key management service.
    
    Features:
    - Secure key generation and storage
    - Granular scope-based permissions
    - Usage tracking and analytics
    - Rate limiting per key
    - IP and origin restrictions
    """
    
    # Key format: rem_<prefix>_<secret>
    KEY_PREFIX = "rem"
    KEY_LENGTH = 48  # Total key length
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    def _generate_api_key(self) -> tuple[str, str]:
        """Generate a new API key and its hash"""
        # Generate random secret
        secret = secrets.token_urlsafe(32)
        
        # Create prefix for identification
        prefix = secrets.token_hex(8)[:8]
        
        # Full key
        api_key = f"{self.KEY_PREFIX}_{prefix}_{secret}"
        
        # Hash for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        return api_key, key_hash, prefix
    
    async def create_key(
        self,
        user_id: str,
        name: str,
        scopes: List[APIKeyScope],
        organization_id: Optional[str] = None,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        rate_limits: Optional[Dict[str, int]] = None,
        allowed_ips: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None
    ) -> APIKeyCredentials:
        """
        Create a new API key.
        
        Args:
            user_id: Owner user ID
            name: Key name/description
            scopes: List of permission scopes
            organization_id: Optional organization ID
            description: Optional detailed description
            expires_in_days: Optional expiration in days
            rate_limits: Optional custom rate limits
            allowed_ips: Optional IP whitelist
            allowed_origins: Optional CORS origins
            
        Returns:
            APIKeyCredentials with the full key (shown only once)
        """
        # Generate key
        api_key, key_hash, prefix = self._generate_api_key()
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create database record
        db_key = APIKey(
            key_prefix=prefix,
            key_hash=key_hash,
            user_id=user_id,
            organization_id=organization_id,
            name=name,
            description=description,
            scopes=[s.value for s in scopes],
            expires_at=expires_at,
            allowed_ips=allowed_ips,
            allowed_origins=allowed_origins,
        )
        
        # Apply custom rate limits
        if rate_limits:
            db_key.rate_limit_per_minute = rate_limits.get('per_minute', 60)
            db_key.rate_limit_per_hour = rate_limits.get('per_hour', 1000)
            db_key.rate_limit_per_day = rate_limits.get('per_day', 10000)
        
        self.db.add(db_key)
        self.db.commit()
        self.db.refresh(db_key)
        
        logger.info(f"Created API key {db_key.id} for user {user_id}")
        
        return APIKeyCredentials(
            key_id=str(db_key.id),
            api_key=api_key,  # Only returned once!
            name=name,
            scopes=[s.value for s in scopes],
            expires_at=expires_at
        )
    
    async def validate_key(self, api_key: str) -> Optional[APIKey]:
        """
        Validate an API key.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            APIKey if valid, None otherwise
        """
        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Find in database
        db_key = self.db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.status == APIKeyStatus.ACTIVE.value
        ).first()
        
        if not db_key:
            return None
        
        # Check expiration
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            db_key.status = APIKeyStatus.EXPIRED.value
            self.db.commit()
            return None
        
        # Update last used
        db_key.last_used_at = datetime.utcnow()
        db_key.total_requests += 1
        self.db.commit()
        
        return db_key
    
    async def revoke_key(
        self,
        key_id: str,
        revoked_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """Revoke an API key"""
        db_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        
        if not db_key:
            return False
        
        db_key.status = APIKeyStatus.REVOKED.value
        db_key.revoked_at = datetime.utcnow()
        db_key.revoked_reason = reason or f"Revoked by {revoked_by}"
        
        self.db.commit()
        
        logger.info(f"Revoked API key {key_id} by {revoked_by}")
        return True
    
    async def get_key_info(self, key_id: str) -> Optional[APIKeyInfo]:
        """Get public information about an API key"""
        db_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        
        if not db_key:
            return None
        
        return APIKeyInfo(
            key_id=str(db_key.id),
            name=db_key.name,
            description=db_key.description,
            scopes=db_key.scopes,
            status=db_key.status,
            created_at=db_key.created_at,
            expires_at=db_key.expires_at,
            last_used_at=db_key.last_used_at,
            total_requests=db_key.total_requests,
            rate_limits={
                'per_minute': db_key.rate_limit_per_minute,
                'per_hour': db_key.rate_limit_per_hour,
                'per_day': db_key.rate_limit_per_day,
            }
        )
    
    async def list_keys(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        status: Optional[APIKeyStatus] = None
    ) -> List[APIKeyInfo]:
        """List API keys with filters"""
        query = self.db.query(APIKey)
        
        if user_id:
            query = query.filter(APIKey.user_id == user_id)
        if organization_id:
            query = query.filter(APIKey.organization_id == organization_id)
        if status:
            query = query.filter(APIKey.status == status.value)
        
        db_keys = query.order_by(APIKey.created_at.desc()).all()
        
        return [
            APIKeyInfo(
                key_id=str(k.id),
                name=k.name,
                description=k.description,
                scopes=k.scopes,
                status=k.status,
                created_at=k.created_at,
                expires_at=k.expires_at,
                last_used_at=k.last_used_at,
                total_requests=k.total_requests,
                rate_limits={
                    'per_minute': k.rate_limit_per_minute,
                    'per_hour': k.rate_limit_per_hour,
                    'per_day': k.rate_limit_per_day,
                }
            )
            for k in db_keys
        ]
    
    async def log_usage(
        self,
        api_key_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Log API key usage"""
        usage = APIKeyUsage(
            api_key_id=uuid.UUID(api_key_id),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message
        )
        
        self.db.add(usage)
        self.db.commit()
    
    async def get_usage_stats(
        self,
        key_id: str,
        days: int = 30
    ) -> UsageStatistics:
        """Get usage statistics for an API key"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        usage_records = self.db.query(APIKeyUsage).filter(
            APIKeyUsage.api_key_id == key_id,
            APIKeyUsage.timestamp >= start_date
        ).all()
        
        if not usage_records:
            return UsageStatistics(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                average_response_time_ms=0,
                requests_by_endpoint={},
                requests_by_day={},
                error_rate=0
            )
        
        total = len(usage_records)
        successful = sum(1 for r in usage_records if r.status_code and r.status_code < 400)
        failed = total - successful
        
        response_times = [r.response_time_ms for r in usage_records if r.response_time_ms]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # By endpoint
        endpoint_counts = {}
        for r in usage_records:
            endpoint_counts[r.endpoint] = endpoint_counts.get(r.endpoint, 0) + 1
        
        # By day
        day_counts = {}
        for r in usage_records:
            day = r.timestamp.strftime('%Y-%m-%d')
            day_counts[day] = day_counts.get(day, 0) + 1
        
        return UsageStatistics(
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            average_response_time_ms=avg_response_time,
            requests_by_endpoint=endpoint_counts,
            requests_by_day=day_counts,
            error_rate=(failed / total * 100) if total > 0 else 0
        )
    
    async def check_rate_limit(
        self,
        api_key_id: str,
        limit_type: str = 'per_minute'
    ) -> tuple[bool, int, int]:
        """
        Check if rate limit is exceeded.
        
        Returns:
            Tuple of (allowed, current_count, limit)
        """
        db_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
        
        if not db_key:
            return False, 0, 0
        
        # Determine time window
        if limit_type == 'per_minute':
            window = timedelta(minutes=1)
            limit = db_key.rate_limit_per_minute
        elif limit_type == 'per_hour':
            window = timedelta(hours=1)
            limit = db_key.rate_limit_per_hour
        else:  # per_day
            window = timedelta(days=1)
            limit = db_key.rate_limit_per_day
        
        start_time = datetime.utcnow() - window
        
        # Count requests in window
        count = self.db.query(APIKeyUsage).filter(
            APIKeyUsage.api_key_id == api_key_id,
            APIKeyUsage.timestamp >= start_time
        ).count()
        
        return count < limit, count, limit
    
    async def rotate_key(
        self,
        key_id: str,
        rotated_by: str
    ) -> Optional[APIKeyCredentials]:
        """
        Rotate an API key (create new, revoke old).
        
        Returns:
            New API key credentials
        """
        old_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        
        if not old_key:
            return None
        
        # Create new key with same settings
        new_credentials = await self.create_key(
            user_id=old_key.user_id,
            name=old_key.name,
            scopes=[APIKeyScope(s) for s in old_key.scopes],
            organization_id=old_key.organization_id,
            description=old_key.description,
            expires_in_days=(old_key.expires_at - datetime.utcnow()).days if old_key.expires_at else None,
            rate_limits={
                'per_minute': old_key.rate_limit_per_minute,
                'per_hour': old_key.rate_limit_per_hour,
                'per_day': old_key.rate_limit_per_day,
            },
            allowed_ips=old_key.allowed_ips,
            allowed_origins=old_key.allowed_origins
        )
        
        # Revoke old key
        await self.revoke_key(key_id, rotated_by, "Rotated to new key")
        
        return new_credentials
    
    def has_scope(self, api_key: APIKey, scope: APIKeyScope) -> bool:
        """Check if API key has a specific scope"""
        return scope.value in api_key.scopes or APIKeyScope.ADMIN.value in api_key.scopes


# Rate limiter helper class

class APIRateLimiter:
    """Rate limiter for API requests"""
    
    def __init__(self, api_key_service: APIKeyService):
        self.api_key_service = api_key_service
        
    async def check_request_allowed(
        self,
        api_key_id: str
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if a request is allowed under rate limits.
        
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        results = {}
        
        # Check all time windows
        for limit_type in ['per_minute', 'per_hour', 'per_day']:
            allowed, current, limit = await self.api_key_service.check_rate_limit(
                api_key_id, limit_type
            )
            results[limit_type] = {
                'allowed': allowed,
                'current': current,
                'limit': limit,
                'remaining': max(0, limit - current)
            }
        
        # Request is allowed only if all limits are respected
        all_allowed = all(r['allowed'] for r in results.values())
        
        return all_allowed, results
