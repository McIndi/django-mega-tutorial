"""
URL configuration for the core app.
"""

from django.contrib import admin
from django.urls import path, include

from .views import index, health_check

app_name = "core"

urlpatterns = [
    path("", index, name="index"),
    path("health/", health_check, name="health_check"),
]
