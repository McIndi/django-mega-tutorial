import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def index(request):
    return render(request, "core/index.html")


def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        200 OK with JSON if healthy
        503 Service Unavailable if unhealthy (e.g., database down)

    Response intentionally minimal to avoid information disclosure.
    """
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        logger.debug("Health check: passed")
        return JsonResponse({"status": "ok"}, status=200)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JsonResponse({"status": "error"}, status=503)
