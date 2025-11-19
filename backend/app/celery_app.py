"""
Celery application configuration.
"""

from __future__ import annotations


from celery import Celery
from celery.signals import after_setup_logger
from loguru import logger

from app.config.settings import settings


@after_setup_logger.connect
def setup_loguru_logging(sender=None, **kwargs):
    """
    Configure Loguru to handle Celery worker logging.

    This function is connected to the `after_setup_logger` signal to ensure
    that our custom logging configuration is applied after Celery sets up its
    default loggers. It removes the default handler and adds a new sink
    with rotation, retention, and compression policies based on app settings.
    """
    logger.remove()  # Remove default handler
    logger.add(
        "logs/worker.log",  # Dedicated log file for Celery workers
        level=settings.LOG_LEVEL,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression=settings.LOG_COMPRESSION,
        enqueue=True,  # Make it process-safe
        backtrace=True,
        diagnose=settings.ENVIRONMENT == "local",  # More details in local dev
    )


def _create_celery() -> Celery:
    app = Celery(
        "verinews",
        broker=settings.celery.broker_url,
        backend=settings.celery.result_backend,
        include=["app.tasks.crawler_tasks"],
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        task_time_limit=settings.celery.task_time_limit,
        task_acks_late=True,
        worker_concurrency=settings.celery.worker_count,
        task_default_retry_delay=5,
    )

    # Beat schedule (kickoff all crawls periodically)
    interval_seconds = max(60, settings.scheduler.crawler_interval_minutes * 60)
    app.conf.beat_schedule = {
        "kickoff-all-crawls": {
            "task": "app.tasks.crawler_tasks.kickoff_all_crawls",
            "schedule": interval_seconds,
        },
        "cleanup-expired-articles": {
            "task": "app.tasks.crawler_tasks.cleanup_expired_articles",
            "schedule": interval_seconds,
        },
    }
    return app


celery_app = _create_celery()
