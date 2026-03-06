from __future__ import annotations

import asyncio

from app.logging_config import get_logger
from app.tasks.celery_app import celery_app
from app.integrations.otodom.service import process_due_jobs

logger = get_logger("publication_tasks")


@celery_app.task(bind=True, name="app.tasks.publication.process_otodom_jobs")
def process_otodom_jobs_task(self, limit: int = 20):
    logger.info(f"Processing Otodom publication jobs. limit={limit}")
    result = asyncio.run(process_due_jobs(limit=limit))
    return result
