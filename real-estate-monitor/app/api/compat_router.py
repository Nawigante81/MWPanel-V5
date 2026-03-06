import base64
import hashlib
import hmac
import io
import mimetypes
import os
import secrets
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Offer
from app.services.compat_store import (
    create_item,
    delete_item,
    get_item,
    list_items,
    seed_if_empty,
    update_item,
)
from app.integrations.otodom import enqueue_publication_job, process_due_jobs
from app.integrations.otodom.validators import validate_property_for_publish

LISTING_STATUSES = {"draft", "published", "archived", "sold", "rented"}
LEGACY_LISTING_STATUSES = {"active": "published", "inactive": "archived", "reserved": "published"}
LEAD_STATUSES = {"new", "contacted", "qualified", "proposal", "won", "lost"}
DEAL_STATUSES = {"open", "won", "lost"}
DEAL_STAGES = {"qualification", "needs_analysis", "proposal", "negotiation", "closed_won", "closed_lost"}
TICKET_STATUSES = {"new", "open", "pending", "resolved", "closed"}
TICKET_PRIORITIES = {"low", "medium", "high", "urgent"}
PROPERTY_STATUSES = {"draft", "ready_for_publish", "published", "update_required", "paused", "sold", "archived", "publish_error"}

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_DOC_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/plain",
}
MAX_DOC_SIZE = 50 * 1024 * 1024  # 50MB


def _safe_doc_record(rec: dict) -> dict:
    r = dict(rec)
    r.pop("storage_path", None)
    return r


def normalize_listing_status(status: str) -> str:
    return LEGACY_LISTING_STATUSES.get(status, status)


def _norm_phone(v: str | None) -> str:
    if not v:
        return ""
    return "".join(ch for ch in v if ch.isdigit())


def _find_duplicate_contact(email: str | None, phone: str | None, ignore_id: str | None = None):
    email_n = (email or "").strip().lower()
    phone_n = _norm_phone(phone)
    if not email_n and not phone_n:
        return None

    for c in list_items("contacts"):
        if ignore_id and c.get("id") == ignore_id:
            continue
        c_email = (c.get("email") or "").strip().lower()
        c_phone = _norm_phone(c.get("phone"))
        if email_n and c_email and c_email == email_n:
            return c
        if phone_n and c_phone and c_phone == phone_n:
            return c
    return None


TOKEN_TTL_SECONDS = 12 * 60 * 60
JWT_ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _auth_secret() -> str:
    return os.getenv("CRM_AUTH_SECRET", "change-me-in-env")


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _safe_hash_password(password: str) -> str:
    try:
        return _hash_password(password)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password hashing error: {str(e)}")


def _verify_password(raw_password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        return pwd_context.verify(raw_password, stored)
    except Exception:
        return False


def _issue_token(user_id: str, role: str, email: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=TOKEN_TTL_SECONDS)).timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    return jwt.encode(payload, _auth_secret(), algorithm=JWT_ALGORITHM)


def _verify_token(token: str):
    try:
        data = jwt.decode(token, _auth_secret(), algorithms=[JWT_ALGORITHM])
        return {"user_id": data.get("sub"), "role": data.get("role"), "email": data.get("email")}
    except Exception:
        return None


def _find_user_by_email(email: str):
    email_n = (email or "").strip().lower()
    return next((u for u in list_items("users") if (u.get("email") or "").strip().lower() == email_n), None)


def _public_user(user: dict):
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "name": user.get("name") or user.get("email"),
        "role": user.get("role") or "user",
        "avatar_url": user.get("avatar_url"),
        "is_active": bool(user.get("is_active", True)),
    }


def _parse_dt(v: str | None):
    try:
        return datetime.fromisoformat(v) if v else None
    except Exception:
        return None


def _validate_deal_payload(payload: dict, current: dict | None = None):
    merged = {**(current or {}), **payload}

    if merged.get("status") and merged["status"] not in DEAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid deal status: {merged['status']}")
    if merged.get("stage") and merged["stage"] not in DEAL_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid deal stage: {merged['stage']}")

    if "probability" in merged and merged["probability"] is not None:
        try:
            prob = int(merged["probability"])
        except Exception:
            raise HTTPException(status_code=400, detail="probability must be an integer 0-100")
        if prob < 0 or prob > 100:
            raise HTTPException(status_code=400, detail="probability must be in range 0-100")

    stage = merged.get("stage")
    if stage in {"proposal", "negotiation"}:
        if not merged.get("next_step"):
            raise HTTPException(status_code=400, detail="next_step is required for proposal/negotiation stage")
        if not merged.get("expected_close_date"):
            raise HTTPException(status_code=400, detail="expected_close_date is required for proposal/negotiation stage")

    if merged.get("status") == "won":
        if not merged.get("value"):
            raise HTTPException(status_code=400, detail="value is required when deal is won")
        merged.setdefault("stage", "closed_won")
        merged.setdefault("actual_close_date", datetime.utcnow().isoformat())

    if merged.get("status") == "lost":
        if not merged.get("lost_reason"):
            raise HTTPException(status_code=400, detail="lost_reason is required when deal is lost")
        merged.setdefault("stage", "closed_lost")
        merged.setdefault("actual_close_date", datetime.utcnow().isoformat())

    return merged


def _ticket_due_by_priority(priority: str) -> str:
    hours = {"low": 72, "medium": 48, "high": 24, "urgent": 4}.get(priority, 48)
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _require_roles(authorization: str | None, allowed_roles: set[str]):
    if not authorization:
        raise HTTPException(status_code=401, detail="Brak tokena")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    data = _verify_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")
    if data.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    return data


def _can_access_record(user: dict, record: dict) -> bool:
    if user.get("role") == "admin":
        return True
    owner = record.get("owner_id") or record.get("created_by")
    return owner is None or owner == user.get("user_id")


def _require_admin(authorization: str | None):
    if not authorization:
        raise HTTPException(status_code=401, detail="Brak tokena")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    data = _verify_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")
    if data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    return data


def _check_login_rate_limit(identity: str):
    now = datetime.utcnow()
    rl = list_items("auth_rate_limits")
    rec = next((r for r in rl if r.get("identity") == identity), None)
    if not rec:
        return

    locked_until = _parse_dt(rec.get("locked_until"))
    if locked_until and locked_until > now:
        sec = int((locked_until - now).total_seconds())
        raise HTTPException(status_code=429, detail=f"Za dużo prób logowania. Spróbuj za {sec}s")


def _register_login_failure(identity: str):
    now = datetime.utcnow()
    rl = list_items("auth_rate_limits")
    rec = next((r for r in rl if r.get("identity") == identity), None)
    if not rec:
        create_item("auth_rate_limits", {"identity": identity, "fail_count": 1, "locked_until": None, "last_attempt_at": now.isoformat()})
        return

    fail_count = int(rec.get("fail_count") or 0) + 1
    lock_minutes = 0
    if fail_count >= 10:
        lock_minutes = 30
    elif fail_count >= 7:
        lock_minutes = 10
    elif fail_count >= 5:
        lock_minutes = 2

    payload = {"fail_count": fail_count, "last_attempt_at": now.isoformat()}
    if lock_minutes:
        payload["locked_until"] = (now + timedelta(minutes=lock_minutes)).isoformat()
    update_item("auth_rate_limits", rec["id"], payload)


def _clear_login_failures(identity: str):
    rl = list_items("auth_rate_limits")
    rec = next((r for r in rl if r.get("identity") == identity), None)
    if rec:
        update_item("auth_rate_limits", rec["id"], {"fail_count": 0, "locked_until": None})


def _notify(title: str, message: str, n_type: str = "system", entity_type: str | None = None, entity_id: str | None = None, user_id: str = "admin-1"):
    create_item("notifications", {
        "user_id": user_id,
        "type": n_type,
        "title": title,
        "message": message,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "is_read": False,
    })


async def _sync_offer_notifications(session: AsyncSession):
    meta = list_items("notification_meta")
    last_ts = None
    if meta:
        last_ts = meta[0].get("last_offer_notified_at")

    def _naive(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if getattr(dt, 'tzinfo', None) else dt

    try:
        last_dt = datetime.fromisoformat(last_ts) if last_ts else datetime(1970, 1, 1)
        last_dt = _naive(last_dt)
    except Exception:
        last_dt = datetime(1970, 1, 1)

    import_col = func.coalesce(Offer.imported_at, Offer.first_seen)
    q = await session.execute(
        select(Offer)
        .where(import_col > last_dt)
        .order_by(import_col.asc())
        .limit(500)
    )
    offers = q.scalars().all()
    if not offers:
        return

    max_dt = last_dt
    for o in offers:
        ts = (o.imported_at or o.first_seen)
        if ts:
            ts = _naive(ts)
        if ts and ts > max_dt:
            max_dt = ts
        price_txt = f"{int(o.price):,} zł".replace(",", " ") if o.price is not None else "cena do uzgodnienia"
        _notify(
            title="Nowa oferta",
            message=f"{o.title or 'Oferta'} • {o.city or o.region or '-'} • {price_txt}",
            n_type="new_offer",
            entity_type="offer",
            entity_id=str(o.id),
        )

    if meta:
        update_item("notification_meta", meta[0]["id"], {"last_offer_notified_at": max_dt.isoformat()})
    else:
        create_item("notification_meta", {"last_offer_notified_at": max_dt.isoformat()})


router = APIRouter(tags=["frontend-compat"])


@router.post("/seed")
async def seed_data():
    return {"status": "ok", "created": seed_if_empty()}


@router.get("/listings")
async def list_listings(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    seed_if_empty()
    items = list_items("listings")
    normalized = []
    for i in items:
        row = dict(i)
        row["status"] = normalize_listing_status(row.get("status", "draft"))
        normalized.append(row)
    return {"listings": normalized[offset: offset + limit], "total": len(normalized)}


@router.get("/listings/{listing_id}")
async def get_listing(listing_id: str):
    item = get_item("listings", listing_id)
    if not item:
        raise HTTPException(status_code=404, detail="Listing not found")
    return item


@router.post("/listings")
async def create_listing(payload: dict):
    payload.setdefault("status", "draft")
    payload.setdefault("transaction_type", "sale")
    payload["status"] = normalize_listing_status(payload["status"])
    if payload["status"] not in LISTING_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid listing status: {payload['status']}")
    item = create_item("listings", payload)
    create_item("audit_logs", {"entity": "listing", "entity_id": item["id"], "action": "create", "changes": payload, "actor": "system"})
    return item


@router.patch("/listings/{listing_id}")
async def patch_listing(listing_id: str, payload: dict):
    if "status" in payload:
        payload["status"] = normalize_listing_status(payload["status"])
        if payload["status"] not in LISTING_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid listing status: {payload['status']}")
    item = update_item("listings", listing_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Listing not found")
    create_item("audit_logs", {"entity": "listing", "entity_id": listing_id, "action": "update", "changes": payload, "actor": "system"})
    if "status" in payload:
        _notify(
            title="Zmiana statusu oferty",
            message=f"{item.get('title') or item.get('id')}: {payload.get('status')}",
            n_type="listing_status_changed",
            entity_type="listing",
            entity_id=listing_id,
        )
    return item


@router.delete("/listings/{listing_id}")
async def remove_listing(listing_id: str):
    if not delete_item("listings", listing_id):
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"status": "deleted"}


@router.get("/contacts")
async def list_contacts():
    return {"contacts": list_items("contacts")}


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: str):
    item = get_item("contacts", contact_id)
    if not item:
        raise HTTPException(status_code=404, detail="Contact not found")
    return item


@router.post("/contacts")
async def create_contact(payload: dict):
    payload.setdefault("type", "lead")

    if not payload.get("name") and not payload.get("email") and not payload.get("phone"):
        raise HTTPException(status_code=400, detail="Wymagane: name lub email lub phone")

    dup = _find_duplicate_contact(payload.get("email"), payload.get("phone"))
    if dup:
        raise HTTPException(status_code=409, detail=f"Duplikat kontaktu: {dup.get('name') or dup.get('email') or dup.get('id')}")

    item = create_item("contacts", payload)
    _notify(
        title="Nowy kontakt",
        message=f"Dodano kontakt: {item.get('name') or item.get('email') or item.get('id')}",
        n_type="contact_created",
        entity_type="contact",
        entity_id=item.get("id"),
    )
    return item


@router.patch("/contacts/{contact_id}")
async def patch_contact(contact_id: str, payload: dict):
    existing = get_item("contacts", contact_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Contact not found")

    next_email = payload.get("email", existing.get("email"))
    next_phone = payload.get("phone", existing.get("phone"))
    dup = _find_duplicate_contact(next_email, next_phone, ignore_id=contact_id)
    if dup:
        raise HTTPException(status_code=409, detail=f"Duplikat kontaktu: {dup.get('name') or dup.get('email') or dup.get('id')}")

    item = update_item("contacts", contact_id, payload)
    return item


@router.delete("/contacts/{contact_id}")
async def remove_contact(contact_id: str):
    if not delete_item("contacts", contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "deleted"}


@router.get("/contacts/{contact_id}/timeline")
async def get_contact_timeline(contact_id: str):
    items = [x for x in list_items("contact_timeline") if x.get("contact_id") == contact_id]
    return {"events": items}


@router.post("/contacts/{contact_id}/timeline")
async def add_contact_timeline(contact_id: str, payload: dict):
    payload.setdefault("type", "note")
    payload.setdefault("message", "")
    payload["contact_id"] = contact_id
    event = create_item("contact_timeline", payload)
    return event


@router.get("/tasks")
async def list_tasks(status: str | None = None, assigned_to: str | None = None):
    tasks = list_items("tasks")
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if assigned_to:
        tasks = [t for t in tasks if t.get("assigned_to") == assigned_to]
    return {"tasks": tasks}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    item = get_item("tasks", task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    return item


@router.post("/tasks")
async def create_task(payload: dict):
    payload.setdefault("status", "pending")
    payload.setdefault("priority", "medium")
    payload.setdefault("completed_at", None)
    item = create_item("tasks", payload)
    _notify(
        title="Nowe zadanie",
        message=f"Dodano zadanie: {item.get('title') or item.get('id')}",
        n_type="task_created",
        entity_type="task",
        entity_id=item.get("id"),
    )
    return item


@router.patch("/tasks/{task_id}")
async def patch_task(task_id: str, payload: dict):
    item = update_item("tasks", task_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    create_item("audit_logs", {"entity": "task", "entity_id": task_id, "action": "update", "changes": payload, "actor": "system"})
    if payload.get("status") in {"pending", "in_progress", "completed", "cancelled"}:
        _notify(
            title="Zmiana statusu zadania",
            message=f"{item.get('title') or item.get('id')}: {payload.get('status')}",
            n_type="task_status_changed",
            entity_type="task",
            entity_id=task_id,
        )
    return item


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, payload: dict = {}):
    changes = {"status": "completed", "completed_at": datetime.utcnow().isoformat(), **payload}
    item = update_item("tasks", task_id, changes)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    create_item("audit_logs", {"entity": "task", "entity_id": task_id, "action": "complete", "changes": changes, "actor": "system"})
    return item


@router.delete("/tasks/{task_id}")
async def remove_task(task_id: str):
    if not delete_item("tasks", task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@router.get("/calendar")
async def list_calendar_events(from_: str | None = Query(default=None, alias="from"), to: str | None = None):
    events = list_items("calendar_events")

    def parse_dt(v: str | None):
        try:
            return datetime.fromisoformat(v) if v else None
        except Exception:
            return None

    from_dt = parse_dt(from_)
    to_dt = parse_dt(to)

    if from_dt or to_dt:
        filtered = []
        for e in events:
            start = parse_dt(e.get("start_at"))
            if not start:
                continue
            if from_dt and start < from_dt:
                continue
            if to_dt and start > to_dt:
                continue
            filtered.append(e)
        events = filtered

    events = sorted(events, key=lambda e: e.get("start_at", ""))
    return {"events": events, "total": len(events)}


@router.get("/calendar/{event_id}")
async def get_calendar_event(event_id: str):
    item = get_item("calendar_events", event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return item


@router.post("/calendar")
async def create_calendar_event(payload: dict):
    payload.setdefault("title", "Nowe wydarzenie")
    payload.setdefault("event_type", "meeting")
    payload.setdefault("status", "scheduled")
    payload.setdefault("description", "")
    payload.setdefault("reminder_minutes", 15)
    if not payload.get("start_at"):
        payload["start_at"] = datetime.utcnow().replace(minute=0, second=0, microsecond=0).isoformat()
    if not payload.get("end_at"):
        payload["end_at"] = (datetime.fromisoformat(payload["start_at"]) + timedelta(hours=1)).isoformat()

    item = create_item("calendar_events", payload)
    create_item("audit_logs", {"entity": "calendar_event", "entity_id": item["id"], "action": "create", "changes": payload, "actor": "system"})
    return item


@router.patch("/calendar/{event_id}")
async def patch_calendar_event(event_id: str, payload: dict):
    item = update_item("calendar_events", event_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    create_item("audit_logs", {"entity": "calendar_event", "entity_id": event_id, "action": "update", "changes": payload, "actor": "system"})
    return item


@router.delete("/calendar/{event_id}")
async def remove_calendar_event(event_id: str):
    if not delete_item("calendar_events", event_id):
        raise HTTPException(status_code=404, detail="Calendar event not found")
    create_item("audit_logs", {"entity": "calendar_event", "entity_id": event_id, "action": "delete", "changes": {}, "actor": "system"})
    return {"status": "deleted"}


@router.get("/workflow/followups")
async def list_followups():
    tasks = [t for t in list_items("tasks") if t.get("follow_up") and t.get("status") != "completed"]
    return {"items": tasks}


@router.post("/workflow/followups/{task_id}/remind")
async def set_followup_reminder(task_id: str, payload: dict):
    remind_at = payload.get("reminder_at")
    if not remind_at:
        raise HTTPException(status_code=400, detail="reminder_at is required")
    item = update_item("tasks", task_id, {"reminder_at": remind_at, "follow_up": True})
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    return item


@router.get("/leads")
async def list_leads(status: str | None = None):
    leads = list_items("leads")
    if status:
        leads = [l for l in leads if l.get("status") == status]
    return {"leads": leads}


@router.post("/leads")
async def create_lead(payload: dict):
    payload.setdefault("status", "new")
    payload.setdefault("score", 50)
    if payload["status"] not in LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid lead status: {payload['status']}")
    lead = create_item("leads", payload)
    create_item("audit_logs", {"entity": "lead", "entity_id": lead["id"], "action": "create", "changes": payload, "actor": "system"})
    return lead


@router.patch("/leads/{lead_id}")
async def update_lead(lead_id: str, payload: dict):
    if "status" in payload and payload["status"] not in LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid lead status: {payload['status']}")
    if "score" in payload:
        payload["score"] = max(0, min(100, int(payload["score"])))
    lead = update_item("leads", lead_id, payload)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    create_item("audit_logs", {"entity": "lead", "entity_id": lead_id, "action": "update", "changes": payload, "actor": "system"})
    return lead


@router.post("/leads/{lead_id}/convert")
async def convert_lead(lead_id: str, payload: dict = Body(default={})):
    lead = get_item("leads", lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.get("status") == "won":
        raise HTTPException(status_code=409, detail="Lead już został skonwertowany")

    owner_id = payload.get("owner_id") or lead.get("owner_id") or "admin-1"

    company = None
    company_id = payload.get("company_id")
    company_name = payload.get("company_name") or lead.get("company_name")
    if company_id:
        company = get_item("companies", company_id)
    elif company_name:
        existing_company = next((c for c in list_items("companies") if (c.get("name") or "").strip().lower() == company_name.strip().lower()), None)
        company = existing_company or create_item("companies", {"name": company_name, "owner_id": owner_id})

    contact_payload = {
        "name": payload.get("contact_name") or lead.get("name") or lead.get("contact_name"),
        "email": payload.get("email") or lead.get("email"),
        "phone": payload.get("phone") or lead.get("phone"),
        "type": "client",
        "owner_id": owner_id,
        "company_id": company.get("id") if company else None,
        "source": lead.get("source"),
    }

    dup = _find_duplicate_contact(contact_payload.get("email"), contact_payload.get("phone"))
    contact = dup or create_item("contacts", contact_payload)

    deal_stage = payload.get("stage") or "qualification"
    if deal_stage not in DEAL_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid deal stage: {deal_stage}")

    deal = create_item("deals", {
        "title": payload.get("deal_title") or f"{contact.get('name') or 'Nowa szansa'} - {lead.get('source') or 'Lead'}",
        "contact_id": contact.get("id"),
        "company_id": company.get("id") if company else None,
        "owner_id": owner_id,
        "value": payload.get("value") or lead.get("value"),
        "currency": payload.get("currency") or "PLN",
        "status": "open",
        "stage": deal_stage,
        "probability": int(payload.get("probability") or 20),
        "expected_close_date": payload.get("expected_close_date"),
        "next_step": payload.get("next_step") or "Pierwszy kontakt handlowy",
        "source_lead_id": lead_id,
    })

    followup_due = payload.get("followup_due_date") or (datetime.utcnow() + timedelta(days=1)).isoformat()
    task = create_item("tasks", {
        "title": f"Follow-up lead: {contact.get('name') or contact.get('id')}",
        "description": "Kontakt po konwersji leada",
        "status": "pending",
        "priority": "high",
        "assigned_to": owner_id,
        "due_date": followup_due,
        "related_type": "deal",
        "related_id": deal.get("id"),
        "follow_up": True,
    })

    update_item("leads", lead_id, {"status": "won", "converted_at": datetime.utcnow().isoformat(), "converted_contact_id": contact.get("id"), "converted_deal_id": deal.get("id")})
    create_item("audit_logs", {"entity": "lead", "entity_id": lead_id, "action": "convert", "changes": {"contact_id": contact.get("id"), "deal_id": deal.get("id")}, "actor": "system"})
    _notify("Konwersja leada", f"Lead {lead.get('name') or lead_id} -> kontakt i szansa", "lead_converted", "lead", lead_id)

    return {"lead": get_item("leads", lead_id), "contact": contact, "deal": deal, "task": task}


@router.get("/companies")
async def list_companies():
    return {"companies": list_items("companies")}


@router.post("/companies")
async def create_company(payload: dict, authorization: str | None = Header(default=None)):
    _require_roles(authorization, {"admin", "agent"})
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Company name is required")
    exists = next((c for c in list_items("companies") if (c.get("name") or "").strip().lower() == name.lower()), None)
    if exists:
        raise HTTPException(status_code=409, detail="Company already exists")
    company = create_item("companies", payload)
    return company


@router.get("/deals")
async def list_deals(status: str | None = None, stage: str | None = None, owner_id: str | None = None, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent", "user"})
    deals = list_items("deals")
    if status:
        deals = [d for d in deals if d.get("status") == status]
    if stage:
        deals = [d for d in deals if d.get("stage") == stage]
    if owner_id:
        deals = [d for d in deals if d.get("owner_id") == owner_id]
    if user.get("role") != "admin":
        deals = [d for d in deals if _can_access_record(user, d)]
    return {"deals": deals, "total": len(deals)}


@router.post("/deals")
async def create_deal(payload: dict, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    payload.setdefault("status", "open")
    payload.setdefault("stage", "qualification")
    payload.setdefault("probability", 20)
    payload.setdefault("currency", "PLN")

    payload = _validate_deal_payload(payload)
    payload.setdefault("owner_id", user.get("user_id"))

    if not payload.get("title"):
        raise HTTPException(status_code=400, detail="title is required")

    deal = create_item("deals", payload)
    create_item("audit_logs", {"entity": "deal", "entity_id": deal["id"], "action": "create", "changes": payload, "actor": "system"})
    return deal


@router.patch("/deals/{deal_id}")
async def update_deal(deal_id: str, payload: dict, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    current = get_item("deals", deal_id)
    if not current:
        raise HTTPException(status_code=404, detail="Deal not found")
    if not _can_access_record(user, current):
        raise HTTPException(status_code=403, detail="Brak dostępu do szansy")

    payload = _validate_deal_payload(payload, current=current)

    updated = update_item("deals", deal_id, payload)
    create_item("audit_logs", {"entity": "deal", "entity_id": deal_id, "action": "update", "changes": payload, "actor": "system"})

    if payload.get("stage") and payload.get("stage") != current.get("stage"):
        create_item("activities", {
            "type": "deal_stage_changed",
            "deal_id": deal_id,
            "from_stage": current.get("stage"),
            "to_stage": payload.get("stage"),
            "owner_id": updated.get("owner_id"),
        })
        if payload.get("next_step"):
            create_item("tasks", {
                "title": f"Next step: {payload.get('next_step')}",
                "status": "pending",
                "priority": "medium",
                "assigned_to": updated.get("owner_id") or "admin-1",
                "related_type": "deal",
                "related_id": deal_id,
                "due_date": payload.get("expected_close_date") or (datetime.utcnow() + timedelta(days=2)).isoformat(),
            })

    return updated


@router.get("/tickets")
async def list_tickets(status: str | None = None, priority: str | None = None, assigned_to: str | None = None, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent", "user"})
    tickets = list_items("tickets")
    if status:
        tickets = [t for t in tickets if t.get("status") == status]
    if priority:
        tickets = [t for t in tickets if t.get("priority") == priority]
    if assigned_to:
        tickets = [t for t in tickets if t.get("assigned_to") == assigned_to]
    if user.get("role") != "admin":
        tickets = [t for t in tickets if _can_access_record(user, t)]

    now = datetime.utcnow()
    for t in tickets:
        due = _parse_dt(t.get("due_at"))
        t["sla_breached"] = bool(due and due < now and t.get("status") not in {"resolved", "closed"})

    return {"tickets": tickets, "total": len(tickets)}


@router.post("/tickets")
async def create_ticket(payload: dict, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent", "user"})
    payload.setdefault("status", "new")
    payload.setdefault("priority", "medium")
    if payload["status"] not in TICKET_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid ticket status: {payload['status']}")
    if payload["priority"] not in TICKET_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid ticket priority: {payload['priority']}")
    if not payload.get("title"):
        raise HTTPException(status_code=400, detail="title is required")

    payload.setdefault("due_at", _ticket_due_by_priority(payload["priority"]))
    payload.setdefault("owner_id", user.get("user_id"))
    ticket = create_item("tickets", payload)
    create_item("audit_logs", {"entity": "ticket", "entity_id": ticket["id"], "action": "create", "changes": payload, "actor": "system"})
    return ticket


@router.patch("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, payload: dict, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    current = get_item("tickets", ticket_id)
    if not current:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not _can_access_record(user, current):
        raise HTTPException(status_code=403, detail="Brak dostępu do zgłoszenia")
    if "status" in payload and payload["status"] not in TICKET_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid ticket status: {payload['status']}")
    if "priority" in payload and payload["priority"] not in TICKET_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid ticket priority: {payload['priority']}")
    ticket = update_item("tickets", ticket_id, payload)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    create_item("audit_logs", {"entity": "ticket", "entity_id": ticket_id, "action": "update", "changes": payload, "actor": "system"})
    return ticket


@router.get("/properties")
async def list_properties(status: str | None = None, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent", "user"})
    items = list_items("properties")
    if status:
        items = [p for p in items if p.get("crm_status") == status]
    if user.get("role") != "admin":
        items = [p for p in items if _can_access_record(user, p)]
    return {"properties": items, "total": len(items)}


@router.post("/properties")
async def create_property(payload: dict, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    payload.setdefault("crm_status", "draft")
    payload.setdefault("is_active", True)
    if payload.get("crm_status") not in PROPERTY_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid crm_status")
    if not payload.get("title"):
        raise HTTPException(status_code=400, detail="title is required")
    if payload.get("price") is None:
        raise HTTPException(status_code=400, detail="price is required")
    payload.setdefault("owner_id", user.get("user_id"))
    prop = create_item("properties", payload)
    return prop


@router.patch("/properties/{property_id}")
async def update_property(property_id: str, payload: dict, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    current = get_item("properties", property_id)
    if not current:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, current):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    if "crm_status" in payload and payload["crm_status"] not in PROPERTY_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid crm_status")

    updated = update_item("properties", property_id, payload)

    # automatyczne kolejki
    status = updated.get("crm_status")
    if status == "ready_for_publish":
        enqueue_publication_job(property_id, "create_listing", requested_by="auto")
    elif status == "update_required":
        enqueue_publication_job(property_id, "update_listing", requested_by="auto")
    elif status in {"sold", "archived"}:
        enqueue_publication_job(property_id, "deactivate_listing", requested_by="auto")

    return updated


@router.get("/properties/{property_id}")
async def get_property(property_id: str, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent", "user"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    return prop


@router.get("/properties/{property_id}/images")
async def list_property_images(property_id: str, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent", "user"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    images = [i for i in list_items("property_images") if i.get("property_id") == property_id]
    images = sorted(images, key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))
    return {"images": images, "total": len(images)}


@router.post("/properties/{property_id}/images")
async def add_property_image(property_id: str, payload: dict, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    if not payload.get("file_url"):
        raise HTTPException(status_code=400, detail="file_url is required")
    payload["property_id"] = property_id
    payload.setdefault("sort_order", 0)
    payload.setdefault("is_cover", False)
    img = create_item("property_images", payload)
    return img


@router.post("/api/properties/{property_id}/publish/otodom")
async def publish_property_otodom(property_id: str, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")

    images = [i for i in list_items("property_images") if i.get("property_id") == property_id]
    v = validate_property_for_publish(prop, images)
    if not v.ok:
        update_item("properties", property_id, {"crm_status": "publish_error"})
        raise HTTPException(status_code=400, detail={"message": "Validation failed", "missing": v.missing_fields, "errors": v.errors})

    update_item("properties", property_id, {"crm_status": "ready_for_publish"})
    job = enqueue_publication_job(property_id, "create_listing", requested_by=user.get("user_id") or "unknown")
    return {"status": "queued", "job": job}


@router.post("/api/properties/{property_id}/sync/otodom")
async def sync_property_otodom(property_id: str, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    update_item("properties", property_id, {"crm_status": "update_required"})
    job = enqueue_publication_job(property_id, "update_listing", requested_by=user.get("user_id") or "unknown")
    return {"status": "queued", "job": job}


@router.post("/api/properties/{property_id}/unpublish/otodom")
async def unpublish_property_otodom(property_id: str, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    update_item("properties", property_id, {"crm_status": "archived", "is_active": False})
    job = enqueue_publication_job(property_id, "deactivate_listing", requested_by=user.get("user_id") or "unknown")
    return {"status": "queued", "job": job}


@router.get("/api/properties/{property_id}/publication/otodom")
async def get_property_otodom_publication(property_id: str, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    publication = next((p for p in list_items("property_publications") if p.get("property_id") == property_id and p.get("portal") == "otodom"), None)
    if not publication:
        return {"publication_status": "not_published", "external_listing_id": None}

    jobs = [j for j in list_items("publication_jobs") if j.get("property_id") == property_id and j.get("portal") == "otodom"]
    attempts = sum(int(j.get("attempts") or 0) for j in jobs)
    return {
        "publication_status": publication.get("publication_status"),
        "external_listing_id": publication.get("external_listing_id"),
        "last_synced_at": publication.get("last_synced_at"),
        "last_error": publication.get("last_error"),
        "attempts": attempts,
    }


@router.get("/api/properties/{property_id}/publication/otodom/logs")
async def get_property_otodom_logs(property_id: str, authorization: str | None = Header(default=None)):
    user = _require_roles(authorization, {"admin", "agent"})
    prop = get_item("properties", property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not _can_access_record(user, prop):
        raise HTTPException(status_code=403, detail="Brak dostępu do oferty")
    logs = [
        l for l in list_items("audit_logs")
        if l.get("entity") == "otodom_publication" and l.get("entity_id") == property_id
    ]
    jobs = [j for j in list_items("publication_jobs") if j.get("property_id") == property_id and j.get("portal") == "otodom"]
    return {"logs": logs, "jobs": jobs}


@router.post("/api/publications/otodom/process-jobs")
async def process_otodom_jobs(authorization: str | None = Header(default=None), limit: int = Query(default=20, ge=1, le=100)):
    _require_roles(authorization, {"admin"})
    return await process_due_jobs(limit)


@router.post("/api/properties/migrate-from-listings")
async def migrate_properties_from_listings(authorization: str | None = Header(default=None), limit: int = Query(default=200, ge=1, le=2000)):
    user = _require_roles(authorization, {"admin"})
    listings = list_items("listings")[:limit]
    created = 0

    for l in listings:
        ext_id = str(l.get("id"))
        exists = next((p for p in list_items("properties") if str(p.get("source_listing_id")) == ext_id), None)
        if exists:
            continue

        status_map = {
            "draft": "draft",
            "published": "published",
            "active": "published",
            "sold": "sold",
            "inactive": "archived",
            "archived": "archived",
            "reserved": "paused",
        }
        crm_status = status_map.get((l.get("status") or "").lower(), "draft")

        create_item("properties", {
            "source_listing_id": ext_id,
            "title": l.get("title") or "Bez tytułu",
            "description": l.get("description") or "",
            "offer_type": l.get("transaction_type") or "sale",
            "property_type": l.get("property_type") or "apartment",
            "market_type": l.get("market_type") or "secondary",
            "price": l.get("price") or 0,
            "area": l.get("area_sqm"),
            "rooms": l.get("rooms"),
            "floor": l.get("floor"),
            "total_floors": l.get("total_floors"),
            "year_built": l.get("year_built"),
            "city": l.get("city"),
            "district": l.get("district"),
            "street": l.get("street"),
            "country": "PL",
            "is_active": crm_status not in {"archived", "sold"},
            "crm_status": crm_status,
            "owner_id": user.get("user_id"),
        })
        created += 1

    return {"status": "ok", "created": created, "scanned": len(listings)}


@router.get("/documents")
async def list_documents(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
):
    docs = list_items("documents")

    # Global stats (full dataset)
    total_size = sum(int(d.get("size_bytes") or 0) for d in docs)
    stats = {
        "total": len(docs),
        "pdf": sum(1 for d in docs if d.get("mime_type") == "application/pdf"),
        "images": sum(1 for d in docs if str(d.get("mime_type") or "").startswith("image/")),
        "total_size_bytes": total_size,
    }

    filtered = docs
    if q:
        qq = q.strip().lower()
        filtered = [
            d for d in docs
            if qq in str(d.get("name") or "").lower() or qq in str(d.get("related_to") or "").lower()
        ]

    total = len(filtered)
    page_docs = filtered[offset: offset + limit]
    safe_docs = [_safe_doc_record(d) for d in page_docs]

    return {
        "documents": safe_docs,
        "stats": stats,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/documents/stats")
async def documents_stats():
    docs = list_items("documents")
    total_size = sum(int(d.get("size_bytes") or 0) for d in docs)
    return {
        "total": len(docs),
        "pdf": sum(1 for d in docs if d.get("mime_type") == "application/pdf"),
        "images": sum(1 for d in docs if str(d.get("mime_type") or "").startswith("image/")),
        "total_size_bytes": total_size,
    }


@router.post("/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...), related_to: str | None = None):
    uploaded = []
    errors = []

    for f in files:
        mime = f.content_type or mimetypes.guess_type(f.filename or "")[0] or "application/octet-stream"
        if mime not in ALLOWED_DOC_MIME:
            errors.append({"file": f.filename, "error": f"Unsupported mime type: {mime}"})
            continue

        data = await f.read()
        size = len(data)
        if size > MAX_DOC_SIZE:
            errors.append({"file": f.filename, "error": "File too large (max 50MB)"})
            continue

        doc_id = f"doc-{datetime.utcnow().timestamp()}-{len(uploaded)}"
        ext = Path(f.filename or "file").suffix or ".bin"
        storage_name = f"{doc_id}{ext}"
        storage_path = DOCS_DIR / storage_name
        storage_path.write_bytes(data)

        rec = create_item("documents", {
            "name": f.filename or storage_name,
            "mime_type": mime,
            "size_bytes": size,
            "uploaded_by": "admin",
            "related_to": related_to or "",
            "storage_path": str(storage_path),
            "extension": ext.lower().lstrip('.'),
        })
        create_item("audit_logs", {"entity": "document", "entity_id": rec["id"], "action": "upload", "changes": {"name": rec.get("name")}, "actor": "system"})
        uploaded.append(_safe_doc_record(rec))

    return {"uploaded": uploaded, "errors": errors}


@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str):
    doc = get_item("documents", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(doc.get("storage_path") or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on storage")

    return FileResponse(path=str(path), filename=doc.get("name") or path.name, media_type=doc.get("mime_type") or "application/octet-stream")


@router.post("/documents/bulk-download")
async def bulk_download_documents(payload: dict = Body(default={})):
    ids = payload.get("ids") or []
    if not ids:
        raise HTTPException(status_code=400, detail="ids are required")

    docs = [get_item("documents", i) for i in ids]
    docs = [d for d in docs if d]
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")

    tmp_zip = DOCS_DIR / f"bulk-{datetime.utcnow().timestamp()}.zip"
    with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in docs:
            p = Path(d.get("storage_path") or "")
            if p.exists():
                zf.write(p, arcname=d.get("name") or p.name)

    return FileResponse(path=str(tmp_zip), filename="documents.zip", media_type="application/zip")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    doc = get_item("documents", doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(doc.get("storage_path") or "")
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass

    delete_item("documents", doc_id)
    create_item("audit_logs", {"entity": "document", "entity_id": doc_id, "action": "delete", "changes": {}, "actor": "system"})
    return {"status": "deleted"}


@router.post("/documents/bulk-delete")
async def bulk_delete_documents(payload: dict = Body(default={})):
    ids = payload.get("ids") or []
    deleted = 0
    for doc_id in ids:
        doc = get_item("documents", doc_id)
        if not doc:
            continue
        p = Path(doc.get("storage_path") or "")
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
        if delete_item("documents", doc_id):
            deleted += 1
            create_item("audit_logs", {"entity": "document", "entity_id": doc_id, "action": "bulk-delete", "changes": {}, "actor": "system"})
    return {"deleted": deleted}


@router.delete("/documents")
async def delete_all_documents(confirm: bool = Query(default=False), authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true is required")

    docs = list_items("documents")
    for d in docs:
        p = Path(d.get("storage_path") or "")
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
        delete_item("documents", d.get("id"))

    create_item("audit_logs", {"entity": "document", "entity_id": "*", "action": "delete-all", "changes": {}, "actor": "system"})
    return {"status": "deleted_all", "count": len(docs)}


@router.get("/audit-logs")
async def list_audit_logs(limit: int = Query(default=100, ge=1, le=500), authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    logs = list_items("audit_logs")
    return {"items": logs[:limit], "total": len(logs)}


@router.get("/roles")
async def list_roles(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return {
        "roles": [
            {"name": "admin", "permissions": ["*"]},
            {"name": "agent", "permissions": ["listings.read", "listings.write", "contacts.*", "tasks.*", "leads.*"]},
            {"name": "assistant", "permissions": ["listings.read", "contacts.read", "tasks.read", "tasks.write"]},
        ]
    }


@router.get("/notifications")
async def list_notifications(
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
):
    await _sync_offer_notifications(session)
    items = list_items("notifications")
    items_sorted = sorted(items, key=lambda n: n.get("created_at", ""), reverse=True)
    if unread_only:
        items_sorted = [n for n in items_sorted if not n.get("is_read")]

    unread_count = sum(1 for n in items if not n.get("is_read"))
    total = len(items_sorted)
    page = items_sorted[offset: offset + limit]
    return {"items": page, "total": total, "unread_count": unread_count, "limit": limit, "offset": offset}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    item = update_item("notifications", notification_id, {"is_read": True})
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return item


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read():
    items = list_items("notifications")
    updated = 0
    for n in items:
        if not n.get("is_read"):
            update_item("notifications", n["id"], {"is_read": True})
            updated += 1
    return {"updated": updated}


def _get_current_user_from_auth(authorization: str | None):
    if not authorization:
        raise HTTPException(status_code=401, detail="Brak tokena")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    token_data = _verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")
    user = next((u for u in list_items("users") if u.get("id") == token_data.get("user_id")), None)
    if not user:
        raise HTTPException(status_code=401, detail="Użytkownik nie istnieje")
    return user


def _get_or_create_profile_for_user(user: dict):
    profiles = list_items("profile")
    user_id = user.get("id")
    profile = next((p for p in profiles if p.get("user_id") == user_id), None)
    if profile:
        return profile
    return create_item("profile", {
        "user_id": user_id,
        "name": user.get("name") or user.get("email") or "Użytkownik",
        "email": user.get("email"),
        "avatar_url": user.get("avatar_url"),
        "cover_url": None,
    })


@router.get("/profile")
async def get_profile(authorization: str | None = Header(default=None)):
    user = _get_current_user_from_auth(authorization)
    row = _get_or_create_profile_for_user(user)
    row.setdefault("avatar_url", user.get("avatar_url"))
    row.setdefault("cover_url", None)
    row["name"] = row.get("name") or user.get("name") or user.get("email")
    row["email"] = user.get("email")
    return row


@router.get("/user/profile")
async def get_user_profile(authorization: str | None = Header(default=None)):
    return await get_profile(authorization)


@router.post("/profile/avatar")
async def upload_avatar(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    user = _get_current_user_from_auth(authorization)

    mime = file.content_type or ""
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Unsupported avatar format")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Avatar too large (max 10MB)")

    avatars_dir = DOCS_DIR / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "avatar").suffix or ".jpg"
    safe_user_id = (user.get("id") or "user").replace("/", "_")
    avatar_path = avatars_dir / f"{safe_user_id}{ext}"
    avatar_path.write_bytes(data)

    avatar_url = f"/api/static/avatars/{avatar_path.name}"
    profile = _get_or_create_profile_for_user(user)
    update_item("profile", profile["id"], {"avatar_url": avatar_url, "name": user.get("name") or profile.get("name"), "email": user.get("email")})
    update_item("users", user["id"], {"avatar_url": avatar_url})
    return get_item("profile", profile["id"])


@router.get("/static/avatars/{filename}")
async def get_avatar_file(filename: str):
    avatars_dir = DOCS_DIR / "avatars"
    p = avatars_dir / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(path=str(p), filename=p.name)


@router.post("/user/cover")
async def upload_cover(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    user = _get_current_user_from_auth(authorization)

    mime = file.content_type or ""
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Unsupported cover format")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Cover too large (max 10MB)")

    covers_dir = DOCS_DIR / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "cover").suffix or ".jpg"
    safe_user_id = (user.get("id") or "user").replace("/", "_")
    cover_path = covers_dir / f"{safe_user_id}-cover{ext}"
    cover_path.write_bytes(data)

    cover_url = f"/api/static/covers/{cover_path.name}"
    profile = _get_or_create_profile_for_user(user)
    update_item("profile", profile["id"], {"cover_url": cover_url, "name": user.get("name") or profile.get("name"), "email": user.get("email")})
    return get_item("profile", profile["id"])


@router.delete("/user/cover")
async def remove_cover(authorization: str | None = Header(default=None)):
    user = _get_current_user_from_auth(authorization)
    profile = next((p for p in list_items("profile") if p.get("user_id") == user.get("id")), None)
    if not profile:
        return {"status": "ok"}

    cover_url = profile.get("cover_url")
    if cover_url and cover_url.startswith("/api/static/covers/"):
        fname = cover_url.split("/")[-1]
        fp = DOCS_DIR / "covers" / fname
        if fp.exists():
            try:
                fp.unlink()
            except Exception:
                pass

    update_item("profile", profile["id"], {"cover_url": None})
    return {"status": "ok"}


@router.get("/static/covers/{filename}")
async def get_cover_file(filename: str):
    covers_dir = DOCS_DIR / "covers"
    p = covers_dir / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Cover not found")
    return FileResponse(path=str(p), filename=p.name)


@router.get("/auth/bootstrap-status")
async def auth_bootstrap_status():
    try:
        users = list_items("users")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Storage unavailable: {str(e)}")
    return {
        "users_count": len(users),
        "requires_bootstrap": len(users) == 0,
        "hint": "Użyj POST /auth/bootstrap-admin z nagłówkiem X-Bootstrap-Token" if len(users) == 0 else "System gotowy",
    }


@router.post("/auth/bootstrap-admin")
async def auth_bootstrap_admin(payload: dict, x_bootstrap_token: str | None = Header(default=None)):
    users = list_items("users")
    if users:
        raise HTTPException(status_code=409, detail="Bootstrap już wykonany")

    expected = os.getenv("CRM_BOOTSTRAP_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="CRM_BOOTSTRAP_TOKEN nie jest ustawiony na serwerze")
    if not x_bootstrap_token or not hmac.compare_digest(x_bootstrap_token, expected):
        raise HTTPException(status_code=401, detail="Nieprawidłowy bootstrap token")

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    name = (payload.get("name") or "Administrator").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Poprawny email jest wymagany")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Hasło musi mieć min. 8 znaków")

    user = create_item("users", {
        "email": email,
        "password_hash": _safe_hash_password(password),
        "role": "admin",
        "name": name,
        "avatar_url": None,
        "last_login": None,
        "is_active": True,
    })
    return {"status": "bootstrapped", "user": _public_user(user)}


@router.post("/auth/register")
async def auth_register(payload: dict, request: Request):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or ""
    name = (payload.get("name") or "").strip() or None
    role = (payload.get("role") or "user").strip().lower()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Poprawny email jest wymagany")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Hasło musi mieć min. 8 znaków")
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Hasła nie są takie same")
    if role not in {"admin", "agent", "user"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = _find_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="Użytkownik o tym emailu już istnieje")

    # role admin tylko dla aktualnego admina
    if role == "admin":
        auth_header = request.headers.get("authorization")
        data = _require_admin(auth_header)
        if data.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Brak uprawnień do tworzenia admina")

    user = create_item("users", {
        "email": email,
        "password_hash": _safe_hash_password(password),
        "role": role,
        "name": name,
        "avatar_url": None,
        "last_login": None,
        "is_active": True,
    })
    create_item("audit_logs", {"entity": "user", "entity_id": user["id"], "action": "register", "changes": {"email": email, "role": role}, "actor": "system"})

    token = _issue_token(user["id"], user.get("role") or "user", user.get("email") or email)
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_TTL_SECONDS, "user": _public_user(user)}


@router.post("/auth/login")
async def auth_login(payload: dict, request: Request):
    email = (payload.get("email") or payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="Login i hasło są wymagane")

    users = list_items("users")
    if not users:
        raise HTTPException(status_code=409, detail="Brak kont w systemie. Wykonaj bootstrap administratora.")

    identity = f"{email}:{request.client.host if request.client else 'unknown'}"
    _check_login_rate_limit(identity)

    user = _find_user_by_email(email)
    if not user or not _verify_password(password, user.get("password_hash") or ""):
        _register_login_failure(identity)
        raise HTTPException(status_code=401, detail="Nieprawidłowy login lub hasło")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Konto nieaktywne")

    _clear_login_failures(identity)
    update_item("users", user["id"], {"last_login": datetime.utcnow().isoformat()})

    token = _issue_token(user["id"], user.get("role") or "user", user.get("email") or email)
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_TTL_SECONDS, "user": _public_user(user)}


@router.post("/auth/logout")
async def auth_logout():
    return {"status": "ok"}


@router.get("/auth/me")
async def auth_me(authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Brak tokena")
    if authorization.lower().startswith("bearer "):
        authorization = authorization[7:]

    data = _verify_token(authorization)
    if not data:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")

    user = next((u for u in list_items("users") if u.get("id") == data.get("user_id")), None)
    if not user:
        raise HTTPException(status_code=401, detail="Użytkownik nie istnieje")

    return _public_user(user)


@router.post("/auth/change-password")
async def change_password(payload: dict, authorization: str | None = Header(default=None)):
    current = payload.get("current_password")
    new = payload.get("new_password")
    confirm = payload.get("confirm_password")

    if not current or not new or not confirm:
        raise HTTPException(status_code=400, detail="Wszystkie pola hasła są wymagane")
    if len(new) < 8:
        raise HTTPException(status_code=400, detail="Nowe hasło musi mieć min. 8 znaków")
    if new != confirm:
        raise HTTPException(status_code=400, detail="Potwierdzenie hasła nie pasuje")

    if not authorization:
        raise HTTPException(status_code=401, detail="Brak tokena")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    data = _verify_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")

    user = next((u for u in list_items("users") if u.get("id") == data.get("user_id")), None)
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")

    if not _verify_password(current, user.get("password_hash") or ""):
        raise HTTPException(status_code=400, detail="Aktualne hasło jest niepoprawne")

    update_item("users", user["id"], {"password_hash": _safe_hash_password(new)})
    return {"status": "ok", "message": "Hasło zostało zmienione pomyślnie."}


@router.post("/auth/reset-password")
async def reset_password(payload: dict):
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email jest wymagany")

    user = _find_user_by_email(email)
    # bez ujawniania czy user istnieje
    if not user:
        return {"status": "ok"}

    token_plain = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token_plain.encode("utf-8")).hexdigest()
    create_item("password_reset_tokens", {
        "user_id": user["id"],
        "token_hash": token_hash,
        "expires_at": (datetime.utcnow() + timedelta(minutes=30)).isoformat(),
        "used": False,
    })

    # TODO: podpiąć wysyłkę email; na razie zwracamy token dla flow operatorskiego
    return {"status": "ok", "reset_token": token_plain, "expires_in_minutes": 30}


@router.get("/auth/admin/users")
async def admin_list_users(authorization: str | None = Header(default=None)):
    _require_roles(authorization, {"admin"})
    users = [_public_user(u) for u in list_items("users")]
    return {"users": users, "total": len(users)}


@router.post("/auth/admin/users/{user_id}/activate")
async def admin_activate_user(user_id: str, authorization: str | None = Header(default=None)):
    _require_roles(authorization, {"admin"})
    user = get_item("users", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")
    updated = update_item("users", user_id, {"is_active": True})
    create_item("audit_logs", {"entity": "user", "entity_id": user_id, "action": "activate", "changes": {}, "actor": "admin"})
    return _public_user(updated)


@router.post("/auth/admin/users/{user_id}/deactivate")
async def admin_deactivate_user(user_id: str, authorization: str | None = Header(default=None)):
    _require_roles(authorization, {"admin"})
    user = get_item("users", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")
    updated = update_item("users", user_id, {"is_active": False})
    create_item("audit_logs", {"entity": "user", "entity_id": user_id, "action": "deactivate", "changes": {}, "actor": "admin"})
    return _public_user(updated)


@router.post("/auth/admin/users/{user_id}/role")
async def admin_change_user_role(user_id: str, payload: dict, authorization: str | None = Header(default=None)):
    _require_roles(authorization, {"admin"})
    role = (payload.get("role") or "").strip().lower()
    if role not in {"admin", "agent", "user"}:
        raise HTTPException(status_code=400, detail="Nieprawidłowa rola")
    user = get_item("users", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")
    updated = update_item("users", user_id, {"role": role})
    create_item("audit_logs", {"entity": "user", "entity_id": user_id, "action": "role_change", "changes": {"role": role}, "actor": "admin"})
    return _public_user(updated)


@router.post("/auth/reset-password/confirm")
async def reset_password_confirm(payload: dict):
    token_plain = payload.get("token") or ""
    new_password = payload.get("new_password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if not token_plain:
        raise HTTPException(status_code=400, detail="token jest wymagany")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Hasło musi mieć min. 8 znaków")
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Hasła nie są takie same")

    token_hash = hashlib.sha256(token_plain.encode("utf-8")).hexdigest()
    rec = next((r for r in list_items("password_reset_tokens") if r.get("token_hash") == token_hash), None)
    if not rec:
        raise HTTPException(status_code=400, detail="Nieprawidłowy token resetu")
    if rec.get("used"):
        raise HTTPException(status_code=400, detail="Token resetu został już użyty")
    if (_parse_dt(rec.get("expires_at")) or datetime.min) < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token resetu wygasł")

    user = next((u for u in list_items("users") if u.get("id") == rec.get("user_id")), None)
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")

    update_item("users", user["id"], {"password_hash": _safe_hash_password(new_password)})
    update_item("password_reset_tokens", rec["id"], {"used": True, "used_at": datetime.utcnow().isoformat()})

    return {"status": "ok", "message": "Hasło zostało zresetowane"}


@router.get("/reports/crm-summary")
async def crm_summary_report(days: int = Query(default=30, ge=1, le=365)):
    now = datetime.utcnow()
    from_dt = now - timedelta(days=days)

    leads = list_items("leads")
    deals = list_items("deals")
    tickets = list_items("tickets")
    contacts = list_items("contacts")

    recent_leads = [l for l in leads if (_parse_dt(l.get("created_at")) or datetime.min) >= from_dt]
    converted_leads = [l for l in recent_leads if l.get("converted_deal_id")]

    won_deals = [d for d in deals if d.get("status") == "won"]
    open_deals = [d for d in deals if d.get("status") == "open"]
    weighted_pipeline = 0.0
    for d in open_deals:
        value = float(d.get("value") or 0)
        probability = int(d.get("probability") or 0)
        weighted_pipeline += value * (probability / 100)

    active_tickets = [t for t in tickets if t.get("status") not in {"resolved", "closed"}]
    now_dt = datetime.utcnow()
    sla_breached = [t for t in active_tickets if (_parse_dt(t.get("due_at")) or datetime.max) < now_dt]

    return {
        "period_days": days,
        "contacts_total": len(contacts),
        "leads_total": len(leads),
        "leads_recent": len(recent_leads),
        "leads_converted_recent": len(converted_leads),
        "lead_conversion_rate_recent": round((len(converted_leads) / len(recent_leads) * 100), 2) if recent_leads else 0.0,
        "deals_total": len(deals),
        "deals_open": len(open_deals),
        "deals_won": len(won_deals),
        "pipeline_weighted_value": round(weighted_pipeline, 2),
        "tickets_total": len(tickets),
        "tickets_open": len(active_tickets),
        "tickets_sla_breached": len(sla_breached),
    }


@router.get("/dashboard")
async def dashboard_payload(session: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    offers_total = int(await session.scalar(select(func.count(Offer.id))) or 0)
    offers_active = int(await session.scalar(select(func.count(Offer.id)).where(Offer.status == "active")) or 0)
    pub_dt = func.coalesce(Offer.source_created_at, Offer.first_seen)
    offers_last_week = int(await session.scalar(select(func.count(Offer.id)).where(pub_dt >= week_ago)) or 0)
    offers_new_today = int(await session.scalar(select(func.count(Offer.id)).where(pub_dt >= today_start)) or 0)

    recent_offers_q = await session.execute(
        select(Offer).order_by(desc(pub_dt)).limit(3)
    )
    recent_offers = [
        {
            "id": str(o.id),
            "title": o.title,
            "city": o.city,
            "region": o.region,
            "price": float(o.price) if o.price is not None else 0,
            "status": str(o.status),
            "created_at": (o.source_created_at or o.first_seen).isoformat() if (o.source_created_at or o.first_seen) else None,
        }
        for o in recent_offers_q.scalars().all()
    ]

    contacts = list_items("contacts")
    tasks = list_items("tasks")
    deals = list_items("deals")
    tickets = list_items("tickets")
    activity = list_items("audit_logs")

    def parse_dt(v: str | None):
        try:
            return datetime.fromisoformat(v) if v else None
        except Exception:
            return None

    actionable_tasks = [t for t in tasks if t.get("status") in {"pending", "in_progress"}]
    pending_tasks = [t for t in tasks if t.get("status") == "pending"]
    pending_tasks_sorted = sorted(
        pending_tasks,
        key=lambda t: (parse_dt(t.get("due_date")) or datetime.max)
    )
    overdue_tasks = [
        t for t in actionable_tasks
        if parse_dt(t.get("due_date")) and parse_dt(t.get("due_date")) < now
    ]

    recent_activity = sorted(
        activity,
        key=lambda a: parse_dt(a.get("created_at")) or datetime.min,
        reverse=True,
    )[:10]

    deals_open = [d for d in deals if d.get("status") == "open"]
    deals_won = [d for d in deals if d.get("status") == "won"]
    weighted_pipeline = 0.0
    for d in deals_open:
        weighted_pipeline += float(d.get("value") or 0) * (int(d.get("probability") or 0) / 100)

    tickets_open = [t for t in tickets if t.get("status") not in {"resolved", "closed"}]
    tickets_sla_breached = [
        t for t in tickets_open
        if (parse_dt(t.get("due_at")) or datetime.max) < now
    ]

    return {
        "offers_total": offers_total,
        "offers_active": offers_active,
        "contacts_total": len(contacts),
        "tasks_pending": len(pending_tasks),
        "tasks_actionable": len(actionable_tasks),
        "tasks_overdue": len(overdue_tasks),
        "offers_last_week": offers_last_week,
        "offers_new_today": offers_new_today,
        "deals_open": len(deals_open),
        "deals_won": len(deals_won),
        "pipeline_weighted_value": round(weighted_pipeline, 2),
        "tickets_open": len(tickets_open),
        "tickets_sla_breached": len(tickets_sla_breached),
        "recent_offers": recent_offers,
        "recent_activity": recent_activity,
        "pending_tasks": pending_tasks_sorted[:5],
    }


@router.get("/dashboard/stats")
async def dashboard_stats(session: AsyncSession = Depends(get_db)):
    payload = await dashboard_payload(session)
    return {
        "total_listings": payload["offers_total"],
        "active_listings": payload["offers_active"],
        "new_this_week": payload["offers_last_week"],
        "price_changes": 0,
        "total_contacts": payload["contacts_total"],
        "pending_tasks": payload["tasks_pending"],
        "overdue_tasks": payload["tasks_overdue"],
        "deals_open": payload.get("deals_open", 0),
        "deals_won": payload.get("deals_won", 0),
        "pipeline_weighted_value": payload.get("pipeline_weighted_value", 0),
        "tickets_open": payload.get("tickets_open", 0),
        "tickets_sla_breached": payload.get("tickets_sla_breached", 0),
    }


@router.get("/dashboard/activity")
async def dashboard_activity(session: AsyncSession = Depends(get_db)):
    payload = await dashboard_payload(session)
    return payload["recent_activity"]
