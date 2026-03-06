"""
Celery application configuration.
"""
from celery import Celery
from celery.signals import setup_logging as celery_setup_logging

from app.logging_config import setup_logging
from app.settings import settings

# Create Celery app
celery_app = Celery(
    "real_estate_monitor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.scrape",
        "app.tasks.notify",
        "app.tasks.publication",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Warsaw",
    enable_utc=True,
    
    # Task execution
    task_always_eager=False,
    task_store_eager_result=False,
    task_ignore_result=False,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_concurrency=4,
    
    # Result backend
    result_expires=3600,
    result_backend_always_retry=True,
    result_backend_max_retries=10,
    
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 43200,  # 12 hours
    },
    
    # Task routes
    task_routes={
        "app.tasks.scrape.*": {"queue": "scrape"},
        "app.tasks.notify.*": {"queue": "notify"},
        "app.tasks.publication.*": {"queue": "publication"},
    },
    
    # Task default queue
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)


@celery_setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure logging for Celery workers."""
    setup_logging()


def get_celery_app():
    """Get configured Celery application."""
    return celery_app
