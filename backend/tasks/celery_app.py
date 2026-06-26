"""Celery application configuration."""

from celery import Celery
from backend.config import settings

celery_app = Celery(
    "secure_translate",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # Process one task at a time
)

# Auto-discover tasks in backend.tasks
celery_app.autodiscover_tasks(["backend.tasks"])
