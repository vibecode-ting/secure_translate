"""Celery application configuration — with fakeredis fallback for testing."""

from backend.config import settings

# Try to connect to real Redis; fall back to fakeredis for local testing
try:
    import redis as _redis_lib
    _redis_client = _redis_lib.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)
    _redis_client.ping()
    _redis_available = True
except Exception:
    _redis_available = False

if _redis_available:
    from celery import Celery
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
        task_time_limit=3600,
        worker_prefetch_multiplier=1,
    )
    celery_app.autodiscover_tasks(["backend.tasks"])
else:
    # fakeredis fallback — tasks execute synchronously, no real broker needed
    import fakeredis
    from celery import Celery

    _fake_redis = fakeredis.FakeRedis()

    celery_app = Celery(
        "secure_translate",
        broker="memory://",
        backend="cache+memory://",
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,
        worker_prefetch_multiplier=1,
        task_always_eager=True,           # execute tasks synchronously
        task_eager_propagates=True,       # propagate exceptions
    )
    celery_app.autodiscover_tasks(["backend.tasks"])
