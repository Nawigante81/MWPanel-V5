"""
Scheduler logic for dispatching scrape tasks.
Runs continuously via Celery Beat.
"""
import random
from datetime import datetime
from typing import List

from sqlalchemy import select

from app.connectors.base import FilterConfig
from app.db import get_sync_session
from app.logging_config import get_logger
from app.models import Source
from app.settings import settings
from app.tasks.celery_app import celery_app
from app.tasks.scrape import scrape_source

logger = get_logger("tasks.scheduler")


# Default filter configurations
DEFAULT_FILTERS = [
    FilterConfig(
        region="pomorskie",
        transaction_type="sale",
    ),
]


def dispatch_scrapes():
    """
    Dispatch scrape tasks for all enabled sources.
    
    This function is called periodically by Celery Beat.
    It:
    1. Gets all enabled sources from database
    2. Applies jitter to intervals
    3. Dispatches scrape tasks
    """
    logger.debug("Dispatching scrape tasks")
    
    with get_sync_session() as session:
        sources = session.execute(
            select(Source).where(Source.enabled == True)
        ).scalars().all()
        
        for source in sources:
            try:
                dispatch_source_scrapes(source)
            except Exception as e:
                logger.error(
                    "Failed to dispatch scrapes for source",
                    extra={
                        "source": source.name,
                        "error": str(e),
                    },
                )


def dispatch_source_scrapes(source: Source):
    """Dispatch scrape tasks for a single source."""
    
    # Apply jitter to interval (±20%)
    jitter = random.uniform(0.8, 1.2)
    effective_interval = int(source.interval_seconds * jitter)
    
    logger.debug(
        "Dispatching source scrapes",
        extra={
            "source": source.name,
            "interval": effective_interval,
        },
    )
    
    # Dispatch for each filter configuration
    for filter_config in DEFAULT_FILTERS:
        # Use Celery's countdown for scheduling
        # This creates a distributed schedule
        scrape_source.apply_async(
            args=[source.name, filter_config.to_dict()],
            countdown=random.randint(0, effective_interval),
            queue="scrape",
        )
        
        logger.debug(
            "Dispatched scrape task",
            extra={
                "source": source.name,
                "filter": filter_config.to_dict(),
            },
        )


# Celery Beat schedule configuration
celery_app.conf.beat_schedule = {
    "dispatch-otodom": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": settings.otodom_interval_seconds,
        "args": ("otodom",),
        "options": {"queue": "scrape"},
    },
    "dispatch-olx": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": settings.olx_interval_seconds,
        "args": ("olx",),
        "options": {"queue": "scrape"},
    },
    "dispatch-facebook": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": settings.facebook_interval_seconds,
        "args": ("facebook",),
        "options": {"queue": "scrape"},
    },
    "dispatch-gratka": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": 900,
        "args": ("gratka",),
        "options": {"queue": "scrape"},
    },
    "dispatch-morizon": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": 900,
        "args": ("morizon",),
        "options": {"queue": "scrape"},
    },
    "dispatch-domiporta": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": 900,
        "args": ("domiporta",),
        "options": {"queue": "scrape"},
    },
    "dispatch-nieruchomosci-online": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": 900,
        "args": ("nieruchomosci-online",),
        "options": {"queue": "scrape"},
    },
    "dispatch-tabelaofert": {
        "task": "app.tasks.scheduler.run_scheduled_scrape",
        "schedule": 900,
        "args": ("tabelaofert",),
        "options": {"queue": "scrape"},
    },
    "check-source-health": {
        "task": "app.tasks.scrape.check_source_health",
        "schedule": 3600,  # Every hour
        "options": {"queue": "default"},
    },
    "retry-failed-notifications": {
        "task": "app.tasks.notify.retry_failed_notifications",
        "schedule": 300,  # Every 5 minutes
        "options": {"queue": "default"},
    },
    "process-otodom-publication-jobs": {
        "task": "app.tasks.publication.process_otodom_jobs",
        "schedule": 60,  # Every minute
        "options": {"queue": "publication"},
    },
    "retrain-price-model": {
        "task": "app.services.price_prediction.retrain_price_model",
        "schedule": 86400,  # Every 24 hours
        "options": {"queue": "default"},
    },
}


@celery_app.task
def run_scheduled_scrape(source_name: str) -> dict:
    """
    Run scheduled scrape for a source.
    
    This task is called by Celery Beat on the configured schedule.
    It adds jitter and dispatches the actual scrape task.
    """
    # Get source config
    with get_sync_session() as session:
        source = session.execute(
            select(Source).where(Source.name == source_name)
        ).scalar_one_or_none()
        
        if not source or not source.enabled:
            return {
                "source": source_name,
                "status": "skipped",
                "reason": "source_disabled",
            }
    
    # Apply jitter (±20%) to avoid robotic patterns
    jitter = random.uniform(0.8, 1.2)
    
    # Add small random delay
    delay = random.uniform(0, 5)
    
    logger.info(
        "Running scheduled scrape",
        extra={
            "source": source_name,
            "jitter": jitter,
            "delay": delay,
        },
    )
    
    # Dispatch for each filter
    for filter_config in DEFAULT_FILTERS:
        scrape_source.apply_async(
            args=[source_name, filter_config.to_dict()],
            countdown=int(delay),
            queue="scrape",
        )
    
    return {
        "source": source_name,
        "status": "dispatched",
        "filters": len(DEFAULT_FILTERS),
    }


@celery_app.task
def seed_sources():
    """
    Seed initial sources into the database.
    
    This should be run once on startup.
    """
    logger.info("Seeding initial sources")
    
    initial_sources = [
        {
            "name": "otodom",
            "enabled": True,
            "fetch_mode": "http",
            "base_url": "https://www.otodom.pl",
            "interval_seconds": settings.otodom_interval_seconds,
            "rate_limit_rps": settings.otodom_rate_limit_rps,
        },
        {
            "name": "olx",
            "enabled": True,
            "fetch_mode": "http",
            "base_url": "https://www.olx.pl",
            "interval_seconds": settings.olx_interval_seconds,
            "rate_limit_rps": settings.olx_rate_limit_rps,
        },
        {
            "name": "facebook",
            "enabled": True,
            "fetch_mode": "playwright",
            "base_url": "https://www.facebook.com",
            "interval_seconds": settings.facebook_interval_seconds,
            "rate_limit_rps": settings.facebook_rate_limit_rps,
        },
        {
            "name": "gratka",
            "enabled": True,
            "fetch_mode": "http",
            "base_url": "https://gratka.pl",
            "interval_seconds": 900,
            "rate_limit_rps": 0.4,
        },
        {
            "name": "morizon",
            "enabled": True,
            "fetch_mode": "http",
            "base_url": "https://www.morizon.pl",
            "interval_seconds": 900,
            "rate_limit_rps": 0.4,
        },
        {
            "name": "domiporta",
            "enabled": True,
            "fetch_mode": "http",
            "base_url": "https://www.domiporta.pl",
            "interval_seconds": 900,
            "rate_limit_rps": 0.4,
        },
        {
            "name": "nieruchomosci-online",
            "enabled": True,
            "fetch_mode": "http",
            "base_url": "https://www.nieruchomosci-online.pl",
            "interval_seconds": 900,
            "rate_limit_rps": 0.4,
        },
        {
            "name": "tabelaofert",
            "enabled": True,
            "fetch_mode": "http",
            "base_url": "https://tabelaofert.pl",
            "interval_seconds": 900,
            "rate_limit_rps": 0.4,
        },
    ]
    
    with get_sync_session() as session:
        for source_data in initial_sources:
            existing = session.execute(
                select(Source).where(Source.name == source_data["name"])
            ).scalar_one_or_none()
            
            if existing:
                # Update existing source with new defaults
                existing.interval_seconds = source_data["interval_seconds"]
                existing.rate_limit_rps = source_data["rate_limit_rps"]
                existing.fetch_mode = source_data["fetch_mode"]
                logger.debug(f"Updated source: {source_data['name']}")
            else:
                # Create new source
                source = Source(**source_data)
                session.add(source)
                logger.info(f"Created source: {source_data['name']}")
        
        session.commit()
    
    return {"status": "completed", "sources": len(initial_sources)}
