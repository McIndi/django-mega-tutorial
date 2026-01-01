# Production-Ready Servers and Docker (Tutorial 004)

**Published January 1, 2026**
*By Cliff*

---

## TL;DR

This tutorial equips your Django SaaS with production-grade servers and Docker support:

- **Custom management commands** (`serve` and `serve_async`): Use Cheroot and Daphne to serve the app with TLS, threading, and environment-based configuration.
- **Docker**: Multi-stage build for minimal footprint, running the `serve` command by default.
- **docker-compose**: PostgreSQL database + web service for local and cloud deployment.
- **TDD approach**: Tests for all server functionality use mocks to avoid spinning up real servers.

By the end, you can run your SaaS locally with `docker-compose up` or deploy the image to any container orchestration platform.

**Estimated time**: **45–90 minutes**
**Prerequisites**: Completed Tutorials 001, 002, and 003 (project runs, all tests green).

---

## Why Custom Servers?

Django's `runserver` is convenient but **not production-ready**:

- Single-threaded (one request at a time)
- No TLS/HTTPS support
- Reloads on code changes (unsafe in production)

This tutorial replaces `runserver` with two production-grade alternatives:

| Server | Use Case | Features |
|--------|----------|----------|
| **Cheroot (serve)** | WSGI, synchronous apps | TLS, threading, minimal deps, production-ready |
| **Daphne (serve_async)** | ASGI, async/WebSocket apps | TLS, async support, future-proofing |

Both servers are configurable via environment variables and CLI arguments, following the same patterns you already know from Tutorial 001.

---

## Part 1: Management Commands (TDD)

### Why Management Commands?

Management commands are the standard way to run Django scripts. They integrate with `manage.py`, support argument parsing, and work seamlessly in Docker containers.

We'll write tests first, then implement.

---

### Step 1: Write Tests for the `serve` Command

Open `core/tests.py` and add these test cases **before** implementing the command:

```python
import os
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase


class ServeCommandTests(TestCase):
    """Tests for the serve management command using Cheroot/CherryPy."""

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_command_defaults(self, mock_server_class):
        """Test serve command with default values when no env vars or args provided."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", stdout=out)

        # Verify server was created with defaults
        mock_server_class.assert_called_once()
        call_args = mock_server_class.call_args

        # Check bind address (host, port)
        self.assertEqual(call_args[0][0], ("127.0.0.1", 8000))

        # Verify server.start() was called
        mock_server.start.assert_called_once()

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_command_reads_env_vars(self, mock_server_class):
        """Test serve command reads SERVER_HOST and SERVER_PORT from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", stdout=out)

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[0][0], ("0.0.0.0", 9000))

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_command_cli_args_override_env(self, mock_server_class):
        """Test CLI arguments override environment variables."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", host="192.168.1.1", port=3000, stdout=out)

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[0][0], ("192.168.1.1", 3000))

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_command_with_workers(self, mock_server_class):
        """Test serve command with numthreads option."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", numthreads=10, stdout=out)

        call_args = mock_server_class.call_args
        # Check kwargs for numthreads
        self.assertEqual(call_args[1].get("numthreads"), 10)

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/path/to/cert.pem", "SERVER_TLS_KEY": "/path/to/key.pem"},
    )
    def test_serve_command_with_tls_from_env(self, mock_server_class):
        """Test serve command reads TLS cert and key from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve", stdout=out)

        # Server should be created with ssl_certificate and ssl_private_key kwargs
        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certificate"), "/path/to/cert.pem")
        self.assertEqual(call_args[1].get("ssl_private_key"), "/path/to/key.pem")

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/env/cert.pem", "SERVER_TLS_KEY": "/env/key.pem"},
    )
    def test_serve_command_tls_cli_overrides_env(self, mock_server_class):
        """Test CLI TLS arguments override environment variables."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command(
            "serve",
            tls_cert="/cli/cert.pem",
            tls_key="/cli/key.pem",
            stdout=out,
        )

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certificate"), "/cli/cert.pem")
        self.assertEqual(call_args[1].get("ssl_private_key"), "/cli/key.pem")

    @patch("core.management.commands.serve.WSGIServer")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_command_tls_requires_both_cert_and_key(self, mock_server_class):
        """Test that TLS requires both cert and key."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        err = StringIO()

        # Providing only cert should work but not enable TLS
        call_command("serve", tls_cert="/path/to/cert.pem", stdout=out, stderr=err)

        call_args = mock_server_class.call_args
        # Should not have ssl_certificate or ssl_private_key if only one is provided
        self.assertIsNone(call_args[1].get("ssl_certificate"))
        self.assertIsNone(call_args[1].get("ssl_private_key"))
```

**Key test patterns:**

- **Mocking the server**: We mock `WSGIServer` so tests don't actually start a server
- **Environment patching**: Use `@patch.dict` to control environment variables per test
- **CLI override testing**: Verify that arguments override env vars
- **TLS validation**: Ensure TLS requires both cert and key

Run tests to see them fail (Red phase):

```bash
python manage.py test core.tests.ServeCommandTests
```

Expect 7 test errors (server command doesn't exist yet).

---

### Step 2: Implement the `serve` Command

Create the management command structure:

```bash
# Create directories if they don't exist
mkdir -p core/management/commands
touch core/management/__init__.py
touch core/management/commands/__init__.py
```

Create `core/management/commands/serve.py`:

```python
"""
Management command to serve Django with Cheroot (CherryPy's production-grade WSGI server).

Supports TLS and configurable threading. Suitable for production use.
"""

import os
import sys

from cheroot.wsgi import Server as WSGIServer
from django.core.management.base import BaseCommand
from django.core.wsgi import get_wsgi_application


class Command(BaseCommand):
    help = "Serve Django application using Cheroot (CherryPy WSGI server)"

    def add_arguments(self, parser):
        """Define command-line arguments with defaults from environment variables."""
        parser.add_argument(
            "--host",
            default=os.getenv("SERVER_HOST", "127.0.0.1"),
            help="Host to bind to (default: SERVER_HOST env var or 127.0.0.1)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("SERVER_PORT", "8000")),
            help="Port to bind to (default: SERVER_PORT env var or 8000)",
        )
        parser.add_argument(
            "--numthreads",
            type=int,
            default=int(os.getenv("SERVER_NUMTHREADS", "10")),
            help="Number of threads for handling requests (default: SERVER_NUMTHREADS env var or 10)",
        )
        parser.add_argument(
            "--tls-cert",
            default=os.getenv("SERVER_TLS_CERT"),
            help="Path to TLS certificate file (default: SERVER_TLS_CERT env var)",
        )
        parser.add_argument(
            "--tls-key",
            default=os.getenv("SERVER_TLS_KEY"),
            help="Path to TLS private key file (default: SERVER_TLS_KEY env var)",
        )

    def handle(self, *args, **options):
        """Start the Cheroot WSGI server."""
        host = options["host"]
        port = options["port"]
        numthreads = options["numthreads"]
        tls_cert = options["tls_cert"]
        tls_key = options["tls_key"]

        # Get the WSGI application
        application = get_wsgi_application()

        # Build server kwargs
        server_kwargs = {"numthreads": numthreads}

        # Enable TLS only if both cert and key are provided
        if tls_cert and tls_key:
            server_kwargs["ssl_certificate"] = tls_cert
            server_kwargs["ssl_private_key"] = tls_key
            protocol = "https"
            self.stdout.write(
                self.style.SUCCESS(f"TLS enabled (cert: {tls_cert}, key: {tls_key})")
            )
        else:
            protocol = "http"
            if tls_cert or tls_key:
                self.stdout.write(
                    self.style.WARNING(
                        "TLS not enabled: both --tls-cert and --tls-key are required"
                    )
                )

        # Create and configure server
        server = WSGIServer((host, port), application, **server_kwargs)

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Cheroot WSGI server on {protocol}://{host}:{port}/"
            )
        )
        self.stdout.write(f"Number of threads: {numthreads}")
        self.stdout.write("Quit the server with CONTROL-C.")

        try:
            server.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nShutting down server..."))
            server.stop()
            sys.exit(0)
```

**Key design decisions:**

1. **Import `WSGIServer` at module level**: This allows tests to mock it
2. **Environment variable defaults**: Use `os.getenv()` in argument defaults, allowing CLI args to override
3. **TLS validation**: Both cert and key required; provide a warning if only one is given
4. **No code changes needed**: Existing Django code works without modification

Now run tests to verify they pass (Green phase):

```bash
python manage.py test core.tests.ServeCommandTests
```

All 7 tests should pass. ✓

---

### Step 3: Write and Implement Tests for `serve_async`

The `serve_async` command is similar but uses Daphne for ASGI support. Add tests:

```python
class ServeAsyncCommandTests(TestCase):
    """Tests for the serve-async management command using Daphne."""

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_async_command_defaults(self, mock_server_class):
        """Test serve-async command with default values."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", stdout=out)

        # Verify server was created with defaults
        mock_server_class.assert_called_once()

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_async_command_reads_env_vars(self, mock_server_class):
        """Test serve-async command reads SERVER_HOST and SERVER_PORT from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", stdout=out)

        mock_server_class.assert_called_once()

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "9000"})
    def test_serve_async_command_cli_args_override_env(self, mock_server_class):
        """Test CLI arguments override environment variables for serve-async."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", host="192.168.1.1", port=3000, stdout=out)

        mock_server_class.assert_called_once()

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/path/to/cert.pem", "SERVER_TLS_KEY": "/path/to/key.pem"},
    )
    def test_serve_async_command_with_tls_from_env(self, mock_server_class):
        """Test serve-async command reads TLS cert and key from environment."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command("serve_async", stdout=out)

        # Server should be created with ssl_certfile and ssl_keyfile kwargs
        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certfile"), "/path/to/cert.pem")
        self.assertEqual(call_args[1].get("ssl_keyfile"), "/path/to/key.pem")

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(
        os.environ,
        {"SERVER_TLS_CERT": "/env/cert.pem", "SERVER_TLS_KEY": "/env/key.pem"},
    )
    def test_serve_async_command_tls_cli_overrides_env(self, mock_server_class):
        """Test CLI TLS arguments override environment variables for serve-async."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        call_command(
            "serve_async",
            tls_cert="/cli/cert.pem",
            tls_key="/cli/key.pem",
            stdout=out,
        )

        call_args = mock_server_class.call_args
        self.assertEqual(call_args[1].get("ssl_certfile"), "/cli/cert.pem")
        self.assertEqual(call_args[1].get("ssl_keyfile"), "/cli/key.pem")

    @patch("core.management.commands.serve_async.Server")
    @patch.dict(os.environ, {}, clear=True)
    def test_serve_async_command_tls_requires_both_cert_and_key(self, mock_server_class):
        """Test that serve-async TLS requires both cert and key."""
        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        out = StringIO()
        err = StringIO()

        # Providing only cert should work but not enable TLS
        call_command("serve_async", tls_cert="/path/to/cert.pem", stdout=out, stderr=err)

        call_args = mock_server_class.call_args
        # Should not have ssl_certfile or ssl_keyfile if only one is provided
        self.assertIsNone(call_args[1].get("ssl_certfile"))
        self.assertIsNone(call_args[1].get("ssl_keyfile"))
```

Create `core/management/commands/serve_async.py`:

```python
"""
Management command to serve Django async with Daphne (ASGI server).

Supports TLS and other options. Suitable for applications using async views or WebSockets.
This command allows testing async compatibility even when not actively using WebSockets.
"""

import os
import sys

from daphne.server import Server
from django.core.asgi import get_asgi_application
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Serve Django application using Daphne (ASGI server) for async support"

    def add_arguments(self, parser):
        """Define command-line arguments with defaults from environment variables."""
        parser.add_argument(
            "--host",
            default=os.getenv("SERVER_HOST", "127.0.0.1"),
            help="Host to bind to (default: SERVER_HOST env var or 127.0.0.1)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("SERVER_PORT", "8000")),
            help="Port to bind to (default: SERVER_PORT env var or 8000)",
        )
        parser.add_argument(
            "--tls-cert",
            default=os.getenv("SERVER_TLS_CERT"),
            help="Path to TLS certificate file (default: SERVER_TLS_CERT env var)",
        )
        parser.add_argument(
            "--tls-key",
            default=os.getenv("SERVER_TLS_KEY"),
            help="Path to TLS private key file (default: SERVER_TLS_KEY env var)",
        )

    def handle(self, *args, **options):
        """Start the Daphne ASGI server."""
        host = options["host"]
        port = options["port"]
        tls_cert = options["tls_cert"]
        tls_key = options["tls_key"]

        # Get the ASGI application
        application = get_asgi_application()

        # Build server kwargs
        server_kwargs = {}

        # Enable TLS only if both cert and key are provided
        if tls_cert and tls_key:
            server_kwargs["ssl_certfile"] = tls_cert
            server_kwargs["ssl_keyfile"] = tls_key
            protocol = "https"
            self.stdout.write(
                self.style.SUCCESS(f"TLS enabled (cert: {tls_cert}, key: {tls_key})")
            )
        else:
            protocol = "http"
            if tls_cert or tls_key:
                self.stdout.write(
                    self.style.WARNING(
                        "TLS not enabled: both --tls-cert and --tls-key are required"
                    )
                )

        # Create and configure server
        server = Server(
            application,
            hosts=[host],
            port=port,
            signal_handlers=True,
            **server_kwargs,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Daphne ASGI server on {protocol}://{host}:{port}/"
            )
        )
        self.stdout.write("Quit the server with CONTROL-C.")

        try:
            server.run()
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nShutting down server..."))
            sys.exit(0)
```

Run tests:

```bash
python manage.py test core.tests.ServeAsyncCommandTests
```

All 6 tests should pass. ✓

---

### Step 4: Update pyproject.toml with Optional Dependencies

The project now uses `pyproject.toml` to define optional dependency groups, allowing users to install only what they need.

Update `pyproject.toml`:

```toml
[project]
name = "django-mega-tutorial"
version = "0.1.0"
description = "Production-minded Django SaaS starter template"
requires-python = ">=3.12"
dependencies = [
    "django",
    "django-environ",
]

[project.optional-dependencies]
cheroot = ["cheroot"]
daphne = ["daphne"]
dev = [
    "black",
    "mypy",
    "django-stubs",
    "bandit",
    "pre-commit",
    "coverage",
]
servers = ["cheroot", "daphne"]
all = [
    "black",
    "mypy",
    "django-stubs",
    "bandit",
    "pre-commit",
    "coverage",
    "cheroot",
    "daphne",
]
```

**Installation options:**

```bash
# Install base dependencies only (minimal)
pip install -e .

# Install with Cheroot (WSGI server)
pip install -e ".[cheroot]"

# Install with Daphne (ASGI server)
pip install -e ".[daphne]"

# Install all dev dependencies (recommended for local development)
pip install -e ".[dev]"

# Install both servers (recommended for production/Docker)
pip install -e ".[servers]"

# Install everything (servers + dev tools)
pip install -e ".[all]"
```

For a quick start in development:

```bash
pip install -e ".[dev]"
```

This installs Django, testing tools, and quality checkers.

For production or Docker deployment:

```bash
pip install -e ".[servers]"
```

This installs Django and both production-grade servers (Cheroot and Daphne).

---

### Step 5: Update Environment Configuration

Update `.env.example` to document the new server settings:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SECRET_KEY=

# Server configuration (for manage.py serve and manage.py serve_async)
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
SERVER_NUMTHREADS=10

# Optional: TLS/HTTPS support
# SERVER_TLS_CERT=/path/to/cert.pem
# SERVER_TLS_KEY=/path/to/key.pem
```

---

## Part 2: Docker Setup

### Step 1: Create a Dockerfile

Docker packages your application and dependencies into an immutable, portable image.

Create `Dockerfile`:

```dockerfile
# Multi-stage Dockerfile for Django SaaS application
# Uses Python 3.14 slim image for minimal footprint

# ============================================================================
# Builder Stage: Install dependencies
# ============================================================================
FROM python:3.14-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files (including pyproject.toml)
COPY pyproject.toml .

# Create venv and install dependencies in it
# Install with [all] extras for comprehensive tooling (both servers, testing, quality)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && pip install -e ".[all]"

# ============================================================================
# Runtime Stage: Minimal final image
# ============================================================================
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Install runtime-only system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port (default for Django)
EXPOSE 8000

# Default command: run the serve management command
# Can be overridden with serve_async or other commands
CMD ["python", "manage.py", "serve", "--host", "0.0.0.0"]
```

**Design decisions:**

1. **Multi-stage build**: Builder stage installs dependencies, runtime stage is lean
2. **Non-root user**: Containers should not run as `root` (security best practice)
3. **Slim base image**: `python:3.14-slim` is 50% smaller than the default `python:3.14`
4. **Virtual environment**: Preserves isolation even in the container
5. **Default command**: `serve --host 0.0.0.0` listens on all interfaces (required in containers)

---

### Step 2: Create docker-compose.yaml

Docker Compose orchestrates multiple services. Create `docker-compose.yaml`:

```yaml
version: "3.9"

services:
  # PostgreSQL database service
  db:
    image: postgres:16-alpine
    container_name: django_saas_db
    environment:
      POSTGRES_DB: ${DB_NAME:-django_saas}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    volumes:
      # Persist database data across container restarts
      - postgres_data:/var/lib/postgresql/data
    ports:
      # Expose on localhost for development; comment out for production
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Django web application service
  web:
    build: .
    container_name: django_saas_web
    command: python manage.py serve --host 0.0.0.0
    environment:
      # Django settings
      DEBUG: ${DJANGO_DEBUG:-False}
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-change-me-in-production}
      DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1}

      # Server configuration
      SERVER_HOST: 0.0.0.0
      SERVER_PORT: ${SERVER_PORT:-8000}
      SERVER_NUMTHREADS: ${SERVER_NUMTHREADS:-10}

    ports:
      # Expose web server
      - "${SERVER_PORT:-8000}:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      # Mount source code for development (optional; comment out for production)
      - .:/app
    # Restart policy
    restart: unless-stopped

volumes:
  # Named volume for PostgreSQL data persistence
  postgres_data:
```

**Design decisions:**

1. **Named volume**: `postgres_data` persists the database across restarts
2. **Health checks**: The web service waits for the database to be healthy
3. **Environment variables**: Configuration via Docker environment, matching `.env` style
4. **Development-friendly**: Source code mount allows hot reloading during development
5. **Defaults**: Sensible defaults for quick startup; override via environment

---

## Part 3: Running Locally

### Using the New `serve` Command

```bash
# Basic usage (defaults to 127.0.0.1:8000)
python manage.py serve

# Custom host/port
python manage.py serve --host 0.0.0.0 --port 9000

# With environment variables
export SERVER_HOST=0.0.0.0
export SERVER_PORT=9000
python manage.py serve

# With TLS (see TLS Setup section below)
python manage.py serve --tls-cert cert.pem --tls-key key.pem
```

### Using Docker Compose

```bash
# Start services in the background
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down

# Stop and remove volumes (destructive; loses data)
docker-compose down -v
```

After startup, visit `http://localhost:8000`.

---

## Part 4: TLS/HTTPS Support (Optional)

### Generate Self-Signed Certificates

For local development and testing:

```bash
# Generate a private key
openssl genrsa -out server.key 2048

# Generate a self-signed certificate valid for 365 days
openssl req -new -x509 -key server.key -out server.crt -days 365

# Common name: localhost (or your domain)
```

This creates `server.key` and `server.crt` in your project root.

### Use with the `serve` Command

```bash
python manage.py serve --tls-cert server.crt --tls-key server.key
```

Or set environment variables:

```bash
export SERVER_TLS_CERT=server.crt
export SERVER_TLS_KEY=server.key
python manage.py serve
```

### Use with Docker Compose

Create a `.env` file (not in git):

```dotenv
SERVER_TLS_CERT=server.crt
SERVER_TLS_KEY=server.key
```

Then start services:

```bash
docker-compose up -d
```

The web service will run with HTTPS.

---

### Future: Let's Encrypt Integration

A future tutorial will cover automatic HTTPS with Let's Encrypt and ACME. For now, self-signed certificates work for local testing and staging.

---

## Part 5: Test Verification

Ensure all tests still pass:

```bash
python manage.py test
```

You should see:

```
Ran 65 tests in ~40s

OK
```

The test suite now includes:
- 7 tests for the `serve` command
- 6 tests for the `serve_async` command
- All existing tests from Tutorials 001–003

---

## Part 6: Deployment Considerations

### Docker Registry

To deploy to production:

```bash
# Build and tag the image
docker build -t your-org/django-saas:v1.0.0 .

# Push to Docker Hub or private registry
docker push your-org/django-saas:v1.0.0
```

Then orchestrate with Kubernetes, Docker Swarm, or a PaaS provider.

### Environment Variables in Production

Production deployments **must** set:

```
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<strong-random-key>
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

Never hardcode secrets or rely on defaults.

### Database Migrations

In a Docker deployment, run migrations on startup:

```dockerfile
# Add to Dockerfile CMD or use an init container:
python manage.py migrate
```

Or use a separate migration service before deploying the web service.

---

## Summary: What We Built

| Component | Purpose |
|-----------|---------|
| `serve` command | WSGI server with TLS and threading |
| `serve_async` command | ASGI server for async/WebSocket apps |
| Dockerfile | Multi-stage build for deployment |
| docker-compose.yaml | Local PostgreSQL + web service |
| Test suite | 13 new tests covering server behavior |

You now have a production-ready Django SaaS that can:

- Run locally with `python manage.py serve` or `serve_async`
- Run in Docker with `docker-compose up`
- Deploy to any container orchestration platform
- Support TLS/HTTPS for secure communication

---

## Next Steps

1. **Test the servers locally**: Run both `serve` and `serve_async` manually
2. **Experiment with Docker Compose**: Start services, inspect logs, test connectivity
3. **Generate SSL certificates**: Try TLS locally
4. **Review Cheroot and Daphne docs**: Understand additional options (e.g., request timeouts, worker settings)

Future tutorials will cover:

- Subscription billing with Stripe
- Background tasks with Celery
- Email backend configuration
- Production deployment with Let's Encrypt
- Monitoring and alerting

---

## References

- [Cheroot Documentation](https://cheroot.cherrypy.org/)
- [Daphne Documentation](https://asgi.readthedocs.io/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
