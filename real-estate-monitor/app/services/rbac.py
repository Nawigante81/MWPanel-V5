"""
Role-Based Access Control (RBAC) Service.
Professional-grade permission system for multi-user environments.
"""
from enum import Enum
from typing import List, Optional, Set
from dataclasses import dataclass
from functools import wraps

from fastapi import HTTPException, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.db import get_db

logger = get_logger("rbac")


class Role(str, Enum):
    """User roles in the system."""
    SUPER_ADMIN = "super_admin"      # Full system access
    ADMIN = "admin"                  # Organization admin
    MANAGER = "manager"              # Team manager
    AGENT = "agent"                  # Real estate agent
    ANALYST = "analyst"              # Data analyst (read-only + reports)
    VIEWER = "viewer"                # Read-only access
    API_CLIENT = "api_client"        # External API access only


class Permission(str, Enum):
    """System permissions."""
    # Offers
    OFFERS_READ = "offers:read"
    OFFERS_CREATE = "offers:create"
    OFFERS_UPDATE = "offers:update"
    OFFERS_DELETE = "offers:delete"
    OFFERS_EXPORT = "offers:export"
    
    # Sources
    SOURCES_READ = "sources:read"
    SOURCES_MANAGE = "sources:manage"
    
    # Notifications
    NOTIFICATIONS_READ = "notifications:read"
    NOTIFICATIONS_MANAGE = "notifications:manage"
    
    # Users
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    
    # Settings
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    
    # Reports
    REPORTS_READ = "reports:read"
    REPORTS_CREATE = "reports:create"
    
    # Leads
    LEADS_READ = "leads:read"
    LEADS_CREATE = "leads:create"
    LEADS_UPDATE = "leads:update"
    LEADS_DELETE = "leads:delete"
    
    # System
    SYSTEM_ADMIN = "system:admin"
    AUDIT_READ = "audit:read"
    API_KEYS_MANAGE = "api_keys:manage"


# Role-Permission mapping
ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: set(Permission),  # All permissions
    
    Role.ADMIN: {
        Permission.OFFERS_READ, Permission.OFFERS_CREATE, Permission.OFFERS_UPDATE,
        Permission.OFFERS_DELETE, Permission.OFFERS_EXPORT,
        Permission.SOURCES_READ, Permission.SOURCES_MANAGE,
        Permission.NOTIFICATIONS_READ, Permission.NOTIFICATIONS_MANAGE,
        Permission.USERS_READ, Permission.USERS_CREATE, Permission.USERS_UPDATE, Permission.USERS_DELETE,
        Permission.SETTINGS_READ, Permission.SETTINGS_WRITE,
        Permission.REPORTS_READ, Permission.REPORTS_CREATE,
        Permission.LEADS_READ, Permission.LEADS_CREATE, Permission.LEADS_UPDATE, Permission.LEADS_DELETE,
        Permission.AUDIT_READ, Permission.API_KEYS_MANAGE,
    },
    
    Role.MANAGER: {
        Permission.OFFERS_READ, Permission.OFFERS_CREATE, Permission.OFFERS_UPDATE,
        Permission.OFFERS_EXPORT,
        Permission.SOURCES_READ,
        Permission.NOTIFICATIONS_READ, Permission.NOTIFICATIONS_MANAGE,
        Permission.USERS_READ, Permission.USERS_CREATE, Permission.USERS_UPDATE,
        Permission.SETTINGS_READ,
        Permission.REPORTS_READ, Permission.REPORTS_CREATE,
        Permission.LEADS_READ, Permission.LEADS_CREATE, Permission.LEADS_UPDATE, Permission.LEADS_DELETE,
    },
    
    Role.AGENT: {
        Permission.OFFERS_READ, Permission.OFFERS_CREATE, Permission.OFFERS_UPDATE,
        Permission.OFFERS_EXPORT,
        Permission.SOURCES_READ,
        Permission.NOTIFICATIONS_READ,
        Permission.REPORTS_READ,
        Permission.LEADS_READ, Permission.LEADS_CREATE, Permission.LEADS_UPDATE,
    },
    
    Role.ANALYST: {
        Permission.OFFERS_READ, Permission.OFFERS_EXPORT,
        Permission.SOURCES_READ,
        Permission.REPORTS_READ, Permission.REPORTS_CREATE,
        Permission.LEADS_READ,
    },
    
    Role.VIEWER: {
        Permission.OFFERS_READ,
        Permission.SOURCES_READ,
        Permission.LEADS_READ,
    },
    
    Role.API_CLIENT: {
        Permission.OFFERS_READ, Permission.OFFERS_EXPORT,
        Permission.SOURCES_READ,
        Permission.LEADS_READ, Permission.LEADS_CREATE, Permission.LEADS_UPDATE,
    },
}


@dataclass
class UserContext:
    """User context with authentication info."""
    user_id: str
    email: str
    role: Role
    organization_id: Optional[str] = None
    permissions: Set[Permission] = None
    api_key_id: Optional[str] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = ROLE_PERMISSIONS.get(self.role, set())
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission."""
        return permission in self.permissions
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if user has any of the permissions."""
        return any(p in self.permissions for p in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """Check if user has all permissions."""
        return all(p in self.permissions for p in permissions)


class RBACService:
    """RBAC service for permission management."""
    
    def __init__(self):
        self.role_permissions = ROLE_PERMISSIONS
    
    def get_user_permissions(self, role: Role) -> Set[Permission]:
        """Get all permissions for a role."""
        return self.role_permissions.get(role, set())
    
    def check_permission(self, user: UserContext, permission: Permission) -> bool:
        """Check if user has permission."""
        return user.has_permission(permission)
    
    def require_permission(self, user: UserContext, permission: Permission):
        """Require permission or raise exception."""
        if not self.check_permission(user, permission):
            logger.warning(
                f"Permission denied: {permission} for user {user.user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission.value}"
            )


# FastAPI dependency for authentication
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db)
) -> UserContext:
    """
    Get current user from request.
    
    Supports:
    - JWT token in Authorization header
    - API key in X-API-Key header
    - Session cookie
    """
    # Try API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = await _get_user_from_api_key(session, api_key)
        if user:
            return user
    
    # Try JWT token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = await _get_user_from_jwt(session, token)
        if user:
            return user
    
    # Default to viewer for public endpoints
    return UserContext(
        user_id="anonymous",
        email="anonymous@system.local",
        role=Role.VIEWER
    )


async def _get_user_from_api_key(
    session: AsyncSession,
    api_key: str
) -> Optional[UserContext]:
    """Get user from API key."""
    from app.models import APIKey
    
    key_record = await session.scalar(
        select(APIKey)
        .where(APIKey.key_hash == _hash_api_key(api_key))
        .where(APIKey.is_active == True)
    )
    
    if not key_record:
        return None
    
    # Update last used
    key_record.last_used_at = datetime.utcnow()
    await session.commit()
    
    return UserContext(
        user_id=key_record.user_id,
        email=f"api@{key_record.name}",
        role=Role.API_CLIENT,
        api_key_id=str(key_record.id),
        organization_id=key_record.organization_id
    )


async def _get_user_from_jwt(
    session: AsyncSession,
    token: str
) -> Optional[UserContext]:
    """Get user from JWT token."""
    try:
        import jwt
        from app.settings import settings
        
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"]
        )
        
        return UserContext(
            user_id=payload["sub"],
            email=payload.get("email", ""),
            role=Role(payload.get("role", "viewer")),
            organization_id=payload.get("organization_id")
        )
        
    except Exception as e:
        logger.debug(f"JWT decode failed: {e}")
        return None


def _hash_api_key(api_key: str) -> str:
    """Hash API key for storage."""
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()


# Permission decorators for FastAPI endpoints
def require_permission(permission: Permission):
    """Decorator to require specific permission."""
    async def checker(
        user: UserContext = Depends(get_current_user)
    ):
        rbac = RBACService()
        rbac.require_permission(user, permission)
        return user
    return checker


def require_any_permission(permissions: List[Permission]):
    """Decorator to require any of the permissions."""
    async def checker(
        user: UserContext = Depends(get_current_user)
    ):
        if not user.has_any_permission(permissions):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied. Required: {[p.value for p in permissions]}"
            )
        return user
    return checker


# Convenience dependencies
require_offers_read = require_permission(Permission.OFFERS_READ)
require_offers_write = require_permission(Permission.OFFERS_CREATE)
require_admin = require_permission(Permission.SYSTEM_ADMIN)
require_leads_manage = require_any_permission([Permission.LEADS_CREATE, Permission.LEADS_UPDATE])


# Global instance
_rbac_service: Optional[RBACService] = None


def get_rbac_service() -> RBACService:
    """Get or create RBAC service."""
    global _rbac_service
    
    if _rbac_service is None:
        _rbac_service = RBACService()
    
    return _rbac_service


from datetime import datetime
