from celery import Celery
from src.config.settings import settings


broker_url = (
    f"amqp://{settings.rabbitmq_user}:{settings.rabbitmq_password}"
    f"@{settings.rabbitmq_host}:{settings.rabbitmq_port}//"
)
result_backend = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"

celery_app = Celery("dating_bot", broker=broker_url, backend=result_backend)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "recalculate-ratings-every-5-minutes": {
            "task": "src.tasks.tasks.recalculate_all_ratings",
            "schedule": 300.0,
        },
    },
    task_routes={
        "src.tasks.tasks.handle_like_event": {"queue": "events"},
        "src.tasks.tasks.handle_match_event": {"queue": "events"},
    },
)

celery_app.autodiscover_tasks(["src.tasks"])
