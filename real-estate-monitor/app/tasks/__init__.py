"""
Celery tasks package.
"""
from app.tasks.celery_app import celery_app, get_celery_app
from app.tasks.scrape import scrape_source, check_source_health
from app.tasks.notify import notify_whatsapp, retry_failed_notifications
from app.tasks.scheduler import (
    dispatch_scrapes,
    run_scheduled_scrape,
    seed_sources,
)

__all__ = [
    "celery_app",
    "get_celery_app",
    "scrape_source",
    "check_source_health",
    "notify_whatsapp",
    "retry_failed_notifications",
    "dispatch_scrapes",
    "run_scheduled_scrape",
    "seed_sources",
]
