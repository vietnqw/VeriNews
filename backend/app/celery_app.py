"""
Celery application configuration.
"""

from __future__ import annotations


from celery import Celery

from app.config.settings import settings


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
    return app


celery_app = _create_celery()
