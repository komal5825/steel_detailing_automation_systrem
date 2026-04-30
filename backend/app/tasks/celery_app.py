from celery import Celery
from app.config.settings import settings

celery_app = Celery(
    "tasks",
    broker=settings.celery_broker_url,
    backend=settings.redis_url
)

celery_app.conf.task_routes = {
    "app.tasks.phase1_tasks.*": {"queue": "phase1"},
    "app.tasks.phase2_tasks.*": {"queue": "phase2"},
}
