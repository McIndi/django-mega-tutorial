# Building a Django SaaS App: Testing, Code Quality, and CI

**Published December 30, 2025**
*By Cliff*

---

## TL;DR

This tutorial extends the Django SaaS foundation from Tutorial 001 by introducing **automated testing and quality gates**.

It covers:

* Converting manual verification into an automated test suite
* Expanding test coverage for authentication, password reset, admin, and edge cases
* Adding code quality tools:

  * **Black** for formatting
  * **MyPy** for static type checking
  * **Bandit** for security scanning
* Enforcing checks locally with **pre-commit**
* Running the same checks automatically with **GitHub Actions CI**

By the end, the project has a repeatable workflow where correctness, consistency, and basic security checks are enforced on every commit.

**Estimated time**: 90–120 minutes
**Prerequisites**: Completed Tutorial 001; Git repository initialized

---

## Introduction: Why Quality Matters for SaaS

Tutorial 001 focused on establishing a runnable Django SaaS foundation and verifying it manually:

* registration
* login/logout
* profile access
* admin access

Manual verification is necessary early, but it does not scale. It captures correctness at a moment in time, not over the lifetime of the codebase.

This tutorial formalizes those checks into **automated tests** and introduces **quality tooling** that runs continuously, both locally and in CI. These practices reduce regressions, improve confidence when making changes, and establish a baseline that real SaaS teams expect.

---

## Reference Results (Example Implementation)

To provide a concrete target, the example implementation accompanying this tutorial was run through the full workflow described below.

The reference run produced:

* 38 tests executed, all passing
* Black formatting checks passing (after formatting was applied)
* MyPy reporting zero type errors
* Bandit reporting no HIGH or CRITICAL findings

These numbers are **not guarantees**. They represent what a correct implementation looks like for this codebase at this stage. Differences usually indicate configuration, dependency version, or environment issues. A consolidated execution summary is included for comparison.

---

## Part 1: Establish a Test Baseline

### From Manual Verification to Automated Tests

Tutorial 001 relied on manual verification to confirm the app worked. This tutorial converts those same checks into automated tests that can be re-run consistently.

The focus is on behaviors most likely to break in an early SaaS application:

* authentication and session handling
* password reset flows
* admin permissions
* form validation and edge cases

### Test Structure

The project uses Django’s built-in `TestCase`, which provides:

* an isolated database per test run
* transaction rollback between tests
* full middleware and authentication behavior
* template rendering and message framework support

This makes it suitable for integration-style tests without additional tooling.

### Test Inventory (Reference)

In the example implementation, tests are organized by responsibility:

* User model and manager behavior
* Registration and login forms
* Authentication views
* Password reset flow
* Admin interface
* Security and edge cases
* End-to-end integration flows
* Core views

A full reference list of tests and their intent is included here.

---

## Part 2: Extending the Test Suite

This section describes the additional tests added to cover high-risk workflows. Each subsection outlines *what to test* and *why it matters*.

### Password Reset Flow Tests

Password reset is a multi-step, security-sensitive workflow involving:

* token generation and validation
* redirects
* email delivery
* session state

Tests cover:

* rendering the reset request form
* handling valid and invalid email submissions
* validating password reset tokens
* rejecting expired or invalid tokens
* completing the password reset

A critical detail is Django’s security behavior: after validating a token, the framework redirects to a session-based URL that removes the token from the address bar. Tests must follow this redirect before submitting the new password. This prevents token leakage via browser history or referrer headers.

---

### Admin Interface Tests

Admin tests verify that:

* non-staff users cannot access the admin
* staff and superusers can view and manage users
* password handling behaves correctly when creating or editing users

For a custom user model, this requires:

* inheriting from `PermissionsMixin`
* using Django’s `UserAdmin` rather than a plain `ModelAdmin`

These tests ensure the admin interface remains functional as the user model evolves.

---

### Security and Edge Case Tests

These tests focus on failure modes that often go unnoticed early:

* duplicate usernames or emails
* unusually long input values
* special characters in passwords
* CSRF enforcement
* SQL injection attempts treated as literal input

The goal is not to simulate a full penetration test, but to ensure basic framework protections are active and validated.

---

### Integration Tests

Integration tests verify that multiple components work together correctly:

* register → login → profile
* register → login → logout
* full password reset flow

These tests catch issues that isolated unit tests do not, such as broken redirect chains, session persistence problems, or missing middleware configuration.

---

## Part 3: Code Quality Tools

This tutorial introduces three tools that address different failure modes:

| Tool   | Purpose                  |
| ------ | ------------------------ |
| Black  | Deterministic formatting |
| MyPy   | Static type checking     |
| Bandit | Security scanning        |

Together, they form a lightweight quality gate suitable for a growing SaaS codebase.

### Black: Code Formatting

Black enforces a single, deterministic formatting style.

Configuration lives in `pyproject.toml`. Once configured:

```bash
black .
black --check .
```

Black reformats code only; it does not change behavior. In the reference run, four files were reformatted with no functional changes.

---

### MyPy: Static Type Checking

MyPy checks for type mismatches before runtime.

With `django-stubs`, MyPy understands Django models, querysets, and settings.

```bash
mypy .
```

Type hints can be added gradually. The configuration allows untyped code while still checking typed sections. The reference run reported no errors.

---

### Bandit: Security Scanning

Bandit scans Python code for common security issues:

* hardcoded secrets
* unsafe function usage
* insecure subprocess calls
* weak cryptography

```bash
bandit -r . -ll
```

Tests and migrations are excluded to reduce false positives. The reference scan reported no HIGH or CRITICAL issues.

---

## Part 4: Pre-Commit Hooks

Pre-commit runs checks locally before commits are created.

Typical setup:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Configured hooks include:

* Black
* MyPy
* Bandit
* whitespace and YAML checks

If a hook fails, the commit is blocked until the issue is fixed.

---

## Part 5: GitHub Actions CI

CI ensures the same checks run in a clean environment on every push and pull request.

### Minimal CI Workflow (SQLite)

This workflow matches the current project setup and avoids unnecessary services:

```yaml
name: CI

on:
  push:
  pull_request:
jobs:
  test-and-quality:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Create .env for CI
        run: |
          echo "DJANGO_SECRET_KEY=ci-test-key" > .env
          echo "DJANGO_DEBUG=False" >> .env
          echo "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1" >> .env

      - name: Run tests with coverage
        run: |
          coverage run --source='.' manage.py test
          coverage report

      - name: Run Black
        run: black --check .

      - name: Run MyPy
        run: mypy .

      - name: Run Bandit
        run: bandit -r . -c .bandit.yaml -ll
```

This is sufficient until database-specific behavior requires Postgres.

---

## Part 6: Running Locally

### Daily Workflow

```bash
python manage.py test
black --check .
mypy .
bandit -r . -ll
```

A single combined check:

```bash
black --check . && mypy . && bandit -r . -ll -c .bandit.yaml && python manage.py test
```

---

## Cheat Sheet

### Tests

```bash
python manage.py test
python manage.py test accounts
python manage.py test accounts.tests.PasswordResetFlowTests
```

### Coverage

```bash
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Quality

```bash
black .
mypy .
bandit -r . -ll
pre-commit run --all-files
```

---

## Conclusion and Next Steps

At the end of this tutorial, the project has:

* an automated test suite covering authentication and critical flows
* deterministic formatting
* static type checking infrastructure
* basic security scanning
* local and CI enforcement

These practices do not guarantee correctness, but they **dramatically reduce risk** as the codebase evolves.

### What Comes Next

Tutorial 003 will build on this foundation by introducing:

* deployment and operational hardening

---

## Series Status

| Tutorial     | Focus                   | Status   |
| ------------ | ----------------------- | -------- |
| Tutorial 001 | Django SaaS foundation  | Complete |
| Tutorial 002 | Testing, quality, CI    | Complete |
| Tutorial 003 | Deployment              | Upcoming |
