"""Lightweight JSON store for frontend compatibility endpoints."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

STORE_PATH = Path(os.getenv("COMPAT_STORE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "compat_store.json")))
_lock = Lock()


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, set):
        return list(value)
    return str(value)


def _now() -> str:
    return datetime.utcnow().isoformat()


def _ensure() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text(json.dumps({"listings": [], "contacts": [], "companies": [], "deals": [], "activities": [], "tickets": [], "tasks": [], "leads": [], "properties": [], "property_images": [], "property_publications": [], "publication_jobs": [], "contact_timeline": [], "documents": [], "audit_logs": [], "notifications": [], "notification_meta": [], "profile": [], "auth_meta": [], "users": [], "auth_rate_limits": [], "password_reset_tokens": []}, indent=2))


def _default_store() -> Dict[str, Any]:
    return {
        "listings": [],
        "contacts": [],
        "companies": [],
        "deals": [],
        "activities": [],
        "tickets": [],
        "tasks": [],
        "leads": [],
        "properties": [],
        "property_images": [],
        "property_publications": [],
        "publication_jobs": [],
        "contact_timeline": [],
        "documents": [],
        "audit_logs": [],
        "notifications": [],
        "notification_meta": [],
        "profile": [],
        "auth_meta": [],
        "users": [],
        "auth_rate_limits": [],
        "password_reset_tokens": [],
    }


def _read() -> Dict[str, Any]:
    _ensure()
    try:
        raw = STORE_PATH.read_text()
        if not raw.strip():
            data = _default_store()
            _write(data)
            return data
        data = json.loads(raw)
    except Exception:
        data = _default_store()
        _write(data)
        return data

    # Ensure required keys exist
    defaults = _default_store()
    for k, v in defaults.items():
        data.setdefault(k, v)
    return data


def _write(data: Dict[str, Any]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_json_default))


def seed_if_empty() -> Dict[str, int]:
    with _lock:
        data = _read()
        c = {"listings": 0, "contacts": 0, "tasks": 0, "leads": 0}
        if not data.get("listings"):
            data["listings"] = [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Mieszkanie 3 pokoje, Wrzeszcz",
                    "price": 789000,
                    "city": "Gdańsk",
                    "location": "Gdańsk",
                    "area_sqm": 62.5,
                    "rooms": 3,
                    "status": "published",
                    "source": "seed",
                    "transaction_type": "sale",
                    "url": "https://example.com/oferta/1",
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ]
            c["listings"] = 1
        if not data.get("contacts"):
            data["contacts"] = []
        if not data.get("tasks"):
            data["tasks"] = []
        if not data.get("leads"):
            data["leads"] = []
        _write(data)
        return c


def list_items(key: str) -> List[Dict[str, Any]]:
    with _lock:
        d = _read()
        return d.get(key, [])


def get_item(key: str, item_id: str) -> Optional[Dict[str, Any]]:
    items = list_items(key)
    for i in items:
        if i["id"] == item_id:
            return i
    return None


def create_item(key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        d = _read()
        item = {"id": str(uuid.uuid4()), **payload, "created_at": _now(), "updated_at": _now()}
        d.setdefault(key, []).insert(0, item)
        _write(d)
        return item


def update_item(key: str, item_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with _lock:
        d = _read()
        for i in d.setdefault(key, []):
            if i["id"] == item_id:
                i.update(payload)
                i["updated_at"] = _now()
                _write(d)
                return i
        return None


def delete_item(key: str, item_id: str) -> bool:
    with _lock:
        d = _read()
        items = d.setdefault(key, [])
        before = len(items)
        items[:] = [i for i in items if i["id"] != item_id]
        _write(d)
        return len(items) != before
