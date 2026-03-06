"""
Auto-retry service for failed scrapes.
Manages a queue of failed scrapes with exponential backoff.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import FailedScrape
from app.db import get_sync_session

logger = get_logger("retry_queue")


class RetryQueue:
    """
    Manages failed scrape retries.
    
    Features:
    - Exponential backoff
    - Max retry limit
    - Priority queue
    - Dead letter tracking
    """
    
    def __init__(self):
        self.max_retries = 5
        self.base_delay_minutes = 5
    
    def add_failed_scrape(
        self,
        source_name: str,
        filter_config: dict,
        error: str,
        retry_count: int = 0
    ) -> UUID:
        """
        Add a failed scrape to the retry queue.
        
        Returns:
            ID of the failed scrape record
        """
        from app.db import SyncSessionLocal
        
        # Calculate next retry time
        next_retry = self._calculate_next_retry(retry_count)
        
        with SyncSessionLocal() as session:
            failed = FailedScrape(
                source_name=source_name,
                filter_config=filter_config,
                error=error,
                retry_count=retry_count,
                next_retry_at=next_retry,
                status="pending"
            )
            session.add(failed)
            session.commit()
            
            logger.info(
                "Added to retry queue",
                extra={
                    "source": source_name,
                    "retry_count": retry_count,
                    "next_retry": next_retry.isoformat()
                }
            )
            
            return failed.id
    
    def get_pending_retries(
        self,
        limit: int = 10
    ) -> List[FailedScrape]:
        """
        Get scrapes ready for retry.
        
        Returns:
            List of failed scrapes ready to retry
        """
        from app.db import SyncSessionLocal
        
        with SyncSessionLocal() as session:
            now = datetime.utcnow()
            
            result = session.execute(
                select(FailedScrape)
                .where(FailedScrape.status == "pending")
                .where(FailedScrape.next_retry_at <= now)
                .where(FailedScrape.retry_count < FailedScrape.max_retries)
                .order_by(FailedScrape.next_retry_at)
                .limit(limit)
            )
            
            return result.scalars().all()
    
    def mark_retrying(self, scrape_id: UUID):
        """Mark a scrape as currently retrying."""
        from app.db import SyncSessionLocal
        
        with SyncSessionLocal() as session:
            scrape = session.get(FailedScrape, scrape_id)
            if scrape:
                scrape.status = "retrying"
                session.commit()
    
    def mark_success(self, scrape_id: UUID):
        """Mark a scrape as successfully resolved."""
        from app.db import SyncSessionLocal
        
        with SyncSessionLocal() as session:
            scrape = session.get(FailedScrape, scrape_id)
            if scrape:
                scrape.status = "resolved"
                scrape.resolved_at = datetime.utcnow()
                session.commit()
                
                logger.info(
                    "Scrape resolved after retry",
                    extra={
                        "scrape_id": str(scrape_id),
                        "retries": scrape.retry_count
                    }
                )
    
    def mark_failed_again(
        self,
        scrape_id: UUID,
        error: str
    ):
        """Mark a retry as failed again."""
        from app.db import SyncSessionLocal
        
        with SyncSessionLocal() as session:
            scrape = session.get(FailedScrape, scrape_id)
            if scrape:
                scrape.retry_count += 1
                scrape.error = error
                
                if scrape.retry_count >= scrape.max_retries:
                    scrape.status = "failed"
                    logger.error(
                        "Scrape failed permanently",
                        extra={
                            "scrape_id": str(scrape_id),
                            "total_retries": scrape.retry_count
                        }
                    )
                else:
                    scrape.next_retry_at = self._calculate_next_retry(scrape.retry_count)
                    scrape.status = "pending"
                
                session.commit()
    
    def _calculate_next_retry(self, retry_count: int) -> datetime:
        """Calculate next retry time with exponential backoff."""
        # Exponential backoff: 5min, 15min, 45min, 2h, 6h
        delay_multiplier = 3 ** retry_count
        delay_minutes = self.base_delay_minutes * delay_multiplier
        
        # Add jitter (±20%)
        import random
        jitter = random.uniform(0.8, 1.2)
        delay_minutes *= jitter
        
        return datetime.utcnow() + timedelta(minutes=delay_minutes)
    
    def get_stats(self) -> dict:
        """Get retry queue statistics."""
        from app.db import SyncSessionLocal
        from sqlalchemy import func
        
        with SyncSessionLocal() as session:
            pending = session.scalar(
                select(func.count(FailedScrape.id))
                .where(FailedScrape.status == "pending")
            )
            
            retrying = session.scalar(
                select(func.count(FailedScrape.id))
                .where(FailedScrape.status == "retrying")
            )
            
            resolved = session.scalar(
                select(func.count(FailedScrape.id))
                .where(FailedScrape.status == "resolved")
            )
            
            failed = session.scalar(
                select(func.count(FailedScrape.id))
                .where(FailedScrape.status == "failed")
            )
            
            return {
                "pending": pending,
                "retrying": retrying,
                "resolved": resolved,
                "failed": failed,
                "total": pending + retrying + resolved + failed
            }
    
    def cleanup_old(self, days: int = 30):
        """Clean up old resolved/failed entries."""
        from app.db import SyncSessionLocal
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        with SyncSessionLocal() as session:
            result = session.execute(
                select(FailedScrape)
                .where(FailedScrape.status.in_(["resolved", "failed"]))
                .where(FailedScrape.created_at < cutoff)
            )
            
            for scrape in result.scalars():
                session.delete(scrape)
            
            session.commit()
            
            logger.info("Cleaned up old failed scrape records")


# Celery task for processing retry queue
from app.tasks.celery_app import celery_app


@celery_app.task
def process_retry_queue():
    """
    Process pending retries in the queue.
    Called periodically by Celery Beat.
    """
    queue = RetryQueue()
    
    pending = queue.get_pending_retries(limit=20)
    
    for failed_scrape in pending:
        logger.info(
            "Processing retry",
            extra={
                "source": failed_scrape.source_name,
                "retry": failed_scrape.retry_count
            }
        )
        
        # Import here to avoid circular imports
        from app.tasks.scrape import scrape_source
        
        # Dispatch retry task
        scrape_source.apply_async(
            args=[failed_scrape.source_name, failed_scrape.filter_config],
            kwargs={"failed_scrape_id": str(failed_scrape.id)},
            queue="scrape"
        )
        
        queue.mark_retrying(failed_scrape.id)
    
    return {
        "processed": len(pending),
        "stats": queue.get_stats()
    }


# Global instance
_retry_queue: Optional[RetryQueue] = None


def get_retry_queue() -> RetryQueue:
    """Get or create retry queue."""
    global _retry_queue
    
    if _retry_queue is None:
        _retry_queue = RetryQueue()
    
    return _retry_queue
