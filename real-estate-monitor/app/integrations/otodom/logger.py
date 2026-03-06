from __future__ import annotations

from app.logging_config import get_logger

logger = get_logger("otodom")


def mask_secret(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"
