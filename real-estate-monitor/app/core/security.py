"""Compatibility shim for legacy imports: app.core.security."""

from app.services.rbac import get_current_user

__all__ = ["get_current_user"]
