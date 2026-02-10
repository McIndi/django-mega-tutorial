"""Celery tasks for link tracking."""

import logging
from typing import Optional

from celery import shared_task
from django.conf import settings

from .models import Click, Link

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def record_link_click(
    self,
    link_id: int,
    referrer: str,
    user_agent: str,
    ip_address: Optional[str],
) -> str:
    """Record a link click asynchronously."""
    link = Link.objects.filter(id=link_id).first()
    if not link:
        logger.warning("record_link_click: Link id %s not found", link_id)
        return f"Link {link_id} not found"

    Click.objects.create(
        link=link,
        referrer=referrer,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    logger.debug(
        "Click recorded",
        extra={"link_id": link.id, "ip": ip_address},
    )
    return f"Click recorded for link {link_id}"
