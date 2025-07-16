"""
Celery application configuration
"""
from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    'globant_challenge',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['app.workers.tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    result_expires=3600,  # 1 hour
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
) 