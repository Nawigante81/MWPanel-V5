"""
Celery tasks for scraping real estate listings.
"""
import asyncio
import random
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, List, Optional

from celery import Task
from sqlalchemy import select
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import app.connectors  # noqa: F401  # ensure connector registration side-effects
from app.connectors.base import ConnectorRegistry, FilterConfig
from app.db import get_sync_session
from app.fingerprint import generate_fingerprint
from app.logging_config import get_logger
from app.models import Offer, OfferStatus, ScrapeRun, ScrapeRunStatus, Source
from app.schemas import OfferNormalized
from app.services.circuit_breaker import get_circuit_breaker
from app.services.rate_limit import get_distributed_lock, get_token_bucket
from app.settings import settings
from app.tasks.celery_app import celery_app
from app.tasks.notify import notify_whatsapp

logger = get_logger("tasks.scrape")


def _parse_date_value(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        # heuristic: unix timestamp seconds
        if value > 0:
            try:
                return datetime.utcfromtimestamp(value)
            except Exception:
                return None

    text = str(value).strip()
    if not text:
        return None

    lower = text.lower()
    now = datetime.utcnow()

    # Polish relative dates
    if "dzis" in lower:  # dziś / dzisiaj
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if "wczoraj" in lower:
        d = now - timedelta(days=1)
        return d.replace(hour=0, minute=0, second=0, microsecond=0)

    # ISO / datetime-like
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        pass

    # dd.mm.yyyy / dd-mm-yyyy / dd/mm/yyyy
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", text)
    if m:
        d, mo, y = m.groups()
        year = int(y)
        if year < 100:
            year += 2000
        try:
            return datetime(year, int(mo), int(d))
        except Exception:
            return None

    return None


def _find_candidate_dates(obj: Any) -> List[Any]:
    candidates: List[Any] = []
    date_keys = {
        "source_created_at", "published_at", "publishedAt", "published", "publication_date",
        "date_published", "datePublished", "created_at", "createdAt", "created_time", "createdTime",
        "listing_date", "posted_at", "post_date", "date", "location_date",
    }

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in date_keys:
                candidates.append(v)
            if isinstance(v, (dict, list)):
                candidates.extend(_find_candidate_dates(v))
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                candidates.extend(_find_candidate_dates(item))

    return candidates


def _infer_source_created_at(offer: OfferNormalized) -> Optional[datetime]:
    # explicit normalized value first
    parsed = _parse_date_value(getattr(offer, "source_created_at", None))
    if parsed:
        return parsed

    raw = offer.raw_json or {}
    for candidate in _find_candidate_dates(raw):
        parsed = _parse_date_value(candidate)
        if parsed:
            return parsed

    # fallback: no source date could be extracted
    return None


def _is_invalid_parse(offer: OfferNormalized) -> bool:
    title = (offer.title or "").strip().lower()
    if not title or len(title) < 8:
        return True

    bad_title_tokens = [
        "zobacz inne ogłoszenia",
        "nieruchomości do wynajęcia",
        "nieruchomości z rynku",
        "w sąsiedztwie",
        "sprzedaj z olx",
    ]
    if any(t in title for t in bad_title_tokens):
        return True

    # Wymaganie: brak ceny => NULL + invalid_parse
    if offer.price is None:
        return True

    return False


class ScrapeTask(Task):
    """Base class for scrape tasks with retry configuration."""
    
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True
    max_retries = 3


@celery_app.task(bind=True, base=ScrapeTask)
def scrape_source(self, source_name: str, filter_config: dict) -> dict:
    """
    Scrape a single source with given filters.
    
    This task is:
    - Idempotent: Same source/filter produces same results
    - Rate-limited: Respects per-source rate limits
    - Circuit-breaker protected: Stops on repeated failures
    - Distributed-locked: Prevents duplicate concurrent scrapes
    """
    filter_obj = FilterConfig(**filter_config)
    
    logger.info(
        "Starting scrape task",
        extra={
            "source": source_name,
            "filter": filter_config,
            "task_id": self.request.id,
        },
    )
    
    # Get connector
    connector = ConnectorRegistry.get(source_name)
    if not connector:
        raise ValueError(f"Unknown source: {source_name}")
    
    # Check circuit breaker
    breaker = get_circuit_breaker()
    if not breaker.can_execute(source_name):
        logger.warning(
            "Circuit breaker open, skipping scrape",
            extra={"source": source_name},
        )
        return {
            "source": source_name,
            "status": "skipped",
            "reason": "circuit_breaker_open",
        }
    
    # Acquire distributed lock
    lock_key = f"scrape:{source_name}:{filter_obj.region or 'all'}"
    lock = get_distributed_lock()
    lock_token = lock.acquire(lock_key, ttl_seconds=300)
    
    if not lock_token:
        logger.info(
            "Could not acquire lock, another worker is processing",
            extra={"source": source_name},
        )
        return {
            "source": source_name,
            "status": "skipped",
            "reason": "lock_not_acquired",
        }
    
    try:
        # Rate limiting
        token_bucket = get_token_bucket()
        
        # Get source config for rate limit
        with get_sync_session() as session:
            source = session.execute(
                select(Source).where(Source.name == source_name)
            ).scalar_one_or_none()
            rate_limit = float(source.rate_limit_rps) if source and source.rate_limit_rps is not None else 1.0

        # Wait for rate limit
        asyncio.run(token_bucket.wait_if_needed(source_name, rate_limit))
        
        # Execute scrape
        result = asyncio.run(_execute_scrape(connector, filter_obj, source_name))
        
        # Record success
        breaker.record_success(source_name)
        
        return result
        
    except Exception as e:
        # Record failure
        breaker.record_failure(source_name)
        
        logger.error(
            "Scrape failed",
            extra={
                "source": source_name,
                "error": str(e),
            },
        )
        raise self.retry(exc=e)
        
    finally:
        lock.release(lock_key, lock_token)


async def _execute_scrape(
    connector,
    filter_obj: FilterConfig,
    source_name: str,
) -> dict:
    """Execute the actual scraping logic."""
    
    # Create scrape run record
    scrape_run_id = None
    fetch_mode = connector.fetch_mode
    with get_sync_session() as session:
        source = session.execute(
            select(Source).where(Source.name == source_name)
        ).scalar_one_or_none()

        if not source:
            raise ValueError(f"Source not found in database: {source_name}")

        fetch_mode = str(source.fetch_mode or connector.fetch_mode)

        scrape_run = ScrapeRun(
            source_id=source.id,
            status=ScrapeRunStatus.RUNNING,
        )
        session.add(scrape_run)
        session.flush()
        scrape_run_id = scrape_run.id
    
    offers_found = 0
    offers_new = 0
    error_msg = None
    
    try:
        # Build search URL
        search_url = connector.build_search_url(filter_obj)

        # Fetch content
        if fetch_mode == "playwright":
            content = await connector.fetch_with_playwright(search_url)
        else:
            content = await connector.fetch_with_http(search_url)
        
        # Extract offers
        offers = await connector.extract_offers(content)
        offers_found = len(offers)
        
        # Process offers
        offers_new = _process_offers(offers, source_name, connector, default_region=filter_obj.region)
        
        # Update scrape run
        with get_sync_session() as session:
            scrape_run = session.get(ScrapeRun, scrape_run_id)
            if scrape_run:
                scrape_run.status = ScrapeRunStatus.SUCCESS
                scrape_run.finished_at = datetime.utcnow()
                scrape_run.offers_found = offers_found
                scrape_run.offers_new = offers_new
        
        logger.info(
            "Scrape completed successfully",
            extra={
                "source": source_name,
                "offers_found": offers_found,
                "offers_new": offers_new,
            },
        )
        
        return {
            "source": source_name,
            "status": "success",
            "offers_found": offers_found,
            "offers_new": offers_new,
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Update scrape run with error
        with get_sync_session() as session:
            scrape_run = session.get(ScrapeRun, scrape_run_id)
            if scrape_run:
                scrape_run.status = ScrapeRunStatus.FAILED
                scrape_run.finished_at = datetime.utcnow()
                scrape_run.error = error_msg
                scrape_run.offers_found = offers_found
        
        raise


def _process_offers(
    offers: List[OfferNormalized],
    source_name: str,
    connector,
    default_region: Optional[str] = None,
) -> int:
    """
    Process extracted offers: deduplicate and persist.
    
    Returns:
        Number of new offers inserted
    """
    new_count = 0
    
    with get_sync_session() as session:
        source = session.execute(
            select(Source).where(Source.name == source_name)
        ).scalar_one_or_none()
        
        if not source:
            logger.error(f"Source not found: {source_name}")
            return 0
        
        for offer in offers:
            try:
                # Canonicalize URL
                canonical_url = connector.canonicalize_url(offer.url)
                
                # Generate fingerprint
                fingerprint = generate_fingerprint(
                    source_name,
                    offer,
                    canonical_url,
                )
                
                source_created_at = _infer_source_created_at(offer)
                imported_at = datetime.utcnow()
                invalid_parse = _is_invalid_parse(offer)

                # Check for existing offer
                existing = session.execute(
                    select(Offer).where(Offer.fingerprint == fingerprint)
                ).scalar_one_or_none()
                
                if existing:
                    # Update last_seen/imported_at
                    existing.last_seen = imported_at
                    existing.imported_at = imported_at

                    # Update mutable fields if changed
                    if offer.price and offer.price != existing.price:
                        existing.price = offer.price

                    if (not existing.region) and (offer.region or default_region):
                        existing.region = offer.region or default_region

                    # Backfill publication date from source portal
                    if (not existing.source_created_at) and source_created_at:
                        existing.source_created_at = source_created_at

                    # Promote/demote parse status depending on current parse quality
                    if invalid_parse:
                        existing.status = OfferStatus.INVALID_PARSE
                    elif existing.status == OfferStatus.INVALID_PARSE:
                        existing.status = OfferStatus.ACTIVE

                    # Backfill images when previously missing
                    existing_images = (existing.raw_json or {}).get("images") if existing.raw_json else None
                    incoming_images = (offer.raw_json or {}).get("images") if offer.raw_json else None
                    if (not existing_images) and incoming_images:
                        merged_raw = dict(existing.raw_json or {})
                        merged_raw["images"] = incoming_images
                        existing.raw_json = merged_raw

                    logger.debug(
                        "Offer already exists, updated last_seen",
                        extra={"fingerprint": fingerprint},
                    )
                else:
                    # Insert new offer
                    normalized_region = offer.region or default_region
                    new_offer = Offer(
                        source_id=source.id,
                        fingerprint=fingerprint,
                        url=canonical_url,
                        title=offer.title,
                        price=offer.price,
                        currency=offer.currency,
                        city=offer.city,
                        region=normalized_region,
                        area_m2=offer.area_m2,
                        rooms=offer.rooms,
                        lat=offer.lat,
                        lng=offer.lng,
                        raw_json=offer.raw_json,
                        status=OfferStatus.INVALID_PARSE if invalid_parse else OfferStatus.ACTIVE,
                        source_created_at=source_created_at,
                        imported_at=imported_at,
                        first_seen=imported_at,
                        last_seen=imported_at,
                    )
                    session.add(new_offer)
                    session.flush()  # Get the ID
                    
                    new_count += 1
                    
                    logger.info(
                        "New offer inserted",
                        extra={
                            "offer_id": str(new_offer.id),
                            "title": offer.title[:50],
                        },
                    )
                    
                    # Enqueue notification only for valid records
                    if new_offer.status != OfferStatus.INVALID_PARSE:
                        notify_whatsapp.delay(str(new_offer.id))
                    
            except Exception as e:
                logger.error(
                    "Failed to process offer",
                    extra={
                        "error": str(e),
                        "offer": offer.model_dump() if hasattr(offer, 'model_dump') else str(offer),
                    },
                )
                continue
        
        session.commit()
    
    return new_count


@celery_app.task
def check_source_health():
    """
    Periodic task to check source health and disable failing sources.
    """
    with get_sync_session() as session:
        # Find sources with many recent failures
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(hours=1)
        
        sources = session.execute(select(Source)).scalars().all()
        
        for source in sources:
            # Count recent failures
            recent_failures = session.execute(
                select(ScrapeRun)
                .where(ScrapeRun.source_id == source.id)
                .where(ScrapeRun.started_at >= cutoff)
                .where(ScrapeRun.status == ScrapeRunStatus.FAILED)
            ).scalars().all()
            
            # Count recent runs
            recent_runs = session.execute(
                select(ScrapeRun)
                .where(ScrapeRun.source_id == source.id)
                .where(ScrapeRun.started_at >= cutoff)
            ).scalars().all()
            
            if len(recent_runs) >= 5 and len(recent_failures) / len(recent_runs) > 0.8:
                # Disable source
                source.enabled = False
                logger.error(
                    "Auto-disabled source due to high failure rate",
                    extra={
                        "source": source.name,
                        "failures": len(recent_failures),
                        "total": len(recent_runs),
                    },
                )
        
        session.commit()
    
    return {"status": "completed"}
