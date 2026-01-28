# Asynchronous Task Processing with Celery (Tutorial 007)

**Published January 27, 2026**
*By Cliff*

---

## TL;DR

This tutorial integrates **Celery** for asynchronous task processing into your Django SaaS:

- **Celery with Redis**: Move time-consuming operations (email, notifications) off the request-response cycle
- **Email tasks**: Welcome emails and password resets now async, with automatic retry logic
- **Monitoring with Flower**: Web UI to inspect task execution, worker health, and queue status
- **Custom logging**: Separate worker logs at ERROR/CRITICAL level prevent log spam
- **Production-ready configuration**: Queues, worker concurrency, prefetch multipliers, task timeouts
- **Health check integration**: Verify Celery broker health alongside database checks
- **TDD approach**: Tasks written with comprehensive tests covering success and failure paths

By the end, your application processes emails asynchronously with observable behavior, graceful error handling, and automatic retries.

**Estimated time**: **75–120 minutes**
**Prerequisites**: Completed Tutorials 001–006 (project runs, all tests green, Docker works)

---

## Introduction: Why Asynchronous Tasks Matter

Tutorials 001–006 built a production-ready Django SaaS with authentication, link shortening, containerization, static file serving, logging, and transactional emails. However, the application still sends emails **synchronously** — blocking the user's request until the email is delivered.

This creates problems:
- **Slow registration**: If the email server is slow, users see a delay
- **Failed operations**: Network hiccup during email sends breaks user-facing flows
- **Resource contention**: Long-running tasks block worker threads, reducing capacity
- **Scalability ceiling**: You can't handle spikes without timeouts

Celery solves this by:
1. **Accepting** the task immediately (queued)
2. **Returning** to the user instantly
3. **Processing** the task asynchronously in a separate worker process
4. **Retrying** automatically if something fails
5. **Monitoring** success/failure through a web UI (Flower)

---

## Part 1: Understanding Celery Architecture

### Components

**Broker** (Message Queue)
- Receives tasks from web workers
- Delivers tasks to Celery workers
- We use **Redis** (simple, fast, widely deployed)
- Alternative: RabbitMQ (more complex, enterprise-grade)

**Worker** (Task Executor)
- Listens for tasks from the broker
- Executes task code (send email, cleanup, etc.)
- Reports success/failure
- Retries on failure

**Result Backend** (Task State Store)
- Stores task results and status
- Allows checking if a task succeeded
- Optional; we use Redis for consistency with broker

**Flower** (Monitoring)
- Web UI showing active tasks, workers, queues
- Useful for debugging and performance analysis
- Runs alongside workers

### Architecture Diagram

```
┌──────────────┐
│   Web App    │
│  (Django)    │
└───────┬──────┘
        │ Queue task
        │ (return immediately)
        ▼
┌───────────────┐      ┌──────────────┐
│    Broker     │◄────►│  Result Store │
│    (Redis)    │      │   (Redis)     │
└───────┬───────┘      └──────────────┘
        │ Deliver
        │ (async)
        ▼
┌──────────────────┐
│  Celery Worker   │
│  • Email queue   │
│  • Concurrency=4 │
└──────────────────┘
```

---

## Part 2: Celery Configuration (TDD)

### Step 1: Environment and Dependencies

Celery requires three packages:
- `celery` - Task framework (core dependency)
- `redis` - Broker and result backend (core dependency)
- `flower` - Monitoring UI (optional but recommended)

**Important Design Decision**: Since our application routes all email sending through Celery tasks (registration welcome emails, password reset emails, etc.), `celery` and `redis` are **core dependencies** in `pyproject.toml`, not optional extras. The application will not function properly without them in production.

#### Install

Core dependencies (including celery and redis):
```bash
pip install -e .
```

With development tools and monitoring:
```bash
pip install -e ".[dev]"
```

This installs celery, redis (core), plus flower, black, mypy, etc.

### Step 2: Celery App Initialization (config/celery.py)

The Celery app must be initialized before Django loads tasks:

```python
# config/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("django_saas")
app.config_from_object("django.conf:settings", namespace="CELERY_")
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Test task to verify Celery connectivity."""
    print(f"Request: {self.request!r}")
```

And ensure it's imported when Django starts:

```python
# config/__init__.py
from .celery import app as celery_app
__all__ = ("celery_app",)
```

### Step 3: Settings Configuration (config/settings.py)

Celery reads all settings with the `CELERY_` prefix:

```python
# Message broker and result backend
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default="redis://localhost:6379/0" if not DEBUG else "memory://",
)
CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND",
    default="redis://localhost:6379/1" if not DEBUG else "cache+memory://",
)

# Serialization
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Task behavior
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 min hard limit
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Test mode: execute tasks synchronously and eagerly
if "test" in sys.argv or env.bool("CELERY_ALWAYS_EAGER", default=False):
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Task routing
CELERY_TASK_ROUTES = {
    "core.tasks.send_welcome_email": {"queue": "email"},
    "core.tasks.send_password_reset_email": {"queue": "email"},
    "core.tasks.cleanup_expired_tokens": {"queue": "celery"},
}

# Worker configuration
CELERYD_PREFETCH_MULTIPLIER = env.int("CELERY_PREFETCH_MULTIPLIER", default=4)
CELERYD_MAX_TASKS_PER_CHILD = env.int("CELERY_MAX_TASKS_PER_CHILD", default=1000)
CELERYD_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=25 * 60)
CELERYD_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=30 * 60)

# Task retry configuration
CELERY_TASK_MAX_RETRIES = env.int("CELERY_TASK_MAX_RETRIES", default=3)
CELERY_TASK_DEFAULT_RETRY_DELAY = env.int("CELERY_TASK_DEFAULT_RETRY_DELAY", default=60)
```

**Key Settings Explained:**

- `CELERY_BROKER_URL`: Where tasks are queued. Use `redis://host:6379/0` in production
- `CELERY_RESULT_BACKEND`: Where results are stored. Can differ from broker
- `CELERY_TASK_ALWAYS_EAGER`: In tests, execute tasks synchronously (no separate worker needed)
- `CELERY_TASK_TIME_LIMIT`: Hard timeout (kills task if it exceeds 30 min)
- `CELERYD_PREFETCH_MULTIPLIER`: How many tasks to reserve per worker (4 = reasonable balance)
- `CELERYD_MAX_TASKS_PER_CHILD`: Restart worker process after N tasks (prevents memory leaks)
- `CELERY_TASK_MAX_RETRIES`: Auto-retry failed tasks up to 3 times

---

## Part 3: Email Tasks with Retry Logic

### Step 1: Write Tests (TDD - Red)

Tests define expected behavior before implementation:

```python
# accounts/tests.py
class EmailTaskTests(TestCase):
    """Tests for Celery email tasks."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpassword123",
        )

    def test_send_welcome_email_task_executes(self):
        """Test that send_welcome_email task executes without errors."""
        from core.tasks import send_welcome_email

        result = send_welcome_email.delay(
            user_id=self.user.id,
            login_url="http://localhost:8000/accounts/login/",
        )
        self.assertTrue(result.successful())

    def test_send_welcome_email_task_sends_email(self):
        """Test that send_welcome_email task actually sends an email."""
        from core.tasks import send_welcome_email

        mail.outbox = []
        send_welcome_email.delay(
            user_id=self.user.id,
            login_url="http://localhost:8000/accounts/login/",
        )

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to[0], self.user.email)
        self.assertIn("Welcome", email.subject)

    def test_send_welcome_email_task_handles_invalid_user(self):
        """Test that task handles invalid user gracefully."""
        from core.tasks import send_welcome_email

        result = send_welcome_email.delay(
            user_id=99999,
            login_url="http://localhost:8000/accounts/login/",
        )
        self.assertTrue(result.successful())  # Doesn't raise; handles gracefully
```

Run tests to confirm they fail (Red):

```bash
python manage.py test accounts.tests.EmailTaskTests
```

Expected: `ModuleNotFoundError: No module named 'core.tasks'`

### Step 2: Implement Tasks (Green)

Create `core/tasks.py`:

```python
# core/tasks.py
import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.conf import settings
from django.utils import timezone

from core.email import send_templated_email

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def send_welcome_email(self, user_id: int, login_url: str) -> str:
    """
    Send a welcome email to a newly registered user.

    Args:
        user_id: ID of the user to send welcome email to
        login_url: Absolute URL to the login page

    Returns:
        Status message

    Retries: Up to CELERY_TASK_MAX_RETRIES times with exponential backoff
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(f"send_welcome_email: User with id {user_id} not found")
        return f"User {user_id} not found"

    try:
        send_templated_email(
            subject="Welcome to Django SaaS",
            template_base="emails/welcome_email",
            context={"user": user, "login_url": login_url},
            to=[user.email],
        )
        logger.info(
            "Welcome email sent",
            extra={"user_id": user.id, "email": user.email},
        )
        return f"Welcome email sent to {user.email}"
    except Exception as e:
        logger.error(
            f"Failed to send welcome email to user {user_id}",
            exc_info=True,
            extra={"user_id": user_id},
        )
        raise  # Re-raise to trigger retry mechanism


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def send_password_reset_email(self, user_id: int, reset_link: str) -> str:
    """
    Send a password reset email to a user.

    Args:
        user_id: ID of the user to send password reset email to
        reset_link: Absolute URL to the password reset confirmation page

    Returns:
        Status message

    Retries: Up to CELERY_TASK_MAX_RETRIES times with exponential backoff
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(f"send_password_reset_email: User with id {user_id} not found")
        return f"User {user_id} not found"

    try:
        send_templated_email(
            subject="Password Reset Request",
            template_base="emails/password_reset_email",
            context={"user": user, "reset_link": reset_link},
            to=[user.email],
        )
        logger.info(
            "Password reset email sent",
            extra={"user_id": user.id, "email": user.email},
        )
        return f"Password reset email sent to {user.email}"
    except Exception as e:
        logger.error(
            f"Failed to send password reset email to user {user_id}",
            exc_info=True,
            extra={"user_id": user_id},
        )
        raise


@shared_task()
def cleanup_expired_tokens() -> str:
    """
    Clean up expired session tokens from the database.

    This is a periodic task that should be scheduled with Celery Beat
    to run daily.

    Returns:
        Status message with count of deleted sessions
    """
    now = timezone.now()

    # Count and delete expired sessions
    expired_sessions = Session.objects.filter(expire_date__lt=now)
    count = expired_sessions.count()
    deleted_count, _ = expired_sessions.delete()

    logger.info(
        f"Cleanup task completed: {deleted_count} expired sessions deleted",
        extra={"deleted_count": deleted_count, "timestamp": now.isoformat()},
    )

    return f"Cleanup completed: {deleted_count} expired sessions deleted"
```

**Important Implementation Notes:**

1. **Django Sessions**: This application uses database-backed sessions (`django.contrib.sessions.backends.db`). Expired sessions accumulate in the `django_session` table and should be periodically cleaned up.

2. **Password Reset Tokens**: Django's `PasswordResetTokenGenerator` creates cryptographic tokens based on the user's password hash and last login timestamp. These are **not stored in the database** and don't require cleanup - they're validated on-demand and automatically expire.

3. **Why This Matters**: Without periodic cleanup, the sessions table grows indefinitely, consuming disk space and slowing queries. Schedule this task to run daily via Celery Beat (see Part 11).
```

**Key Decorators:**

```python
@shared_task(
    bind=True,                          # Access self (task instance)
    autoretry_for=(Exception,),         # Retry on any exception
    retry_kwargs={
        "max_retries": 3                # Retry up to 3 times
    },
    retry_backoff=True,                 # Exponential backoff (60s, 120s, 240s)
    retry_backoff_max=600,              # Cap backoff at 10 min
    retry_jitter=True,                  # Add randomness to prevent thundering herd
)
def my_task(...):
    pass
```

Run tests again (Green):

```bash
python manage.py test accounts.tests.EmailTaskTests
```

Expected: All tests pass ✓

### Step 3: Update Views to Use Tasks

Modify `accounts/views.py` to queue tasks instead of sending synchronously:

```python
# accounts/views.py (RegisterView.form_valid)
from core.tasks import send_welcome_email

def form_valid(self, form):
    response = super().form_valid(form)
    logger.info("New user registered", extra={"user_id": self.object.id})

    # Queue welcome email task (doesn't block the user)
    try:
        login_url = self.request.build_absolute_uri(reverse("login"))
        send_welcome_email.delay(user_id=self.object.id, login_url=login_url)
        logger.info("Welcome email task queued", extra={"user_id": self.object.id})
    except Exception as e:
        logger.error(
            f"Failed to queue welcome email: {e}",
            exc_info=True,
            extra={"user_id": self.object.id},
        )

    messages.success(self.request, "Account created successfully! Please log in.")
    return response
```

### Step 4: Route Password Reset Emails Through Celery

Django's `PasswordResetView` uses the form's `save()` method to send emails. To ensure password reset emails go through Celery, override `CustomPasswordResetForm.save()` to enqueue the task and build a full reset URL.

```python
# accounts/forms.py
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.tasks import send_password_reset_email


class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your email"}
        )

    def save(
        self,
        domain_override=None,
        subject_template_name=None,
        email_template_name=None,
        use_https=False,
        token_generator=default_token_generator,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        email = self.cleaned_data["email"]
        protocol = "https" if use_https else "http"

        for user in self.get_users(email):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            path = reverse(
                "password_reset_confirm",
                kwargs={"uidb64": uid, "token": token},
            )

            if request is not None:
                reset_link = request.build_absolute_uri(path)
            else:
                domain = domain_override or "localhost"
                reset_link = f"{protocol}://{domain}{path}"

            send_password_reset_email.delay(
                user_id=user.id,
                reset_link=reset_link,
            )
```

### Step 5: Add Password Reset Email Templates

The password reset task uses `emails/password_reset_email` as its template base, so add both text and HTML templates:

```text
templates/emails/password_reset_email.txt
templates/emails/password_reset_email.html
```

This keeps the task aligned with the existing `send_templated_email()` helper and ensures tests pass.

---

## Part 4: Custom Logging for Workers

### Why Separate Worker Logs?

- **Debugging**: Task failures logged to `celery_worker.log`
- **Monitoring**: Errors in `celery_errors.log` for alerting
- **No spam**: Workers only log errors/critical, not info/debug (too noisy)
- **Retention**: Separate files with rotation prevent unbounded growth

### Configuration

In `config/settings.py`, add file handlers:

```python
# Ensure logs directory exists
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "formatters": {
        "celery": {
            "format": "[{levelname}] {asctime} {name} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "celery_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "celery_worker.log",
            "formatter": "celery",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,     # Keep 10 rotated files
            "level": "ERROR",      # Only log errors and above
        },
        "celery_error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "celery_errors.log",
            "formatter": "celery",
            "maxBytes": 10485760,
            "backupCount": 10,
            "level": "ERROR",      # Only errors
        },
    },
    "loggers": {
        "celery": {
            "handlers": ["console", "celery_file", "celery_error_file"],
            "level": "ERROR",      # Suppress INFO/DEBUG from Celery itself
            "propagate": False,
        },
    },
}

```

**Environment Variables to Control Logging:**

```bash
# Override log levels
CELERY_LOG_LEVEL=WARNING      # Celery framework logs (default: ERROR)
CELERY_TASK_LOG_LEVEL=ERROR   # Task-specific logs (default: ERROR)
DJANGO_LOG_LEVEL=INFO         # Django app logs (default: INFO)
```

### Viewing Logs

**In development:**

```bash
# Watch celery worker errors in real-time
tail -f logs/celery_errors.log

# Inspect all worker activity
tail -f logs/celery_worker.log
```

**In production:**

```bash
# Aggregate logs to a monitoring system
# Example: ELK (Elasticsearch, Logstash, Kibana)
# Example: Datadog, New Relic, Sentry, Splunk
```

---

## Part 5: Running Celery with Docker Compose

### Updated docker-compose.yaml

The project now includes three new services:

**Redis** (Broker & Result Backend)
```yaml
redis:
  image: docker.io/redis:latest
  ports:
    - "6379:6379"
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
```

**Celery Worker** (Task Executor)
```yaml
celery_worker:
  build: .
  command: celery -A config worker -Q email,celery -l info --concurrency=4
  environment:
    CELERY_BROKER_URL: redis://redis:6379/0
    CELERY_RESULT_BACKEND: redis://redis:6379/1
```

**Flower** (Monitoring UI)
```yaml
flower:
  build: .
  command: celery -A config flower --port=5555
  ports:
    - "5555:5555"
```

### Running

```bash
# Start all services
docker-compose up -d

# Verify services are healthy
docker-compose ps

# View logs from a specific service
docker-compose logs -f celery_worker

# Stop services
docker-compose down
```

### Manual Commands Without Docker

If you prefer to run Redis, Celery, and Flower manually (without docker-compose), follow these steps:

#### 1. Start Redis Server

**Windows:**
```bash
# If using Windows Subsystem for Linux (WSL):
wsl redis-server

# Or using Windows Redis (if installed):
redis-server.exe
```

**macOS (with Homebrew):**
```bash
# Start Redis
redis-server

# Or run in background
brew services start redis
```

**Linux:**
```bash
# Ubuntu/Debian
sudo systemctl start redis-server

# Or run directly
redis-server
```

**Verify Redis is running:**
```bash
# In another terminal
redis-cli ping
# Should output: PONG
```

#### 2. Start Celery Worker

**In a new terminal (with virtual environment activated):**

```bash
# Process email queue only, 4 concurrent processes, info level
celery -A config worker -Q email -l info --concurrency=4

# Or process multiple queues
celery -A config worker -Q email,celery -l info --concurrency=4

# For debugging (single process, verbose logging)
celery -A config worker -l debug --concurrency=1 --without-gossip
```

#### 3. Monitor with Flower

**In another new terminal (with virtual environment activated):**

```bash
# Start Flower (monitoring UI)
celery -A config flower --port=5555

# Open http://localhost:5555 in your browser
```

#### 4. Send Test Task

**Test that everything is working:**

```bash
python manage.py shell
>>> from core.tasks import send_welcome_email
>>> send_welcome_email.delay(user_id=1, login_url="http://localhost:8000/accounts/login/")
# <AsyncResult: e1234567-abcd-1234-abcd-1234567890ab>

# Check the worker terminal - you should see the task being processed
```

#### Quick Reference: Terminal Setup

For convenient manual testing, open 4 terminals:

```
Terminal 1: python manage.py runserver
Terminal 2: celery -A config worker -Q email,celery -l info
Terminal 3: celery -A config flower --port=5555
Terminal 4: redis-cli  # (optional, for inspecting Redis)
```

**Useful Redis commands (in Terminal 4):**
```bash
redis-cli
> PING          # Test connection
> KEYS *        # List all keys
> DBSIZE        # Number of keys
> SELECT 0      # Switch to broker DB (tasks)
> SELECT 1      # Switch to result backend DB (task results)
> FLUSHALL      # Clear all data (careful!)
> QUIT          # Exit redis-cli
```

---

## Part 6: Monitoring with Flower

### What Flower Provides

**Tasks Tab:**
- Currently executing tasks
- Task history with duration
- Success/failure status
- Arguments and results

**Workers Tab:**
- Worker status and pool size
- Tasks processed
- CPU and memory usage
- Uptime

**Queues Tab:**
- Active queues
- Pending/undelivered tasks

### Accessing Flower

**Local (docker-compose):**
```
http://localhost:5555
```

**Remote:**
```
# If Flower is behind a proxy, add authentication:
celery -A config flower --port=5555 --basic-auth=admin:password
```

### Flower Dashboard Navigation

1. **Home**: Overview of workers and queue status
2. **Tasks**: All tasks with execution history
3. **Workers**: Individual worker metrics
4. **Queues**: Message queue status
5. **Settings**: Configure Flower behavior

### Production Considerations

- Secure Flower behind authentication
- Run on a private network (not exposed to internet)
- Use another product for persistent metrics (Flower data is in-memory)

---

## Part 7: Health Check Integration

The `/health/` endpoint now checks Celery broker connectivity:

```python
# core/views.py
def health_check(request):
    """
    Health check for load balancers and monitoring.

    Checks:
    - Database connectivity
    - Celery broker connectivity
    """
    health_status = {"status": "ok"}
    http_status = 200

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        logger.error(f"Health check failed (database): {e}")
        health_status["status"] = "error"
        http_status = 503

    # Check Celery broker
    try:
        celery_app.control.inspect().active()
    except Exception as e:
        logger.warning(f"Health check: Celery broker unavailable: {e}")
        # Warning only; Celery down doesn't fail health check
        # (web requests don't depend on Celery running)

    return JsonResponse(health_status, status=http_status)
```

**Usage:**

```bash
# Test health endpoint
curl -s http://localhost:8000/health/ | jq

# Output when healthy:
# {"status": "ok"}

# Output when database down:
# {"status": "error"} [HTTP 503]
```

---

## Part 7.5: Multi-Worker Logging Strategy

### The Problem: Multiprocess Logging with Rotation

When running multiple Celery workers (e.g., `celery -A config worker --concurrency=4`), each worker process writes to log files. If they share the same file, Python's `RotatingFileHandler` causes problems because it's **thread-safe but NOT multiprocess-safe**:

1. **Rotation Race Conditions**: When the file reaches `maxBytes`, one process rotates/renames the file while others are still writing to it
2. **Lost Log Lines**: During rotation, some processes may write to the old file descriptor, losing data
3. **Garbled Output**: Multiple processes can interleave writes even during normal operation

**Source**: [Python Logging Cookbook - Logging to a single file from multiple processes](https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes)

### Our Current Setup: Per-Process Log Files

To avoid multiprocess conflicts, we use **per-process log files** with the process ID (PID) in the filename.

**Current Configuration** (in `config/settings.py`):

```python
import os

"celery_file": {
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOGS_DIR / f"celery_worker-{os.getpid()}.log",  # Unique per process
    "formatter": "celery",
    "maxBytes": 10485760,  # 10MB per file
    "backupCount": 10,
    "level": env("CELERY_LOG_LEVEL", default="ERROR"),
},
"celery_error_file": {
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOGS_DIR / f"celery_errors-{os.getpid()}.log",  # Unique per process
    "formatter": "celery",
    "maxBytes": 10485760,  # 10MB per file
    "backupCount": 10,
    "level": "ERROR",
},
```

**How It Works:**
- Each Celery worker process gets its own log file(s)
- Example: `celery_worker-12345.log`, `celery_worker-12346.log`, etc.
- No lock contention between processes
- Each file can safely rotate independently

**Tradeoffs:**

✅ **Pros:**
- ✅ **No multiprocess conflicts**: Each process owns its file
- ✅ **Safe rotation**: RotatingFileHandler works correctly per-process
- ✅ **Simple**: No external dependencies or configuration
- ✅ **Good for development/testing**: Easy to debug specific workers
- ✅ **Acceptable for light production**: Works well with 2-10 workers

❌ **Cons:**
- ❌ **Many log files**: 4 workers = 8 files (worker + error logs)
- ❌ **Harder to search**: Must grep across multiple files or use aggregation tool
- ❌ **No single timeline**: Need to merge logs by timestamp to see full picture
- ❌ **Disk space**: Total space = workers × (maxBytes × backupCount)
- ❌ **Log management overhead**: More files to monitor, rotate, clean up

**When This Approach Works:**
- Running 1-10 Celery workers
- Development and testing environments
- Light production with manual log inspection
- Short-lived workers (process ID reuse is rare)

**When to Upgrade:**
- Many workers (10+) creating file proliferation
- Need centralized searching/aggregation
- High log volume requiring better management
- Compliance requirements for log integrity
    "maxBytes": 10485760,  # 10MB
    "backupCount": 10,
}
```

**Why This Works:**

- `RotatingFileHandler` has **basic thread-safety** via file locking
- Python's logging module uses locks to prevent corrupted writes
- **Adequate for low-to-medium concurrency** (1-10 workers)
- Simple: no external dependencies

**Limitations:**

- Minor performance overhead under high load
- Rare edge cases where log lines might interleave
- Not ideal for 20+ workers or high-throughput logging

### Production-Safe Logging Strategies

⚠️ **DO NOT use RotatingFileHandler with multiple workers in production!**

Choose one of these proven approaches:

---

#### ✅ Option 1: stdout/stderr + External Rotation (RECOMMENDED)

**The Boring, Reliable Default**

Log to stdout/stderr and let your deployment platform handle aggregation/rotation:

```python
# config/settings.py
LOGGING = {
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "celery",
            "stream": "ext://sys.stdout",  # Explicit stdout
        },
    },
    "loggers": {
        "celery": {
            "handlers": ["console"],  # Only console, no file handlers
            "level": "INFO",
        },
    },
}
```

**Rotation/Aggregation by Platform:**

| Platform | How Logs Are Handled |
|----------|---------------------|
| **Docker** | `docker logs <container>`, use log drivers (json-file, journald, syslog) |
| **systemd** | `journalctl -u celery-worker.service`, automatic rotation via journald |
| **Kubernetes** | `kubectl logs`, forwarded to logging backend (Elasticsearch, CloudWatch) |
| **supervisord** | Captures stdout/stderr, use external logrotate with copytruncate |
| **Heroku** | Logs aggregated to `heroku logs`, add logging add-on for persistence |

**Why This is Best:**
- ✅ No multiprocess conflicts
- ✅ Platform handles rotation correctly
- ✅ Standard for containerized deployments
- ✅ Integrates with centralized logging (Elasticsearch, Splunk, CloudWatch)

**Example: systemd service**

```ini
# /etc/systemd/system/celery-worker.service
[Service]
StandardOutput=journal
StandardError=journal
ExecStart=/path/to/venv/bin/celery -A config worker -l INFO
```

Then view logs: `journalctl -u celery-worker.service -f`

---

#### ✅ Option 2: concurrent-log-handler (Multiprocess-Safe Rotation)

If you MUST rotate files in-process with multiple workers:

```bash
pip install concurrent-log-handler
```

```python
# config/settings.py
LOGGING = {
    "handlers": {
        "celery_file": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "filename": LOGS_DIR / "celery_worker.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            # Uses file locking to coordinate rotation across processes
        },
    },
}
```

**Pros:**
- ✅ Actually safe for multiprocess rotation
- ✅ Drop-in replacement for RotatingFileHandler

**Cons:**
- ❌ Additional dependency
- ❌ File locking overhead
- ❌ Not as robust as external rotation

---

#### Option 3: External Rotation with FileHandler (No In-Process Rotation)

Use non-rotating `FileHandler` + system logrotate:

```python
# config/settings.py
LOGGING = {
    "handlers": {
        "celery_file": {
            "class": "logging.FileHandler",  # No rotation
            "filename": LOGS_DIR / "celery_worker.log",
            "formatter": "celery",
        },
    },
}
```

```bash
# /etc/logrotate.d/celery
/path/to/logs/celery_worker.log {
    daily
    rotate 10
    size 10M
    copytruncate  # Important: doesn't rename, just truncates
    compress
    delaycompress
    notifempty
}
```

**Why This Works:**
- ✅ logrotate uses `copytruncate` - copies and truncates instead of renaming
- ✅ No coordination needed between processes
- ✅ Battle-tested Unix tool

---

#### Option 4: Per-Worker Log Files (OUR CURRENT CHOICE)

**This is what we're using in this tutorial.**

Use process ID in filename to give each worker its own log file:

```python
import os

LOGGING = {
    "handlers": {
        "celery_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / f"celery_worker-{os.getpid()}.log",
            "maxBytes": 10485760,
            "backupCount": 10,
        },
    },
}
```

**Why We Chose This:**
- ✅ **Multiprocess-safe**: Each process owns its file, no conflicts
- ✅ **Simple**: No external dependencies or complex setup
- ✅ **Good for dev/testing/light production**: 1-10 workers manageable
- ✅ **Debug-friendly**: Can tail specific worker logs

**Tradeoffs:**
- ❌ **Many files**: 4 workers = 8 files (worker + error logs)
- ❌ **Search complexity**: Must grep multiple files or use aggregation
- ❌ **No unified timeline**: Need to merge by timestamp

**Example log directory:**
```bash
$ ls logs/
celery_worker-12345.log
celery_worker-12345.log.1
celery_worker-12346.log
celery_errors-12345.log
celery_errors-12346.log
```

**Searching across per-worker logs:**
```bash
# Grep all worker logs
grep "error" logs/celery_worker-*.log

# Merge logs by timestamp (requires sort)
cat logs/celery_worker-*.log | sort

# Use log aggregation tools
# - Papertrail, Loggly, Splunk, ELK stack
# - Or write script to merge by timestamp
```

---

#### Option 5: QueueHandler + QueueListener (Advanced)

Centralized logging via in-memory queue (single writer thread):

```python
from logging.handlers import QueueHandler, QueueListener
import queue

# Create a queue for log records
log_queue = queue.Queue(-1)

LOGGING = {
    "handlers": {
        "queue": {
            "class": "logging.handlers.QueueHandler",
            "queue": log_queue,  # All workers write to queue
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "celery_worker.log",
            "formatter": "celery",
        },
    },
    "loggers": {
        "celery": {
            "handlers": ["queue"],  # Workers use queue
            "level": "INFO",
        },
    },
}

# Start listener in main process (handles file writes)
listener = QueueListener(log_queue, file_handler)
listener.start()
```

**Pros:**
- ✅ No lock contention (single writer thread)
- ✅ Workers never block on I/O
- ✅ Best performance under high load

**Cons:**
- ❌ More complex setup
- ❌ Requires careful process lifecycle management
- ❌ Still uses RotatingFileHandler (single writer makes it safe)

---

#### Option 6: Syslog Handler (Unix/Linux)

Send logs to system logger:

```python
LOGGING = {
    "handlers": {
        "syslog": {
            "class": "logging.handlers.SysLogHandler",
            "address": "/dev/log",  # Unix socket
            "facility": "local0",
            "formatter": "celery",
        },
    },
}
```

**Pros:**
- ✅ System logger handles concurrency
- ✅ Integrates with system logging infrastructure
- ✅ Can forward to rsyslog, journald, etc.

**Cons:**
- ❌ Unix/Linux only
- ❌ Requires syslog configuration
- ❌ Less portable

---

#### Option 7: External Logging Services

Send logs directly to cloud/SaaS services:

```python
# Examples:
# - Sentry (errors + tracing)
# - DataDog (logs + metrics)
# - AWS CloudWatch
# - Elasticsearch + Logstash + Kibana (ELK)
# - Grafana Loki

LOGGING = {
    "handlers": {
        "sentry": {
            "class": "sentry_sdk.integrations.logging.EventHandler",
            "level": "ERROR",
        },
    },
}
```

**Pros:**
- ✅ Built for scale and concurrency
- ✅ Search, alerting, visualization built-in
- ✅ No local disk management

**Cons:**
- ❌ External service dependency
- ❌ Potential costs
- ❌ Network dependency

---

### Summary: Choose Your Strategy

| Strategy | Safety | Complexity | Best For | This Tutorial |
|----------|--------|-----------|----------|---------------|
| **Per-worker files (PID)** | ✅✅ | Low | Dev/testing/light prod | **✓ Current** |
| **stdout/stderr + platform** | ✅✅✅ | Low | Production default | Recommended upgrade |
| **concurrent-log-handler** | ✅✅ | Low | File rotation required | Alternative |
| **FileHandler + logrotate** | ✅✅ | Medium | Unix/Linux | Alternative |
| **QueueHandler + Listener** | ✅✅ | High | In-app centralized | Advanced |
| **Syslog** | ✅✅ | Medium | Unix/Linux | Alternative |
| **External services** | ✅✅✅ | Low-Med | Production with budget | Enterprise |
| **Shared RotatingFileHandler** | ❌ | Low | **NEVER USE** | Avoided |

### For This Tutorial

**Current Setup (Per-Worker Log Files):**
```python
# config/settings.py
"celery_file": {
    "filename": LOGS_DIR / f"celery_worker-{os.getpid()}.log",
    "level": "ERROR",
    "delay": True,  # Only create file when first error occurs
}
```

**Key Optimization:** `delay=True` means the log file is NOT created until the first log record is written. Since we only log `ERROR` level and above, **workers that never encounter errors will never create a log file**. This prevents cluttering your `logs/` directory with empty files from successful workers.

**Why We Chose This:**
- ✅ **Multiprocess-safe**: No rotation conflicts
- ✅ **Simple**: No external dependencies
- ✅ **Serviceable**: Good for dev/testing/light production (1-10 workers)
- ✅ **Debug-friendly**: Can inspect individual worker logs
- ✅ **Clean logs directory**: Only workers with errors create log files

**Tradeoffs Accepted:**
- ⚠️ Multiple log files when errors occur (manageable at small scale)
- ⚠️ Need to search across files (grep, aggregation tools)
- ⚠️ Should upgrade to stdout logging for high-scale production

**Production Recommendation:**
1. **Keep per-worker files** if you have <10 workers and can manage multiple files
2. **Best for scale**: Log to stdout + Docker/systemd/Kubernetes handles aggregation
3. **Also good**: Install `concurrent-log-handler` for single-file rotation
4. **Traditional**: FileHandler + external logrotate with copytruncate

### Monitoring Log Files

With per-worker log files and `delay=True`, **log files are only created when errors occur**. If you don't see any log files, that's good news - no errors!

```bash
# Check log sizes (will show files only from workers that had errors)
du -h logs/

# List all worker log files (empty if no errors yet)
ls -lh logs/celery_worker-*.log

# Watch real-time log growth
watch -n 1 'ls -lh logs/'

# Check rotation is working per worker
ls -l logs/celery_worker-*.log*
```

### Working with Per-Worker Logs

**Viewing individual worker logs:**
```bash
# Tail specific worker
tail -f logs/celery_worker-12345.log

# View all current worker logs
tail -f logs/celery_worker-*.log

# Search across all workers
grep "ERROR" logs/celery_worker-*.log

# Count log files (2 per worker: worker + error)
ls logs/celery_*.log | wc -l
```

**Merging logs by timestamp:**
```bash
# Simple cat (not time-ordered)
cat logs/celery_worker-*.log

# Merge and sort by timestamp (if format allows)
awk '{print $0}' logs/celery_worker-*.log | sort -k2,3

# Use multitail for live monitoring
multitail logs/celery_worker-*.log
```

### Testing Multi-Worker Logging

**Test with per-worker files:**

```bash
# Start 4 workers (will create 8 log files: 4 worker + 4 error)
celery -A config worker --concurrency=4 -l INFO

# Check that separate files were created
ls -l logs/

# Expected output:
# celery_worker-12345.log
# celery_worker-12346.log
# celery_worker-12347.log
# celery_worker-12348.log
# celery_errors-12345.log
# celery_errors-12346.log
# celery_errors-12347.log
# celery_errors-12348.log

# Send tasks
python manage.py shell
>>> from core.tasks import send_welcome_email
>>> for i in range(100):
...     send_welcome_email.delay(user_id=1, login_url="http://localhost:8000")

# View logs from specific worker
tail -f logs/celery_worker-12345.log

# Search all workers for errors
grep "ERROR" logs/celery_worker-*.log
```

**Cleanup old worker logs:**
```bash
# Remove logs from dead workers (pids not running)
# Be careful - only do this when workers are stopped
find logs/ -name "celery_worker-*.log" -mtime +7 -delete
```

**Advantages of Per-Worker Files:**
- ✅ No rotation corruption (each process manages its own file)
- ✅ Can identify which worker had issues
- ✅ Safe to delete old logs after worker restarts
- ✅ No lock contention between workers
- ✅ With `delay=True`: files only created when errors occur (no empty log clutter)

---

## Part 8: Production Hardening

### Security Best Practices

#### Anti-User-Enumeration Pattern

**Why we don't raise errors when users aren't found:**

```python
# core/tasks.py
try:
    user = User.objects.get(id=user_id)
except User.DoesNotExist:
    logger.warning(f"send_password_reset_email: User with id {user_id} not found")
    return f"User {user_id} not found"  # ✅ Logs internally, doesn't raise
```

**Security Rationale:**

1. **Prevents User Enumeration Attacks**: If the system raises an error saying "user not found", attackers can determine which emails are registered in your system by observing different responses.

2. **Timing Attack Prevention**: Same response time and behavior whether user exists or not prevents attackers from using timing differences to enumerate accounts.

3. **Information Disclosure**: Revealing which emails exist in your database is a privacy and security leak.

**This follows Django's built-in `PasswordResetView` behavior:**

From Django docs: *"If any of these conditions are not met, no email will be sent, but the user won't receive any error message either. This prevents information leaking to potential attackers."*

**The same principle applies to:**
- Login forms (say "Invalid credentials" not "User doesn't exist")
- Password reset forms
- Account verification systems

**What we DO:**
- ✅ Log warnings for monitoring/debugging (server-side only)
- ✅ Return consistent success messages to users
- ✅ Track failed attempts with identical timing

**What we DON'T do:**
- ❌ Raise exceptions that could leak to users
- ❌ Show different error messages for "user not found" vs other errors
- ❌ Allow timing differences to reveal user existence

### Configuration Best Practices

#### 1. **Task Timeouts**

```python
# settings.py
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 min: graceful exit
CELERY_TASK_TIME_LIMIT = 30 * 60       # 30 min: SIGKILL if still running
```

A task has 5 minutes to clean up between soft and hard limits.

#### 2. **Worker Concurrency**

```bash
# Celery worker scaling
celery -A config worker --concurrency=4

# For CPU-bound tasks (link validation, processing):
# concurrency = number of CPU cores

# For I/O-bound tasks (email, HTTP):
# concurrency = 4-8x CPU cores (tasks spend time waiting)

# Our email tasks are I/O-bound, so concurrency=4 is reasonable for 1 core
```

#### 3. **Prefetch Multiplier**

```python
CELERYD_PREFETCH_MULTIPLIER = 4  # Each worker reserves 4 tasks at a time
```

- Higher = Better throughput but less fair distribution
- Lower = Better fairness but more broker chatter
- Default of 4 is balanced

#### 4. **Max Tasks Per Child**

```python
CELERYD_MAX_TASKS_PER_CHILD = 1000  # Restart worker after 1000 tasks
```

Prevents memory leaks in long-lived workers.

#### 5. **Retry Strategy**

```python
# Exponential backoff with jitter
@shared_task(
    autoretry_for=(Exception,),
    retry_kwargs={
        "max_retries": 3,
        "countdown": 60,  # First retry after 60s
    },
    retry_backoff=True,        # Double each time: 60, 120, 240
    retry_backoff_max=600,     # Cap at 10 min
    retry_jitter=True,         # Add ±10% random jitter
)
def my_task():
    pass
```

Jitter prevents all workers from retrying at the same moment (thundering herd).

### Monitoring in Production

**Option 1: Prometheus + Grafana**

```python
# Install celery-prometheus-exporter
pip install celery-prometheus-exporter

# Run exporter (separate process)
celery-prometheus-exporter --broker redis://redis:6379/0 --port 8888

# Scrape metrics in Prometheus
# Create Grafana dashboards for task rates, latencies, failures
```

**Option 2: Custom Logging + ELK Stack**

```python
# Settings: Send logs to Elasticsearch
# Kibana: Query and visualize task failures
# Alerting: If error rate exceeds threshold
```

**Option 3: Third-Party Services**

- **Sentry**: Error tracking for failed tasks
- **DataDog**: Metrics, traces, logs
- **New Relic**: Application monitoring
- **Honeycomb**: Observability

### Dead Letter Queue Pattern

For tasks that repeatedly fail:

```python
# Create a 'dead-letter' queue
CELERY_TASK_ROUTES = {
    "core.tasks.send_email": {"queue": "email"},
}

CELERY_QUEUES = {
    "email": {"exchange": "email", "routing_key": "email"},
    "dead_letter": {"exchange": "dead_letter", "routing_key": "dead_letter"},
}
```

Override retry handler to route to dead letter:

```python
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
)
def my_task(self):
    try:
        # Do work
        pass
    except RetryableException:
        # Retry normally
        raise
    except FatalException as e:
        # Send to dead letter queue
        logger.error(f"Task {self.id} fatal error: {e}")
        # Manually move to dead letter or skip
```

---

## Part 9: Troubleshooting Guide

### Common Issues and Solutions

#### **Tasks Not Running**

**Symptom:** Tasks are queued but not executing

**Diagnosis:**
```bash
# Check if worker is running
ps aux | grep celery

# Check broker connectivity
redis-cli ping

# Inspect active tasks
celery -A config inspect active
```

**Solutions:**
1. Start Celery worker: `celery -A config worker -l info`
2. Check broker URL: `CELERY_BROKER_URL=redis://localhost:6379/0`
3. Verify Redis is running: `docker-compose up redis`

#### **Tasks Keep Retrying Infinitely**

**Symptom:** Task fails and retries forever without stopping

**Cause:** Misconfigured retry logic

**Fix:**
```python
@shared_task(
    autoretry_for=(NetworkException,),  # Only retry on specific exceptions
    # NOT: autoretry_for=(Exception,) - too broad
    retry_kwargs={"max_retries": 3},
)
def my_task():
    pass
```

#### **Worker Memory Growing**

**Symptom:** Celery worker process uses increasing RAM

**Causes:**
- Memory leak in task code
- `CELERYD_MAX_TASKS_PER_CHILD` too high
- No result backend cleanup

**Solutions:**
```python
# Lower max tasks per child
CELERYD_MAX_TASKS_PER_CHILD = 500  # Restart more frequently

# Use result expiration
CELERY_RESULT_EXPIRES = 3600  # Delete results after 1 hour

# Profile the task
import tracemalloc
@shared_task
def my_task():
    tracemalloc.start()
    # Do work
    current, peak = tracemalloc.get_traced_memory()
    logger.info(f"Memory: {peak / 10**6} MB")
```

#### **Tasks Timing Out**

**Symptom:** Task takes longer than `CELERY_TASK_TIME_LIMIT` and is killed

**Solutions:**
```python
# Increase time limit if task legitimately needs time
CELERY_TASK_TIME_LIMIT = 60 * 60  # 1 hour for long-running tasks

# Or break task into smaller subtasks
@shared_task
def process_large_dataset():
    items = Item.objects.all()
    for batch in chunks(items, 100):
        process_batch.delay(batch_ids=[i.id for i in batch])

@shared_task
def process_batch(batch_ids):
    # Smaller, faster task
    pass
```

#### **Broker Connection Errors**

**Symptom:** `ConnectionError: Error -2 connecting to localhost:6379`

**Solutions:**
```bash
# Verify Redis is running
redis-cli ping

# Check broker URL
echo $CELERY_BROKER_URL

# Test connection
python -c "import redis; redis.Redis.from_url('redis://localhost:6379/0').ping()"
```

#### **No Tasks in Flower Dashboard**

**Symptom:** Tasks execute but don't appear in Flower

**Cause:** Flower not connected to same broker

**Fix:**
```bash
# Verify Flower is pointing to correct broker
celery -A config flower --broker=redis://redis:6379/0

# Check docker-compose: services must reference same Redis
```

---

## Part 10: Testing Celery Tasks

### Unit Tests (No Broker Required)

```python
# accounts/tests.py
class EmailTaskTests(TestCase):
    def setUp(self):
        # Set CELERY_ALWAYS_EAGER in settings for test mode
        self.user = User.objects.create_user(...)

    def test_send_welcome_email_task_executes(self):
        """Task executes synchronously in tests."""
        from core.tasks import send_welcome_email
        result = send_welcome_email.delay(user_id=self.user.id, login_url="...")
        self.assertTrue(result.successful())


# core/tests.py
class CeleryTaskTests(TestCase):
    """Tests for Celery cleanup and maintenance tasks."""

    def test_cleanup_expired_tokens_deletes_expired_sessions(self):
        """Test that cleanup_expired_tokens deletes expired sessions from database."""
        from core.tasks import cleanup_expired_tokens
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()

        # Create an expired session (1 day in the past)
        expired_session = Session.objects.create(
            session_key="expired_session_key_123",
            expire_date=now - timedelta(days=1),
            session_data="test_data",
        )

        # Create a valid session (1 day in the future)
        valid_session = Session.objects.create(
            session_key="valid_session_key_456",
            expire_date=now + timedelta(days=1),
            session_data="test_data",
        )

        # Verify both sessions exist
        self.assertEqual(Session.objects.count(), 2)

        # Run cleanup task
        result = cleanup_expired_tokens.delay()

        # Verify expired session was deleted
        self.assertFalse(Session.objects.filter(pk=expired_session.pk).exists())

        # Verify valid session still exists
        self.assertTrue(Session.objects.filter(pk=valid_session.pk).exists())
        self.assertEqual(Session.objects.count(), 1)

        # Check return message
        self.assertIn("1 expired sessions deleted", result.result)
```

**Test Configuration:**

In `config/settings.py`, tests automatically use eager mode:

```python
if "test" in sys.argv:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
```

This means:
- Tasks execute immediately (no Redis needed)
- Exceptions propagate to test code
- Perfect for unit testing task logic

### Integration Tests (Real Broker Optional)

To test with a real Redis broker:

```bash
# Start Redis in Docker
docker run -d -p 6379:6379 redis:7-alpine

# Run tests normally (not in eager mode)
# Set in .env or environment:
CELERY_ALWAYS_EAGER=false

# Run specific test
python manage.py test accounts.tests.EmailTaskTests
```

### Mocking Task Execution

For views that queue tasks:

```python
# accounts/tests.py
from unittest.mock import patch

class RegistrationEmailTests(TestCase):
    @patch("accounts.views.send_welcome_email.delay")
    def test_registration_queues_welcome_email(self, mock_send_email):
        """Test that registration queues (but doesn't execute) the task."""
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "pass123",
                "password2": "pass123",
            },
        )

        # Assert task was queued
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs["user_id"], User.objects.get(email="new@example.com").id)
```

---

## Part 11: Advanced Topics (Deferred)

Future tutorials will cover:

### **Celery Beat** (Scheduled Tasks)
```python
# Periodic tasks
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "cleanup-tokens-daily": {
        "task": "core.tasks.cleanup_expired_tokens",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
    },
}
```

### **Task Chains and Workflows**
```python
# Sequential task execution
from celery import chain

task1.s(arg1) | task2.s(arg2) | task3.s(arg3)

# Parallel execution
from celery import group
group(task1.s(), task2.s(), task3.s())()
```

### **Rate Limiting**
```python
# Limit task execution rate
@shared_task(rate_limit="10/m")  # 10 per minute
def rate_limited_task():
    pass
```

---

## Summary: What You've Learned

✅ **Celery architecture**: Broker, worker, result backend, monitoring
✅ **Configuration**: Redis, queues, retry logic, timeouts
✅ **Email tasks**: Welcome and password reset as async operations
✅ **Custom logging**: Per-worker files with `delay=True` (files only created on errors)
✅ **Docker Compose**: Redis, Celery worker, Flower services
✅ **Manual setup**: Run Celery/Flower/Redis without Docker
✅ **Monitoring**: Flower UI + health check integration
✅ **Production hardening**: Timeouts, concurrency, prefetch, dead letters
✅ **Troubleshooting**: Common issues and solutions
✅ **Testing**: Unit tests with eager mode, integration tests

---

## Environment Variables Reference

```bash
# Broker and backend
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Worker tuning
CELERY_PREFETCH_MULTIPLIER=4
CELERY_MAX_TASKS_PER_CHILD=1000
CELERY_TASK_SOFT_TIME_LIMIT=1500  # 25 min
CELERY_TASK_TIME_LIMIT=1800       # 30 min

# Retry behavior
CELERY_TASK_MAX_RETRIES=3
CELERY_TASK_DEFAULT_RETRY_DELAY=60

# Logging
CELERY_LOG_LEVEL=ERROR
CELERY_TASK_LOG_LEVEL=ERROR

# Testing
CELERY_ALWAYS_EAGER=true
```

---

## Next Steps

1. **Run the test suite**: `python manage.py test`
2. **Start services**: `docker-compose up -d`
3. **Monitor tasks**: Open http://localhost:5555 (Flower)
4. **Register a user**: Watch welcome email queue and execute
5. **Check logs**: `tail -f logs/celery_worker.log`

For future tutorials:
- **Stripe integration**: Queue webhook processing tasks
- **Scheduled jobs**: Cleanup, reports, notifications via Celery Beat
- **Background data processing**: Import/export, link validation

---
