import os
import sys
from celery import Celery
from kombu import Queue
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "geo_insight_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.computer_vision_tasks",
        "app.tasks.geospatial_tasks",
        "app.tasks.agent_tasks",
        "app.tasks.maintenance_tasks",
        "app.tasks.satellite_tasks",
        "app.tasks.vector_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    task_track_started=True,
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", 30 * 60)),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", 25 * 60)),

    task_acks_on_failure_or_timeout=True,
    task_reject_on_worker_lost=False,

    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", 3600)),

    worker_prefetch_multiplier=int(os.getenv("CELERY_PREFETCH_MULTIPLIER", 1)),
    worker_max_tasks_per_child=int(os.getenv("CELERY_MAX_TASKS_PER_CHILD", 100)),
    worker_pool=os.getenv("CELERY_POOL", "solo"),
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", 1)),
    worker_send_task_events=True,

    task_default_queue=os.getenv("CELERY_DEFAULT_QUEUE", "default"),
    task_queues=(
        Queue("default",      routing_key="task.default"),
        Queue("high_priority",routing_key="task.high"),
        Queue("cpu_bound",    routing_key="task.cpu"),
        Queue("io_bound",     routing_key="task.io"),
        Queue("maintenance",  routing_key="task.maintenance"),
    ),

    task_routes={
        "app.tasks.satellite_tasks.analyze_satellite":         {"queue": "cpu_bound", "routing_key": "task.cpu"},
        "app.tasks.geospatial_tasks.analyze_neighborhood":     {"queue": "io_bound",  "routing_key": "task.io"},
        "app.tasks.agent_tasks.process_agent_query":           {"queue": "default",   "routing_key": "task.default"},
        "app.tasks.maintenance_tasks.cleanup_old_tasks":       {"queue": "maintenance","routing_key": "task.maintenance"},
        "app.tasks.vector_tasks.batch_embed_properties":       {"queue": "cpu_bound", "routing_key": "task.cpu"},
    },

    broker_transport_options={
        "visibility_timeout": int(os.getenv("CELERY_VISIBILITY_TIMEOUT", 3600)),
    },


    task_annotations={
        "*": {"rate_limit": None},
    },

    beat_schedule={
        "cleanup-old-tasks": {
            "task":    "app.tasks.maintenance_tasks.cleanup_old_tasks",
            "schedule": float(os.getenv("MAINTENANCE_SCHEDULE_SECONDS", 3600.0)),
            "options": {"queue": "maintenance"},
        },
    },
)


def get_celery_queues():
    return [q.name for q in celery_app.conf.task_queues]