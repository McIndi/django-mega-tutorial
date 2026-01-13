# Django SaaS Mega-Tutorial

A production-minded Django SaaS starter template with email-based authentication, automated testing, and CI/CD pipeline.

## Overview

This project provides a clean foundation for building a Django-based SaaS application. It prioritizes correctness, security, and maintainability over quick shortcuts, making it suitable for solo founders, technical leaders, and developers evaluating Django as a SaaS platform.

### Key Features

- **Email-first authentication** - Custom user model with email as the primary identifier
- **Complete auth flows** - Registration, login, logout, password reset, and profile management
- **Bootstrap 5 UI** - Responsive, accessible design with light/dark theme toggle
- **Automated testing** - Comprehensive test suite covering authentication, forms, views, and edge cases
- **Code quality tools** - Black, MyPy, and Bandit for formatting, type checking, and security scanning
- **CI/CD ready** - GitHub Actions workflow with pre-commit hooks
- **Environment-based configuration** - Secure settings management with django-environ

## Project Structure

```
├── accounts/              # User authentication and management
│   ├── models.py         # Custom user model
│   ├── forms.py          # Bootstrap-styled auth forms
│   ├── views.py          # Registration and auth views
│   ├── urls.py           # Auth-related URLs
│   └── templates/        # Auth templates (login, register, password reset, etc.)
├── config/               # Project configuration
│   ├── settings.py       # Django settings with environment variables
│   ├── urls.py           # Root URL configuration
│   └── wsgi.py          # WSGI application
├── core/                 # Core app for non-auth pages
│   ├── views.py         # Homepage and shared views
│   ├── urls.py          # Core URLs
│   └── templates/       # Shared base template and homepage
├── .env                  # Environment variables (not in git)
├── .env.example          # Environment variable template
├── requirements.txt      # Python dependencies
├── pyproject.toml       # Tool configuration (Black, MyPy)
├── .bandit.yaml         # Bandit security scanner configuration
├── .pre-commit-config.yaml # Pre-commit hooks
└── manage.py            # Django management script
```

## Prerequisites

- Python 3.14 or newer (Although will likely work on 3.12+)
- Git
- Basic familiarity with Django and the command line

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/McIndi/django-mega-tutorial
cd django-mega-tutorial

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip
```

### 2. Install Dependencies

Choose the installation option that suits your needs:

```bash
# Development (with testing and quality tools)
pip install -e ".[dev]"

# Production servers only (Cheroot + Daphne)
pip install -e ".[servers]"

# Everything (development + servers)
pip install -e ".[all]"

# Minimal (base only)
pip install -e .
```

We recommend `pip install -e ".[dev]"` for local development.

### 3. Configure Environment

```bash
# Copy example environment file
copy .env.example .env  # Windows
# cp .env.example .env  # macOS/Linux

# Edit .env and set your values:
# - DJANGO_SECRET_KEY (generate a secure key)
# - DJANGO_DEBUG=True for development
# - DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Initialize Database

```bash
# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
python manage.py serve
```

Visit [http://127.0.0.1:8000](http://127.0.0.1:8000) to see the application.

## Running with Docker

To run the application with Docker and PostgreSQL:

```bash
# Start services (database + web)
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# View logs
docker-compose logs -f web

# Stop services
docker-compose down
```

The application will be available at [http://localhost:8000](http://localhost:8000).

See [Tutorial 004](tutorial-004.md) for detailed Docker setup and customization.

**Podman tips:**
- Use fully qualified images (e.g., `docker.io/postgres:18-alpine`) to avoid short-name resolution errors.
- After changing the Dockerfile (such as copying the source before `pip install -e .`), run `podman-compose build --no-cache` so the builder sees the new context.

## Testing

### Run Tests

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test accounts

# Run a specific test class
python manage.py test accounts.tests.PasswordResetFlowTests
```

### Test Coverage

```bash
# Run tests with coverage
coverage run --source='.' manage.py test

# View coverage report
coverage report

# Generate HTML coverage report
coverage html
```

The test suite includes:
- User model and manager behavior
- Registration and login forms
- Authentication views and flows
- Password reset workflow
- Admin interface permissions
- Security and edge case handling
- End-to-end integration tests

## Code Quality

### Formatting with Black

```bash
# Format all code
black .

# Check formatting without changes
black --check .
```

### Type Checking with MyPy

```bash
# Run type checks
mypy .
```

### Security Scanning with Bandit

```bash
# Scan for security issues
bandit -r . -ll -c .bandit.yaml
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run all hooks manually
pre-commit run --all-files
```

### Combined Quality Check

```bash
# Run all quality checks at once
black --check . && mypy . && bandit -r . -ll -c .bandit.yaml && python manage.py test
```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** - Write code following Django best practices

3. **Run tests and quality checks**
   ```bash
   python manage.py test
   black .
   mypy .
   bandit -r . -ll -c .bandit.yaml
   ```

4. **Commit your changes** - Pre-commit hooks will run automatically
   ```bash
   git add .
   git commit -m "Your commit message"
   ```

5. **Push and create PR** - CI will run tests and quality checks
   ```bash
   git push origin feature/your-feature-name
   ```

## Key Design Decisions

### Custom User Model

The project uses a custom user model with **email as the primary identifier** instead of username. This is standard for SaaS applications and must be configured before initial migrations.

```python
USERNAME_FIELD = 'email'
REQUIRED_FIELDS = ['username']
```

### Environment-Based Configuration

All environment-specific settings (secrets, debug flags, hosts) are managed via environment variables using `django-environ`. This separates configuration from code and supports different environments (dev, staging, production).

### Bootstrap Forms

Authentication forms are styled with Bootstrap classes at the form level, avoiding hardcoded colors and maintaining theme compatibility.

### Security Best Practices

- CSRF protection enforced
- Logout uses POST method (not GET)
- Password reset tokens validated securely
- Environment variables for secrets
- Security scanning with Bandit

## CI/CD Pipeline

The GitHub Actions workflow runs on every push and pull request:

1. **Setup** - Installs Python and dependencies
2. **Tests** - Runs full test suite with coverage
3. **Quality** - Checks formatting (Black), types (MyPy), and security (Bandit)

See [.github/workflows/ci.yml](.github/workflows/ci.yml) for details.

## Available Pages

- `/` - Homepage
- `/accounts/register/` - User registration
- `/accounts/login/` - User login
- `/accounts/logout/` - User logout (POST)
- `/accounts/profile/` - User profile (requires authentication)
- `/accounts/password-reset/` - Password reset request
- `/admin/` - Django admin interface

## Dependencies

Core dependencies:
- **Django** - Web framework
- **django-environ** - Environment variable management
- **coverage** - Test coverage measurement

Development dependencies:
- **black** - Code formatting
- **mypy** - Static type checking
- **django-stubs** - Django type stubs for MyPy
- **bandit** - Security issue scanner
- **pre-commit** - Git hook framework

## Tutorials

This project is built following a comprehensive tutorial series:

1. **[Tutorial 001](tutorial-001.md)** - Django SaaS Foundation
   - Environment setup and project initialization
   - Custom user model with email authentication
   - Authentication views, forms, and templates
   - Core app and shared UI
   - Bootstrap integration with theme toggle

2. **[Tutorial 002](tutorial-002.md)** - Testing, Code Quality, and CI
   - Automated test suite
   - Code quality tools (Black, MyPy, Bandit)
   - Pre-commit hooks
   - GitHub Actions CI workflow

3. **[Tutorial 003](tutorial-003.md)** - Building a Link Shortener
   - User-scoped link shortening feature
   - Model design and CRUD operations
   - TDD approach: Red → Green → Refactor
   - Analytics with Click tracking

4. **[Tutorial 004](tutorial-004.md)** - Production-Ready Servers and Docker
   - Custom management commands (serve, serve_async)
   - Cheroot and Daphne WSGI/ASGI servers
   - TLS/HTTPS support
   - Dockerfile with multi-stage build
   - docker-compose with PostgreSQL

5. **More tutorials coming soon** - Topics will include subscription billing, background tasks, Let's Encrypt integration, and production monitoring

## Why Django for SaaS?

Django's strength is not that it's "simple," but that it's **complete**. Authentication, admin tooling, ORM, migrations, and security primitives are all first-class. For SaaS products, this matters more than novelty.

Key advantages:
- **Batteries included** - Built-in authentication, admin, ORM
- **Mature ecosystem** - Established patterns and libraries
- **Security-first** - Strong defaults and security primitives
- **Scalable** - Grows with complexity rather than fighting it
- **Predictable** - Convention over configuration where it matters

## Contributing

This is a tutorial project demonstrating best practices. If you find issues or have suggestions:

1. Check existing issues
2. Create a new issue describing the problem or enhancement
3. Submit a pull request with tests and documentation

## License

[Specify your license here]

## Author

Built by Cliff as part of the Django SaaS Mega-Tutorial series.

Published _.

---

## Next Steps

After getting familiar with this foundation:

1. **Add your domain logic** - Create new apps for your SaaS features
2. **Configure production deployment** - Topics covered in an upcoming tutorial
3. **Add subscription billing** - Integrate Stripe or similar payment processor (upcoming tutorial)
4. **Customize the UI** - Replace the default Bootstrap theme with your brand
5. **Add email backend** - Configure SMTP or a service like SendGrid for password resets
6. **Set up monitoring** - Add error tracking and performance monitoring
7. **Scale as needed** - Add caching, CDN, background tasks when traffic grows

Remember: Start simple, measure usage, scale based on actual needs.
