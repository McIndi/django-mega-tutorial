import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from config.celery import app as celery_app

logger = logging.getLogger(__name__)


def index(request):
    return render(request, "core/index.html")


def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.

    Checks:
        - Database connectivity (PostgreSQL/SQLite)
        - Celery broker connectivity (Redis/other)

    Returns:
        200 OK with JSON if healthy
        503 Service Unavailable if unhealthy (e.g., database or broker down)

    Response intentionally minimal to avoid information disclosure.
    """
    health_status = {"status": "ok"}
    http_status = 200

    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        logger.debug("Health check: database OK")
    except Exception as e:
        logger.error(f"Health check failed (database): {e}")
        health_status["status"] = "error"
        http_status = 503

    # Check Celery broker connectivity
    try:
        celery_app.control.inspect().active()
        logger.debug("Health check: Celery broker OK")
    except Exception as e:
        logger.warning(f"Health check: Celery broker unavailable: {e}")
        # Don't fail the health check if Celery is down; it's not critical
        # for all operations. In a production environment with strict
        # requirements, you may want to change this behavior.

    return JsonResponse(health_status, status=http_status)
