"""
Audit Logging Service

Professional-grade audit logging system for tracking all changes,
access, and actions in the real estate monitoring platform.
Compliant with GDPR and professional standards.
"""

import json
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from contextvars import ContextVar
import asyncio
from sqlalchemy import Column, String, DateTime, Text, Index, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

from app.core.logging import get_logger

logger = get_logger(__name__)

# Context variable for current user/request context
audit_context: ContextVar[Dict[str, Any]] = ContextVar('audit_context', default={})


class AuditAction(str, Enum):
    """Types of audit actions"""
    # Offer actions
    OFFER_CREATED = "offer:created"
    OFFER_UPDATED = "offer:updated"
    OFFER_DELETED = "offer:deleted"
    OFFER_VIEWED = "offer:viewed"
    OFFER_EXPORTED = "offer:exported"
    OFFER_SHARED = "offer:shared"
    
    # Search actions
    SEARCH_CREATED = "search:created"
    SEARCH_UPDATED = "search:updated"
    SEARCH_DELETED = "search:deleted"
    SEARCH_EXECUTED = "search:executed"
    
    # User actions
    USER_LOGIN = "user:login"
    USER_LOGOUT = "user:logout"
    USER_CREATED = "user:created"
    USER_UPDATED = "user:updated"
    USER_DELETED = "user:deleted"
    USER_PASSWORD_CHANGED = "user:password_changed"
    
    # API actions
    API_KEY_CREATED = "api_key:created"
    API_KEY_REVOKED = "api_key:revoked"
    API_REQUEST = "api:request"
    
    # Lead actions
    LEAD_CREATED = "lead:created"
    LEAD_UPDATED = "lead:updated"
    LEAD_CONVERTED = "lead:converted"
    
    # System actions
    CONFIG_CHANGED = "config:changed"
    REPORT_GENERATED = "report:generated"
    DATA_EXPORTED = "data:exported"
    NOTIFICATION_SENT = "notification:sent"


class AuditSeverity(str, Enum):
    """Severity levels for audit events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


Base = declarative_base()


class AuditLogEntry(Base):
    """Database model for audit log entries"""
    __tablename__ = 'audit_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default='info')
    
    # Actor information
    user_id = Column(String(100), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    api_key_id = Column(String(100), nullable=True)
    
    # Resource information
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(100), nullable=True, index=True)
    
    # Request context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    session_id = Column(String(100), nullable=True)
    
    # Change details
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    changes_summary = Column(Text, nullable=True)
    
    # Metadata
    organization_id = Column(String(100), nullable=True, index=True)
    metadata = Column(JSONB, nullable=True)
    
    # Integrity
    integrity_hash = Column(String(64), nullable=False)
    
    __table_args__ = (
        Index('idx_audit_timestamp_action', 'timestamp', 'action'),
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_org_timestamp', 'organization_id', 'timestamp'),
    )


@dataclass
class AuditContext:
    """Context for audit logging"""
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    api_key_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    organization_id: Optional[str] = None


class AuditLogger:
    """
    Professional audit logging system.
    
    Features:
    - Immutable audit trail with integrity verification
    - Tamper-evident logging with cryptographic hashes
    - GDPR-compliant data handling
    - Efficient querying and filtering
    - Automatic retention management
    """
    
    def __init__(self, database_url: str, retention_days: int = 2555):  # 7 years
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.retention_days = retention_days
        self._batch_queue: List[Dict[str, Any]] = []
        self._batch_size = 100
        self._flush_interval = 5  # seconds
        self._running = False
        
    async def start(self):
        """Start the audit logger background tasks"""
        self._running = True
        asyncio.create_task(self._flush_loop())
        asyncio.create_task(self._retention_cleanup_loop())
        logger.info("Audit logger started")
        
    async def stop(self):
        """Stop the audit logger and flush pending entries"""
        self._running = False
        await self._flush_batch()
        logger.info("Audit logger stopped")
        
    async def _flush_loop(self):
        """Periodic batch flush"""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            if self._batch_queue:
                await self._flush_batch()
                
    async def _retention_cleanup_loop(self):
        """Periodic cleanup of old audit logs"""
        while self._running:
            await asyncio.sleep(86400)  # Daily
            await self._cleanup_old_logs()
    
    def set_context(self, context: AuditContext):
        """Set the audit context for the current execution"""
        audit_context.set({
            'user_id': context.user_id,
            'user_email': context.user_email,
            'user_role': context.user_role,
            'api_key_id': context.api_key_id,
            'ip_address': context.ip_address,
            'user_agent': context.user_agent,
            'request_id': context.request_id,
            'session_id': context.session_id,
            'organization_id': context.organization_id,
        })
    
    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an audit event.
        
        Args:
            action: Type of action performed
            resource_type: Type of resource affected
            resource_id: ID of the resource
            old_values: Previous values (for updates)
            new_values: New values
            severity: Event severity level
            metadata: Additional metadata
            
        Returns:
            Audit log entry ID
        """
        ctx = audit_context.get()
        
        # Calculate changes summary
        changes_summary = None
        if old_values and new_values:
            changes_summary = self._calculate_changes(old_values, new_values)
        
        entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow(),
            'action': action.value,
            'severity': severity.value,
            'user_id': ctx.get('user_id'),
            'user_email': ctx.get('user_email'),
            'user_role': ctx.get('user_role'),
            'api_key_id': ctx.get('api_key_id'),
            'resource_type': resource_type,
            'resource_id': resource_id,
            'ip_address': ctx.get('ip_address'),
            'user_agent': ctx.get('user_agent'),
            'request_id': ctx.get('request_id'),
            'session_id': ctx.get('session_id'),
            'old_values': old_values,
            'new_values': new_values,
            'changes_summary': changes_summary,
            'organization_id': ctx.get('organization_id'),
            'metadata': metadata or {},
        }
        
        # Calculate integrity hash
        entry['integrity_hash'] = self._calculate_hash(entry)
        
        # Add to batch queue
        self._batch_queue.append(entry)
        
        # Flush if batch is full
        if len(self._batch_queue) >= self._batch_size:
            await self._flush_batch()
        
        return entry['id']
    
    def _calculate_changes(
        self,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any]
    ) -> str:
        """Calculate a human-readable summary of changes"""
        changes = []
        all_keys = set(old_values.keys()) | set(new_values.keys())
        
        for key in all_keys:
            old_val = old_values.get(key)
            new_val = new_values.get(key)
            
            if old_val != new_val:
                if old_val is None:
                    changes.append(f"{key}: ustawiono na '{new_val}'")
                elif new_val is None:
                    changes.append(f"{key}: usunięto (było '{old_val}')")
                else:
                    changes.append(f"{key}: zmieniono z '{old_val}' na '{new_val}'")
        
        return "; ".join(changes) if changes else None
    
    def _calculate_hash(self, entry: Dict[str, Any]) -> str:
        """Calculate integrity hash for tamper detection"""
        # Create canonical representation
        hash_data = {
            'timestamp': entry['timestamp'].isoformat() if isinstance(entry['timestamp'], datetime) else entry['timestamp'],
            'action': entry['action'],
            'user_id': entry['user_id'],
            'resource_type': entry['resource_type'],
            'resource_id': entry['resource_id'],
        }
        
        canonical = json.dumps(hash_data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    async def _flush_batch(self):
        """Flush batched entries to database"""
        if not self._batch_queue:
            return
            
        entries = self._batch_queue[:]
        self._batch_queue = []
        
        try:
            session = self.Session()
            for entry_data in entries:
                entry = AuditLogEntry(**entry_data)
                session.add(entry)
            session.commit()
            logger.debug(f"Flushed {len(entries)} audit entries")
        except Exception as e:
            logger.error(f"Failed to flush audit entries: {e}")
            session.rollback()
            # Re-queue failed entries
            self._batch_queue.extend(entries)
        finally:
            session.close()
    
    async def _cleanup_old_logs(self):
        """Remove audit logs older than retention period"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        try:
            session = self.Session()
            deleted = session.query(AuditLogEntry).filter(
                AuditLogEntry.timestamp < cutoff_date
            ).delete()
            session.commit()
            logger.info(f"Cleaned up {deleted} old audit log entries")
        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")
            session.rollback()
        finally:
            session.close()
    
    async def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query audit logs with filters.
        
        Returns:
            List of audit log entries as dictionaries
        """
        session = self.Session()
        try:
            query = session.query(AuditLogEntry)
            
            if user_id:
                query = query.filter(AuditLogEntry.user_id == user_id)
            if action:
                query = query.filter(AuditLogEntry.action == action.value)
            if resource_type:
                query = query.filter(AuditLogEntry.resource_type == resource_type)
            if resource_id:
                query = query.filter(AuditLogEntry.resource_id == resource_id)
            if organization_id:
                query = query.filter(AuditLogEntry.organization_id == organization_id)
            if start_date:
                query = query.filter(AuditLogEntry.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditLogEntry.timestamp <= end_date)
            if severity:
                query = query.filter(AuditLogEntry.severity == severity.value)
            
            entries = query.order_by(
                AuditLogEntry.timestamp.desc()
            ).offset(offset).limit(limit).all()
            
            return [self._entry_to_dict(e) for e in entries]
        finally:
            session.close()
    
    def _entry_to_dict(self, entry: AuditLogEntry) -> Dict[str, Any]:
        """Convert audit entry to dictionary"""
        return {
            'id': str(entry.id),
            'timestamp': entry.timestamp.isoformat(),
            'action': entry.action,
            'severity': entry.severity,
            'user_id': entry.user_id,
            'user_email': entry.user_email,
            'user_role': entry.user_role,
            'resource_type': entry.resource_type,
            'resource_id': entry.resource_id,
            'ip_address': entry.ip_address,
            'changes_summary': entry.changes_summary,
            'old_values': entry.old_values,
            'new_values': entry.new_values,
            'metadata': entry.metadata,
            'integrity_hash': entry.integrity_hash,
        }
    
    async def verify_integrity(self, entry_id: str) -> bool:
        """
        Verify the integrity of an audit log entry.
        
        Returns:
            True if entry is intact, False if tampered
        """
        session = self.Session()
        try:
            entry = session.query(AuditLogEntry).filter(
                AuditLogEntry.id == entry_id
            ).first()
            
            if not entry:
                return False
            
            # Recalculate hash
            entry_data = {
                'timestamp': entry.timestamp,
                'action': entry.action,
                'user_id': entry.user_id,
                'resource_type': entry.resource_type,
                'resource_id': entry.resource_id,
            }
            
            calculated_hash = self._calculate_hash(entry_data)
            return calculated_hash == entry.integrity_hash
        finally:
            session.close()
    
    async def get_statistics(
        self,
        organization_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get audit log statistics"""
        from sqlalchemy import func
        
        start_date = datetime.utcnow() - timedelta(days=days)
        session = self.Session()
        
        try:
            query = session.query(AuditLogEntry).filter(
                AuditLogEntry.timestamp >= start_date
            )
            
            if organization_id:
                query = query.filter(AuditLogEntry.organization_id == organization_id)
            
            total_entries = query.count()
            
            # Actions breakdown
            action_counts = session.query(
                AuditLogEntry.action,
                func.count(AuditLogEntry.id)
            ).filter(
                AuditLogEntry.timestamp >= start_date
            ).group_by(AuditLogEntry.action).all()
            
            # User activity
            user_counts = session.query(
                AuditLogEntry.user_id,
                func.count(AuditLogEntry.id)
            ).filter(
                AuditLogEntry.timestamp >= start_date
            ).group_by(AuditLogEntry.user_id).all()
            
            return {
                'total_entries': total_entries,
                'period_days': days,
                'actions_breakdown': {action: count for action, count in action_counts},
                'user_activity': {user_id: count for user_id, count in user_counts if user_id},
            }
        finally:
            session.close()


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def init_audit_logger(database_url: str, retention_days: int = 2555) -> AuditLogger:
    """Initialize the global audit logger"""
    global _audit_logger
    _audit_logger = AuditLogger(database_url, retention_days)
    return _audit_logger


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance"""
    if _audit_logger is None:
        raise RuntimeError("Audit logger not initialized")
    return _audit_logger


# Convenience decorators

def audit_log(
    action: AuditAction,
    resource_type: str,
    resource_id_param: str = 'id',
    log_old_values: bool = False
):
    """
    Decorator to automatically log function calls.
    
    Args:
        action: Audit action type
        resource_type: Type of resource being accessed
        resource_id_param: Parameter name containing resource ID
        log_old_values: Whether to fetch and log old values
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            audit_logger = get_audit_logger()
            
            # Get resource ID from kwargs
            resource_id = kwargs.get(resource_id_param)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Log the action
            await audit_logger.log(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata={'function': func.__name__}
            )
            
            return result
        return wrapper
    return decorator
