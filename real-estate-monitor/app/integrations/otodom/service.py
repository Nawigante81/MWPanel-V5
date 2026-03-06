from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict

from app.services.compat_store import create_item, get_item, list_items, update_item

from .client import OtodomClient
from .images import normalize_images
from .logger import logger
from .mapper import map_property_to_otodom_payload
from .types import OtodomPublicationResult
from .validators import validate_property_for_publish


def _env_cfg() -> Dict[str, Any]:
    return {
        "OTODOM_DEFAULT_CONTACT_NAME": os.getenv("OTODOM_DEFAULT_CONTACT_NAME"),
        "OTODOM_DEFAULT_CONTACT_EMAIL": os.getenv("OTODOM_DEFAULT_CONTACT_EMAIL"),
        "OTODOM_DEFAULT_CONTACT_PHONE": os.getenv("OTODOM_DEFAULT_CONTACT_PHONE"),
    }


def _publication_row(property_id: str):
    return next((p for p in list_items("property_publications") if p.get("property_id") == property_id and p.get("portal") == "otodom"), None)


def _upsert_publication(property_id: str, patch: Dict[str, Any]):
    row = _publication_row(property_id)
    if row:
        return update_item("property_publications", row["id"], patch)
    payload = {
        "property_id": property_id,
        "portal": "otodom",
        "publication_status": "pending",
        "external_listing_id": None,
        "last_error": None,
        "last_synced_at": None,
        "payload_json": None,
        "response_json": None,
    }
    payload.update(patch)
    return create_item("property_publications", payload)


def _log(property_id: str, action: str, message: str, extra: Dict[str, Any] | None = None):
    create_item("audit_logs", {
        "entity": "otodom_publication",
        "entity_id": property_id,
        "action": action,
        "changes": {"message": message, **(extra or {})},
        "actor": "system",
    })


class OtodomService:
    async def publish(self, property_id: str) -> OtodomPublicationResult:
        prop = get_item("properties", property_id)
        if not prop:
            return OtodomPublicationResult(False, "publish_error", None, {}, {}, "Property not found")

        images = [i for i in list_items("property_images") if i.get("property_id") == property_id]
        v = validate_property_for_publish(prop, images)
        if not v.ok:
            err = "; ".join([*v.missing_fields, *v.errors])
            update_item("properties", property_id, {"crm_status": "publish_error"})
            _upsert_publication(property_id, {"publication_status": "publish_error", "last_error": err})
            _log(property_id, "publish_validation_error", err)
            return OtodomPublicationResult(False, "publish_error", None, {}, {}, err)

        payload = map_property_to_otodom_payload(prop, _env_cfg())
        publication = _publication_row(property_id)
        external_listing_id = publication.get("external_listing_id") if publication else None

        client = OtodomClient()

        try:
            if external_listing_id:
                response = await client.update_listing(external_listing_id, payload)
                action = "update"
            else:
                response = await client.create_listing(payload)
                action = "create"
                external_listing_id = str(response.get("id") or response.get("listingId") or "")

            if not external_listing_id:
                raise RuntimeError("No external listing id returned by Otodom")

            # upload images after create/update
            normalized_images = normalize_images(images)
            image_upload_results = []
            for img in normalized_images:
                image_upload_results.append(
                    await client.upload_image(
                        external_listing_id,
                        img["file_url"],
                        is_cover=img["is_cover"],
                        sort_order=img["sort_order"],
                    )
                )

            _upsert_publication(property_id, {
                "publication_status": "published",
                "external_listing_id": external_listing_id,
                "last_error": None,
                "last_synced_at": datetime.utcnow().isoformat(),
                "payload_json": payload,
                "response_json": {"listing": response, "images": image_upload_results},
            })
            update_item("properties", property_id, {"crm_status": "published"})
            _log(property_id, f"publish_{action}_ok", "Otodom sync success", {"external_listing_id": external_listing_id})

            return OtodomPublicationResult(True, "published", external_listing_id, payload, response)
        except Exception as e:
            err = str(e)
            _upsert_publication(property_id, {
                "publication_status": "publish_error",
                "last_error": err,
                "last_synced_at": datetime.utcnow().isoformat(),
                "payload_json": payload,
            })
            update_item("properties", property_id, {"crm_status": "publish_error"})
            _log(property_id, "publish_error", err)
            return OtodomPublicationResult(False, "publish_error", external_listing_id, payload, {}, err)

    async def deactivate(self, property_id: str) -> OtodomPublicationResult:
        publication = _publication_row(property_id)
        if not publication or not publication.get("external_listing_id"):
            return OtodomPublicationResult(False, "archived", None, {}, {}, "No external listing id")

        client = OtodomClient()
        ext_id = publication["external_listing_id"]
        try:
            resp = await client.deactivate_listing(ext_id)
            _upsert_publication(property_id, {
                "publication_status": "archived",
                "last_error": None,
                "last_synced_at": datetime.utcnow().isoformat(),
                "response_json": resp,
            })
            update_item("properties", property_id, {"crm_status": "archived", "is_active": False})
            _log(property_id, "deactivate_ok", "Otodom listing deactivated", {"external_listing_id": ext_id})
            return OtodomPublicationResult(True, "archived", ext_id, {}, resp)
        except Exception as e:
            err = str(e)
            _upsert_publication(property_id, {"publication_status": "publish_error", "last_error": err})
            _log(property_id, "deactivate_error", err)
            return OtodomPublicationResult(False, "publish_error", ext_id, {}, {}, err)


def enqueue_publication_job(property_id: str, job_type: str, requested_by: str = "system"):
    # idempotency: avoid duplicate queued/running for same property+type+portal
    existing = next((j for j in list_items("publication_jobs") if j.get("property_id") == property_id and j.get("portal") == "otodom" and j.get("job_type") == job_type and j.get("job_status") in {"queued", "running"}), None)
    if existing:
        return existing

    return create_item("publication_jobs", {
        "property_id": property_id,
        "portal": "otodom",
        "job_type": job_type,
        "job_status": "queued",
        "attempts": 0,
        "max_attempts": int(os.getenv("OTODOM_MAX_RETRIES", "5")),
        "run_after": datetime.utcnow().isoformat(),
        "last_error": None,
        "requested_by": requested_by,
    })


async def process_one_job(job: Dict[str, Any]):
    svc = OtodomService()
    job_id = job["id"]
    property_id = job["property_id"]
    attempts = int(job.get("attempts") or 0)
    max_attempts = int(job.get("max_attempts") or 5)

    update_item("publication_jobs", job_id, {"job_status": "running", "attempts": attempts + 1})

    try:
        if job["job_type"] in {"create_listing", "update_listing"}:
            result = await svc.publish(property_id)
        elif job["job_type"] == "deactivate_listing":
            result = await svc.deactivate(property_id)
        else:
            raise RuntimeError(f"Unknown job_type {job['job_type']}")

        if result.ok:
            update_item("publication_jobs", job_id, {"job_status": "done", "last_error": None})
            return

        raise RuntimeError(result.error or "Unknown Otodom publication error")
    except Exception as e:
        err = str(e)
        next_attempt = attempts + 1
        if next_attempt >= max_attempts:
            update_item("publication_jobs", job_id, {"job_status": "failed", "last_error": err})
            _log(property_id, "job_failed", err, {"job_id": job_id})
            return

        backoff_min = min(30, 2 ** next_attempt)
        run_after = (datetime.utcnow() + timedelta(minutes=backoff_min)).isoformat()
        update_item("publication_jobs", job_id, {"job_status": "queued", "run_after": run_after, "last_error": err})
        _log(property_id, "job_retry", err, {"job_id": job_id, "run_after": run_after})


async def process_due_jobs(limit: int = 20) -> Dict[str, Any]:
    now = datetime.utcnow()
    jobs = [
        j for j in list_items("publication_jobs")
        if j.get("portal") == "otodom"
        and j.get("job_status") == "queued"
        and ((datetime.fromisoformat(j.get("run_after")) if j.get("run_after") else now) <= now)
    ]
    jobs = sorted(jobs, key=lambda x: x.get("created_at", ""))[:limit]

    for job in jobs:
        await process_one_job(job)

    return {"processed": len(jobs)}
