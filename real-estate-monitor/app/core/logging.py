"""Compatibility shim for legacy imports: app.core.logging."""

from app.logging_config import get_logger

__all__ = ["get_logger"]
