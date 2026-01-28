"""Celery app configuration for Django project."""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("django_saas")

# Load configuration from Django settings, all configuration keys should
# have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY_")

# Auto-discover tasks from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery worker connectivity."""
    print(f"Request: {self.request!r}")
