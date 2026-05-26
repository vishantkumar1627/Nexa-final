from celery import Celery
from shared.config import settings

# Initialize Celery app
celery_app = Celery(
    "architecture_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Optional configuration updates
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=900,  # 15 minutes max per pipeline job (supports Blender rendering)
)

# Autodiscover tasks from the workers directory
celery_app.autodiscover_tasks(["workers"])
