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
