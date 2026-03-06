from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class OtodomAuth:
    access_token: str
    refresh_token: Optional[str] = None


@dataclass
class ValidationResult:
    ok: bool
    missing_fields: List[str]
    errors: List[str]


@dataclass
class OtodomPublicationResult:
    ok: bool
    publication_status: str
    external_listing_id: Optional[str]
    payload: Dict[str, Any]
    response: Dict[str, Any]
    error: Optional[str] = None
