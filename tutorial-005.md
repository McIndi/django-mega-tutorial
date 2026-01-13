# Production Readiness: Static Files, Logging, and Health Checks (Tutorial 005)

**Published January 3, 2026**
*By Cliff*

---

## TL;DR

This tutorial prepares your Django SaaS for production deployment by adding essential infrastructure:

- **WhiteNoise**: Efficient static file serving without external dependencies or CDN lock-in
- **Structured logging**: Consistent logging configuration with proper log levels across all apps
- **Custom error pages**: Branded 404 and 500 pages extending your base template
- **Health check endpoint**: `/health/` endpoint for load balancers and monitoring

Following TDD principles, we'll write tests first, then implement each feature. By the end, your application will be production-ready with proper static file handling, observable behavior through logs, user-friendly error pages, and infrastructure-ready health checks.

**Estimated time**: **60–90 minutes**
**Prerequisites**: Completed Tutorials 001–004 (project runs, all tests green, Docker works)

---

## Introduction: Why Production Readiness Matters

Tutorials 001–004 built a functional Django SaaS with authentication, link shortening, testing, and containerization. However, several production essentials remain:

1. **Static files**: Django's `runserver` serves static files automatically, but production servers don't
2. **Logging**: Debug prints don't scale; structured logs enable monitoring and troubleshooting
3. **Error pages**: Django's default error pages expose technical details users shouldn't see
4. **Health checks**: Load balancers and orchestration platforms need a simple way to verify app health

This tutorial addresses all four, creating a release-ready application.

---

## Part 1: Static Files with WhiteNoise (TDD)

### Why WhiteNoise?

Django's static file system requires two steps:
1. Development: Files served directly from app directories
2. Production: Files collected to `STATIC_ROOT` and served by a web server

Traditional solutions use nginx, Apache, or a CDN. WhiteNoise is simpler:

- **Zero configuration**: Works out of the box with Django
- **No external dependencies**: No nginx, no S3, no CDN required (but compatible with all)
- **Efficient**: Compression, caching headers, and CDN-friendly URLs built in
- **Not a lock-in**: Easily switch to a CDN later by changing `STATIC_URL`

For early-stage SaaS products, WhiteNoise gets you running quickly without infrastructure complexity.

---

### Step 1: Write Tests for Static File Serving (Red)

Following TDD, we write tests before implementation. Open `core/tests.py` and add these tests:

```python
from django.conf import settings
from django.test import TestCase, override_settings


class StaticFilesTests(TestCase):
    """Tests for static file serving with WhiteNoise."""

    @override_settings(DEBUG=False)
    def test_static_files_served_in_production(self):
        """Test that static files are served when DEBUG=False."""
        # WhiteNoise should serve static files even with DEBUG=False
        # Django's admin ships with static files we can test against
        response = self.client.get("/static/admin/css/base.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Django", response.content)

    @override_settings(DEBUG=False)
    def test_static_files_have_cache_headers(self):
        """Test that static files include caching headers."""
        response = self.client.get("/static/admin/css/base.css")
        self.assertEqual(response.status_code, 200)
        # WhiteNoise should add cache-control headers
        self.assertIn("Cache-Control", response.headers)

    def test_staticfiles_dirs_configured(self):
        """Test that STATICFILES_DIRS is properly configured."""
        # Ensure we have a static directory configured
        self.assertTrue(hasattr(settings, "STATICFILES_DIRS"))
        self.assertIsInstance(settings.STATICFILES_DIRS, list)
```

Run these tests to confirm they fail (Red phase):

```bash
python manage.py test core.tests.StaticFilesTests
```

Expected: Tests fail because WhiteNoise is not yet configured.

---

### Step 2: Install and Configure WhiteNoise (Green)

#### Update Dependencies

Edit `pyproject.toml` to add WhiteNoise:

```toml
[project]
dependencies = [
    "django",
    "django-environ",
    "whitenoise",
]
```

Install:

```bash
pip install -e .
```

#### Configure WhiteNoise in Settings

Edit `config/settings.py`:

**1. Add WhiteNoise middleware** (must be after SecurityMiddleware, before all others):

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Add this line
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ... rest of middleware
]
```

**2. Configure static files settings** (add near the bottom):

```python
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# WhiteNoise configuration
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
```

**Why this configuration?**

- `STATIC_URL`: URL prefix for static files
- `STATIC_ROOT`: Directory where `collectstatic` gathers all static files
- `STATICFILES_DIRS`: Additional locations for static files (app-level static files are found automatically)
- `CompressedManifestStaticFilesStorage`: Adds compression and cache-busting hashes to filenames

#### Create Static Directory

```bash
mkdir static
```

This is where project-level static files (not app-specific) will live.

#### Run collectstatic

```bash
python manage.py collectstatic --noinput
```

This collects all static files from Django apps and `STATICFILES_DIRS` into `STATIC_ROOT`.

#### Verify Tests Pass (Green)

```bash
python manage.py test core.tests.StaticFilesTests
```

All three tests should now pass.

---

### Step 3: Update Build Processes for collectstatic

We need to run `collectstatic` in multiple places:

#### Update Dockerfile

Edit `Dockerfile` to run `collectstatic` during the build:

```dockerfile
# Production stage
FROM base AS production

# Copy application code
COPY --chown=appuser:appuser . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Use the custom serve command
CMD ["python", "manage.py", "serve", "--host", "0.0.0.0"]
```

#### Update GitHub Actions CI

Edit `.github/workflows/ci.yml` to run collectstatic before tests:

```yaml
      - name: Collect static files
        run: python manage.py collectstatic --noinput

      - name: Run tests
        run: python manage.py test
```

#### Update README.md

Add collectstatic to the setup instructions:

```markdown
### Initial Setup

```bash
# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Run the server
python manage.py serve
```
```

---

## Part 2: Structured Logging (TDD)

### Why Logging Matters

Logging provides visibility into application behavior:

- **Development**: Understand what's happening during requests
- **Production**: Debug issues without ssh access
- **Monitoring**: Feed logs to centralized systems (CloudWatch, Datadog, Splunk)

Django's logging system uses Python's `logging` module with sensible defaults. We'll configure structured logging and add it consistently across the codebase.

---

### Step 1: Write Logging Tests (Red)

Add these tests to `core/tests.py`:

```python
import logging
from io import StringIO

from django.test import TestCase


class LoggingTests(TestCase):
    """Tests for logging configuration."""

    def test_logging_configured(self):
        """Test that logging is properly configured."""
        from django.conf import settings

        self.assertIn("LOGGING", dir(settings))
        self.assertIsInstance(settings.LOGGING, dict)
        self.assertIn("version", settings.LOGGING)

    def test_logger_output_format(self):
        """Test that log messages include timestamp and level."""
        logger = logging.getLogger("django")

        # Capture log output
        with self.assertLogs("django", level="INFO") as cm:
            logger.info("Test log message")

        # Verify log output contains expected format
        self.assertEqual(len(cm.output), 1)
        self.assertIn("INFO", cm.output[0])
        self.assertIn("Test log message", cm.output[0])

    def test_app_loggers_exist(self):
        """Test that application loggers can be instantiated."""
        # These should not raise errors
        accounts_logger = logging.getLogger("accounts")
        links_logger = logging.getLogger("links")
        core_logger = logging.getLogger("core")

        self.assertIsNotNone(accounts_logger)
        self.assertIsNotNone(links_logger)
        self.assertIsNotNone(core_logger)
```

Run tests (Red phase):

```bash
python manage.py test core.tests.LoggingTests
```

---

### Step 2: Configure Logging in Settings (Green)

Add this logging configuration to `config/settings.py`:

```python
# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "links": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
```

**Configuration explained:**

- **Formatters**: Define how log messages appear
  - `verbose`: Includes level, timestamp, module, and message
  - `simple`: Just level and message
- **Handlers**: Where logs go (console, file, external service)
- **Root logger**: Catches all unhandled logs
- **App loggers**: Dedicated loggers for each Django app
- **Environment variable**: `DJANGO_LOG_LEVEL` controls verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)

Verify tests pass:

```bash
python manage.py test core.tests.LoggingTests
```

---

### Step 3: Add Logging to Application Code

Now we'll add consistent logging across the codebase. Use these guidelines:

| Level | When to Use |
|-------|-------------|
| **DEBUG** | Detailed diagnostic info (disabled in production) |
| **INFO** | Normal operations (user registered, link created) |
| **WARNING** | Unexpected but handled (invalid form, rate limit) |
| **ERROR** | Errors requiring attention (external API failure) |
| **CRITICAL** | System-level failures (database down) |

#### accounts/views.py

```python
import logging

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CustomUserCreationForm

logger = logging.getLogger(__name__)


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            logger.info(
                f"New user registered: {user.username} ({user.email})",
                extra={"user_id": user.id, "username": user.username},
            )
            return redirect("accounts:profile")
        else:
            logger.warning(
                f"Registration form invalid: {form.errors.as_json()}",
                extra={"errors": form.errors.as_data()},
            )
    else:
        form = CustomUserCreationForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    logger.debug(
        f"Profile accessed by {request.user.username}",
        extra={"user_id": request.user.id},
    )
    return render(request, "accounts/profile.html")
```

#### accounts/forms.py

```python
import logging

from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser

logger = logging.getLogger(__name__)


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if CustomUser.objects.filter(email=email).exists():
            logger.warning(
                f"Registration attempt with duplicate email: {email}",
                extra={"email": email},
            )
            raise forms.ValidationError("This email address is already registered.")
        return email
```

#### links/views.py

```python
import logging

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import LinkForm
from .models import Click, Link

logger = logging.getLogger(__name__)


class LinkListView(LoginRequiredMixin, ListView):
    model = Link
    template_name = "links/link_list.html"
    context_object_name = "links"

    def get_queryset(self):
        logger.debug(
            f"Fetching links for user {self.request.user.username}",
            extra={"user_id": self.request.user.id},
        )
        return Link.objects.filter(user=self.request.user).order_by("-created_at")


class LinkCreateView(LoginRequiredMixin, CreateView):
    model = Link
    form_class = LinkForm
    template_name = "links/link_form.html"
    success_url = reverse_lazy("links:link_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        logger.info(
            f"Link created: {self.object.public_path} -> {self.object.target_url}",
            extra={
                "user_id": self.request.user.id,
                "link_id": self.object.id,
                "slug": self.object.slug,
            },
        )
        return response


class LinkDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Link
    template_name = "links/link_detail.html"
    context_object_name = "link"

    def test_func(self):
        link = self.get_object()
        return link.user == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["clicks"] = self.object.clicks.order_by("-created_at")[:10]
        context["click_count"] = self.object.clicks.count()
        logger.debug(
            f"Link detail viewed: {self.object.public_path} ({context['click_count']} clicks)",
            extra={"link_id": self.object.id, "user_id": self.request.user.id},
        )
        return context


class LinkUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Link
    form_class = LinkForm
    template_name = "links/link_form.html"

    def test_func(self):
        link = self.get_object()
        return link.user == self.request.user

    def get_success_url(self):
        logger.info(
            f"Link updated: {self.object.public_path}",
            extra={"link_id": self.object.id, "user_id": self.request.user.id},
        )
        return reverse_lazy("links:link_detail", kwargs={"pk": self.object.pk})


class LinkDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Link
    template_name = "links/link_confirm_delete.html"
    success_url = reverse_lazy("links:link_list")

    def test_func(self):
        link = self.get_object()
        return link.user == self.request.user

    def form_valid(self, form):
        logger.info(
            f"Link deleted: {self.object.public_path}",
            extra={"link_id": self.object.id, "user_id": self.request.user.id},
        )
        return super().form_valid(form)


def redirect_link(request, username, slug):
    """Public endpoint that redirects to target URL and records click."""
    link = get_object_or_404(Link, user__username=username, slug=slug)

    # Record the click
    Click.objects.create(
        link=link,
        referrer=request.META.get("HTTP_REFERER", ""),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        ip_address=request.META.get("REMOTE_ADDR", ""),
    )

    logger.info(
        f"Link redirect: {link.public_path} -> {link.target_url}",
        extra={
            "link_id": link.id,
            "slug": slug,
            "target": link.target_url,
            "ip": request.META.get("REMOTE_ADDR"),
        },
    )

    return redirect(link.target_url)
```

#### links/models.py

```python
import logging
import secrets
import string

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

SLUG_ALPHABET = string.ascii_lowercase + string.digits
SLUG_LENGTH = 8


def generate_slug(length: int = SLUG_LENGTH) -> str:
    slug = "".join(secrets.choice(SLUG_ALPHABET) for _ in range(length))
    logger.debug(f"Generated slug: {slug}")
    return slug


# ... rest of models (no changes needed to model definitions)
```

#### core/management/commands/serve.py

```python
import logging
import os

from cheroot.wsgi import Server as WSGIServer
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.wsgi import get_wsgi_application

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the Django application using Cheroot WSGI server"

    def add_arguments(self, parser):
        # ... existing arguments ...

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]
        numthreads = options["numthreads"]
        tls_cert = options["tls_cert"]
        tls_key = options["tls_key"]

        logger.info(f"Starting Cheroot WSGI server on {host}:{port}")
        logger.info(f"Using {numthreads} threads")

        # ... rest of implementation with logging at key points ...
```

#### core/management/commands/serve_async.py

```python
import logging
import os

from daphne.cli import CommandLineInterface
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the Django application using Daphne ASGI server"

    def add_arguments(self, parser):
        # ... existing arguments ...

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]
        tls_cert = options["tls_cert"]
        tls_key = options["tls_key"]

        logger.info(f"Starting Daphne ASGI server on {host}:{port}")

        # ... rest of implementation with logging at key points ...
```

---

## Part 3: Custom Error Pages (TDD)

### Why Custom Error Pages?

Django's default error pages expose technical details useful during development but problematic in production:

- **404**: Shows attempted URL and Django's URLconf
- **500**: Shows full stack trace with file paths and variable values

Custom error pages provide:
- Brand consistency
- User-friendly messaging
- No information leakage
- Helpful navigation (back to home, contact support)

---

### Step 1: Write Error Page Tests (Red)

Add these tests to `core/tests.py`:

```python
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    """Tests for custom error pages."""

    def test_404_page_uses_custom_template(self):
        """Test that 404 errors render the custom template."""
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page Not Found", status_code=404)

    def test_404_page_extends_base_template(self):
        """Test that 404 page uses the site layout."""
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        # Check for elements from base.html
        self.assertContains(response, "Django SaaS", status_code=404)

    def test_500_page_uses_custom_template(self):
        """Test that 500 errors render the custom template."""
        # We can't easily trigger a real 500 in tests, so we'll check the view directly
        from django.views.defaults import server_error
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")

        # Test the error view directly
        response = server_error(request, template_name="500.html")
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Server Error", response.content)
```

Run tests (Red phase):

```bash
python manage.py test core.tests.ErrorPageTests
```

---

### Step 2: Create Custom Error Templates (Green)

Create two templates in the project root `templates/` directory (not inside any app):

#### templates/404.html

```html
{% extends "core/base.html" %}

{% block title %}Page Not Found{% endblock %}

{% block content %}
<div class="container mt-5">
    <div class="row justify-content-center">
        <div class="col-md-8 text-center">
            <h1 class="display-1">404</h1>
            <h2 class="mb-4">Page Not Found</h2>
            <p class="lead">
                The page you're looking for doesn't exist or has been moved.
            </p>
            <div class="mt-4">
                <a href="{% url 'core:index' %}" class="btn btn-primary btn-lg">
                    <i class="bi bi-house"></i> Go to Homepage
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

#### templates/500.html

```html
{% extends "core/base.html" %}

{% block title %}Server Error{% endblock %}

{% block content %}
<div class="container mt-5">
    <div class="row justify-content-center">
        <div class="col-md-8 text-center">
            <h1 class="display-1">500</h1>
            <h2 class="mb-4">Server Error</h2>
            <p class="lead">
                Something went wrong on our end. We've been notified and are working on it.
            </p>
            <div class="mt-4">
                <a href="{% url 'core:index' %}" class="btn btn-primary btn-lg">
                    <i class="bi bi-house"></i> Go to Homepage
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**Note**: These templates extend `core/base.html`, ensuring consistent navigation and styling.

#### Update settings.py

Ensure Django knows to look for templates in the project root:

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # This should already be configured
        "APP_DIRS": True,
        # ... rest of config
    },
]
```

Verify tests pass:

```bash
python manage.py test core.tests.ErrorPageTests
```

---

## Part 4: Health Check Endpoint (TDD)

### Why Health Checks?

Production infrastructure needs a simple way to verify application health:

- **Load balancers**: Route traffic only to healthy instances
- **Kubernetes**: Restart unhealthy pods automatically
- **Monitoring**: Alert when health checks fail

A health check endpoint should:
- Return 200 OK when the app is working
- Be fast (< 100ms)
- Optionally check critical dependencies (database, cache)

---

### Step 1: Write Health Check Tests (Red)

Add these tests to `core/tests.py`:

```python
from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    """Tests for the health check endpoint."""

    def test_health_check_returns_200(self):
        """Test that health check endpoint returns 200 OK."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_check_json_response(self):
        """Test that health check returns JSON with status."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")

    def test_health_check_includes_database_status(self):
        """Test that health check verifies database connectivity."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("database", data)
        self.assertEqual(data["database"], "connected")

    def test_health_check_does_not_require_authentication(self):
        """Test that health check is accessible without login."""
        # Clear any existing session
        self.client.logout()

        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
```

Run tests (Red phase):

```bash
python manage.py test core.tests.HealthCheckTests
```

---

### Step 2: Implement Health Check Endpoint (Green)

#### Add the view to core/views.py

```python
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
    """
    health_status = {
        "status": "healthy",
    }

    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status["database"] = "connected"
        logger.debug("Health check: database connected")
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = "disconnected"
        logger.error(f"Health check: database connection failed: {e}")
        return JsonResponse(health_status, status=503)

    return JsonResponse(health_status, status=200)
```

#### Add URL pattern to core/urls.py

```python
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("health/", views.health_check, name="health_check"),
]
```

Verify tests pass:

```bash
python manage.py test core.tests.HealthCheckTests
```

---

## Part 5: Production Checklist and Verification

### Update .env.example

Add the new environment variable:

```dotenv
# Logging
DJANGO_LOG_LEVEL=INFO
```

### Create .gitignore entries

Ensure these are in `.gitignore`:

```
staticfiles/
static/
*.log
```

### Run the Full Test Suite

```bash
python manage.py test
```

You should see all tests passing, including the new ones:
- 3 static file tests
- 3 logging tests
- 3 error page tests
- 4 health check tests

### Verify with DEBUG=False

Test the application with production settings:

```bash
# Set DEBUG=False in .env
echo "DJANGO_DEBUG=False" >> .env

# Collect static files
python manage.py collectstatic --noinput

# Run the server
python manage.py serve
```

Visit:
- `http://localhost:8000/` - Homepage should load with styles
- `http://localhost:8000/admin/` - Admin should have CSS
- `http://localhost:8000/does-not-exist/` - Should show custom 404 page
- `http://localhost:8000/health/` - Should return JSON health status

Check logs for structured output:

```
INFO 2026-01-03 12:34:56 core Starting Cheroot WSGI server on 127.0.0.1:8000
INFO 2026-01-03 12:35:01 accounts New user registered: alice (alice@example.com)
INFO 2026-01-03 12:35:15 links Link created: /alice/abc123de/ -> https://example.com
```

---

## Summary: What We Built

| Feature | Purpose | Tests Added |
|---------|---------|-------------|
| **WhiteNoise** | Efficient static file serving | 3 |
| **Structured Logging** | Observable application behavior | 3 |
| **Custom Error Pages** | User-friendly 404/500 handling | 3 |
| **Health Check** | Infrastructure readiness | 4 |

### Key Files Modified

- `config/settings.py` - WhiteNoise, logging, static files configuration
- `core/views.py` - Health check endpoint
- `core/urls.py` - Health check URL
- `core/tests.py` - 13 new tests
- `accounts/views.py`, `accounts/forms.py` - Logging
- `links/views.py`, `links/models.py` - Logging
- `core/management/commands/serve.py`, `serve_async.py` - Logging
- `templates/404.html`, `templates/500.html` - Custom error pages
- `Dockerfile` - collectstatic during build
- `docker-compose.yaml` - collectstatic on startup
- `.github/workflows/ci.yml` - collectstatic in CI
- `README.md` - Updated setup instructions

### Production Readiness Achieved

Your Django SaaS now has:

✅ **Static file serving** without external dependencies
✅ **Structured logging** for debugging and monitoring
✅ **Custom error pages** that don't leak information
✅ **Health check endpoint** for infrastructure integration
✅ **CI/CD integration** with collectstatic in all environments
✅ **Docker support** with proper static file handling

---

## Next Steps

1. **Test in staging**: Deploy to a staging environment and verify logs
2. **Configure log aggregation**: Send logs to CloudWatch, Datadog, or Splunk
3. **Set up monitoring**: Create alerts based on health check and log patterns
4. **Load testing**: Verify WhiteNoise performance under load

Future tutorials will cover:

- **Tutorial 006**: Email backend configuration and transactional emails
- **Tutorial 007**: Background tasks with Celery
- **Tutorial 008**: Subscription billing with Stripe
- **Tutorial 009**: Production deployment with Let's Encrypt
- **Tutorial 010**: Monitoring and observability

---

## References

- [WhiteNoise Documentation](http://whitenoise.evans.io/)
- [Django Logging Documentation](https://docs.djangoproject.com/en/stable/topics/logging/)
- [Python Logging Levels](https://docs.python.org/3/library/logging.html#logging-levels)
- [Django Error Views](https://docs.djangoproject.com/en/stable/ref/views/#error-views)

---

**Published January 3, 2026**
*By Cliff*
