from __future__ import annotations

from typing import Any, Dict

from .types import ValidationResult


REQUIRED_FIELDS = [
    "title",
    "description",
    "offer_type",
    "property_type",
    "price",
    "city",
]


def validate_property_for_publish(prop: Dict[str, Any], images: list[Dict[str, Any]]) -> ValidationResult:
    missing = []
    errors = []

    for field in REQUIRED_FIELDS:
        if prop.get(field) in (None, "", []):
            missing.append(field)

    if not images:
        missing.append("images")

    if prop.get("price") is not None:
        try:
            if float(prop["price"]) <= 0:
                errors.append("price must be > 0")
        except Exception:
            errors.append("price must be numeric")

    return ValidationResult(ok=(not missing and not errors), missing_fields=missing, errors=errors)
