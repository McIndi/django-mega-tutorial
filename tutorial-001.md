# Building a Django SaaS App Template
Or The Django SaaS Mega-Tutorial

## From Scratch to Subscription-Ready (Part 1)

**Published December 30, 2025**
*By Cliff*

---

## TL;DR

This tutorial walks through building a **clean, production-minded Django SaaS starter** from scratch. You’ll set up environment-based settings, implement an email-first custom user model, wire authentication flows, and build a responsive Bootstrap UI. By the end, you’ll have a runnable local application suitable for free-tier users and ready to evolve into a paid SaaS.

Production deployment and subscription billing are intentionally deferred to later tutorials.

---

## Who This Is For

This guide is written for:

* **Solo founders** who want a solid SaaS starting point
* **Developers** who want fewer shortcuts and more correctness
* **Technical leaders** evaluating Django as a SaaS platform

You don’t need deep Django expertise, but you should be comfortable reading Python and using the command line.

---

## Prerequisites

* Python 3.10 or newer
* Basic familiarity with Git and virtual environments
* Estimated time: **30–90 minutes**

---

## Table of Contents

* Environment setup and project initialization
* Email-based custom user model
* Authentication views, forms, and templates
* Core app and shared UI
* Testing and local verification
* Project structure and flow diagrams
* Production notes and gotchas

---

## One-Page Quick Reference

### Key Commands

```bash
# Create and activate a virtual environment (Windows)
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Create project and apps
django-admin startproject config .
python manage.py startapp accounts

# Migrations and local run
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Key Files

* `config/settings.py` — environment loading, security, auth model
* `accounts/models.py` — custom user model
* `accounts/forms.py` — Bootstrap-styled auth forms
* `accounts/views.py` — registration and login flows
* `core/templates/core/base.html` — shared layout and navigation

---

## Why Django for SaaS?

Django’s strength is not that it’s “simple,” but that it’s **complete**.

Authentication, admin tooling, ORM, migrations, and security primitives are all first-class. For SaaS products, this matters more than novelty. You want predictable behavior, strong defaults, and a framework that scales with complexity rather than fighting it.

This tutorial reflects that philosophy. We avoid shortcuts that feel convenient early but cause friction later, especially around authentication, settings, and structure.

---

## Step 1: Environment Setup and Project Initialization

### Goals

In this step, you will:

* Create an isolated Python environment
* Install minimal dependencies
* Initialize a Django project with environment-based settings

### Virtual Environment

Always start with isolation. It prevents dependency conflicts and makes builds reproducible.

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

---

### Dependencies

Create a `requirements.txt` file:

```
django
django-environ
```

Install:

```bash
python -m pip install -r requirements.txt
```

**Why these?**

* `django` — the framework
* `django-environ` — structured, explicit environment management

We keep dependencies minimal on purpose.

---

### Create the Project

```bash
django-admin startproject config .
```

Using `config` as the project name keeps the structure clean and avoids semantic confusion later when adding domain-specific apps.

---

### Environment-Based Settings

Edit `config/settings.py`:

```python
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
env.read_env(BASE_DIR / '.env')
```

Replace hardcoded values:

```python
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])
```

Create `.env`:

```dotenv
DJANGO_SECRET_KEY=replace-me-with-a-real-secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

**Why this matters**

Hardcoded secrets leak. Environment variables scale cleanly from local dev to CI to production. `.env.example` doubles as documentation for collaborators and automation.

Validate early:

```bash
python manage.py check
```

---

## Step 2: Custom User Model (Email-First)

Email-based authentication is the norm for SaaS. Django allows this cleanly, but **only if you do it early**.

### Create the Accounts App

```bash
python manage.py startapp accounts
```

---

### Custom User Model

`accounts/models.py`:

```python
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password):
        user = self.create_user(username, email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class CustomUser(AbstractBaseUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email
```

Register it in `config/settings.py`:

```python
INSTALLED_APPS += ['accounts']
AUTH_USER_MODEL = 'accounts.CustomUser'
```

> ⚠️ **Important**
> `AUTH_USER_MODEL` must be set **before** initial migrations. Changing it later is painful and error-prone.

Run migrations:

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

---

## Step 3: Authentication Views, Forms, and Templates

This step wires user registration, login, logout, and profile views.

### Forms with Bootstrap Styling

`accounts/forms.py`:

```python
from django import forms
from .models import CustomUser

class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
```

**Guideline:**
Add layout classes only. Avoid hardcoded colors that will clash with theming later.

---

### Views and URLs

Use Django’s built-in auth views where possible. They are secure, tested, and boring in the best way.

* Class-based views for registration
* Built-ins for login/logout/reset
* Function views only when simplicity wins

Templates live under `accounts/templates/accounts/` and extend a shared base.

---

## Step 4: Core App and Shared UI

Create a `core` app for non-auth pages:

```bash
python manage.py startapp core
```

This app owns:

* The homepage
* Shared layout (`base.html`)
* Navigation and theme toggle

### Base Template

Use Bootstrap 5 and a single shared navbar. Authentication state controls visible links. Logout is a POST form to avoid side effects from browser caching and to follow HTTP conventions (state-changing operations should use POST, not GET).

Theme toggling is client-side and minimal:

```html
<script>
    const toggle = document.getElementById('theme-toggle');
    toggle?.addEventListener('click', () => {
        document.documentElement.classList.toggle('dark');
        localStorage.theme =
            document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    });
</script>
```

---

## Deep Dive: Shared Base Template and Authentication Pages

At this point in the tutorial, we’ve referenced a shared base template and several authentication pages without looking at them in detail. This section fills that gap.

These templates are intentionally simple, explicit, and boring. That’s a feature, not a bug. SaaS applications benefit from predictability and clarity, especially around authentication flows.

---

## The Shared Base Template (`core/base.html`)

This file defines the global layout, navigation, Bootstrap inclusion, and light/dark theme toggle. Every page in the app extends it.

### Full Listing: `core/templates/core/base.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}My SaaS App{% endblock %}</title>

    <link
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css"
        rel="stylesheet"
        integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB"
        crossorigin="anonymous"
    >

    {% block extra_head %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg bg-light navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'index' %}">My SaaS App</a>

            <button
                class="navbar-toggler"
                type="button"
                data-bs-toggle="collapse"
                data-bs-target="#navbarNav"
                aria-controls="navbarNav"
                aria-expanded="false"
                aria-label="Toggle navigation"
            >
                <span class="navbar-toggler-icon"></span>
            </button>

            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'index' %}">Home</a>
                    </li>

                    {% if user.is_authenticated %}
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'profile' %}">Profile</a>
                    </li>
                    {% endif %}
                </ul>

                <ul class="navbar-nav">
                    {% if user.is_authenticated %}
                        <li class="nav-item">
                            <form method="post" action="{% url 'logout' %}" style="display: inline;">
                                {% csrf_token %}
                                <button type="submit" class="btn btn-link nav-link" style="border: none; padding: 0; background: none; cursor: pointer;">Logout</button>
                            </form>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="{% url 'login' %}">Login</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{% url 'register' %}">Register</a>
                        </li>
                    {% endif %}

                    <li class="nav-item">
                        <button
                            id="theme-toggle"
                            class="btn btn-link nav-link"
                            type="button"
                        >
                            🌙
                        </button>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% block content %}{% endblock %}
    </div>

    <script
        src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI"
        crossorigin="anonymous"
    ></script>

    <script>
        document.addEventListener('DOMContentLoaded', function () {
            const themeToggle = document.getElementById('theme-toggle');
            const html = document.documentElement;
            const navbar = document.querySelector('.navbar');

            const currentTheme = localStorage.getItem('theme') || 'light';
            html.setAttribute('data-bs-theme', currentTheme);
            updateNavbar();
            updateIcon();

            themeToggle.addEventListener('click', () => {
                const newTheme =
                    html.getAttribute('data-bs-theme') === 'dark'
                        ? 'light'
                        : 'dark';

                html.setAttribute('data-bs-theme', newTheme);
                localStorage.setItem('theme', newTheme);
                updateNavbar();
                updateIcon();
            });

            function updateNavbar() {
                const isDark = html.getAttribute('data-bs-theme') === 'dark';
                navbar.classList.toggle('bg-light', !isDark);
                navbar.classList.toggle('bg-dark', isDark);
                navbar.classList.toggle('navbar-light', !isDark);
                navbar.classList.toggle('navbar-dark', isDark);
            }

            function updateIcon() {
                const isDark = html.getAttribute('data-bs-theme') === 'dark';
                themeToggle.innerHTML = isDark ? '☀️' : '🌙';
            }
        });
    </script>

    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Why This Template Works Well

A few intentional choices worth calling out:

* **Single responsibility**: layout, navigation, and theme only
* **No inline business logic**: only auth-aware conditionals
* **Client-side theme toggle**: no database writes, no sessions
* **Bootstrap via CDN**: simple for tutorials, easy to replace later

This template is stable enough to survive early SaaS growth without becoming a dumping ground for unrelated concerns.

---

## Authentication Template Example: Login Page

The login template demonstrates a reusable pattern you’ll see across all auth-related pages: centered card layout, form iteration, and consistent error handling.

### Full Listing: `accounts/login.html`

```html
{% extends 'core/base.html' %}

{% block title %}Login{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6 col-lg-4">
        <div class="card">
            <div class="card-body">
                <h2 class="card-title text-center">Login</h2>

                <form method="post">
                    {% csrf_token %}

                    {% if form.non_field_errors %}
                        <div class="alert alert-danger">
                            {{ form.non_field_errors }}
                        </div>
                    {% endif %}

                    {% for field in form %}
                        <div class="mb-3">
                            {{ field.label_tag }}
                            {{ field }}

                            {% if field.help_text %}
                                <div class="form-text">
                                    {{ field.help_text }}
                                </div>
                            {% endif %}

                            {% if field.errors %}
                                <div class="text-danger">
                                    {{ field.errors }}
                                </div>
                            {% endif %}
                        </div>
                    {% endfor %}

                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">
                            Login
                        </button>
                    </div>
                </form>

                <div class="mt-3 text-center">
                    <p>
                        <a href="{% url 'password_reset' %}">
                            Forgot password?
                        </a>
                    </p>
                    <p>
                        Don't have an account?
                        <a href="{% url 'register' %}">Register here</a>
                    </p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

### Design Notes

* **Field iteration** keeps templates resilient to form changes
* **Explicit CSRF token** reinforces security habits
* **No custom JavaScript** required for validation
* **Consistent spacing** via Bootstrap utilities only

This pattern repeats cleanly for password reset and registration pages.

---

## Authenticated Page Example: Profile

The profile page shows how authenticated data is surfaced safely and readably.

### Full Listing: `accounts/profile.html`

```html
{% extends 'core/base.html' %}

{% block title %}Profile{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <h2>Welcome to your profile, {{ user.username }}!</h2>

        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Your Information</h5>

                <p><strong>Username:</strong> {{ user.username }}</p>
                <p><strong>Email:</strong> {{ user.email }}</p>
                <p><strong>Member since:</strong> {{ user.date_joined|date:"F j, Y" }}</p>
                <p><strong>Last login:</strong> {{ user.last_login|date:"F j, Y, g:i a" }}</p>
                <p>
                    <strong>Staff status:</strong>
                    {% if user.is_staff %}Yes{% else %}No{% endif %}
                </p>
                <p>
                    <strong>Superuser status:</strong>
                    {% if user.is_superuser %}Yes{% else %}No{% endif %}
                </p>
            </div>
        </div>

        <div class="mt-3">
            <a href="{% url 'index' %}" class="btn btn-secondary">
                Back to Home
            </a>
            <form method="post" action="{% url 'logout' %}" style="display: inline;">
                {% csrf_token %}
                <button type="submit" class="btn btn-danger ms-2">Logout</button>
            </form>
        </div>
    </div>
</div>
{% endblock %}
```

### Why This Matters

This page is intentionally simple:

* It proves authentication is wired correctly
* It validates the custom user model
* It provides a natural landing page after login

In later tutorials, this page becomes the obvious place to surface subscription status, billing links, and feature access.

---

## Password Reset Templates (Brief Note)

The remaining password reset templates (`password_reset_email.html`, `password_reset_confirm.html`, etc.) follow the same structural patterns:

* Extend `core/base.html`
* Centered card layout
* Clear success and error messaging

They are intentionally thin wrappers around Django’s built-in password reset views, which is exactly what you want for security-sensitive flows.

---

## Closing Note on Templates

These templates are not flashy. They are:

* **Readable**
* **Predictable**
* **Easy to reason about**
* **Safe to extend**

That combination is far more valuable in a SaaS foundation than clever abstractions or premature design systems.

---

## Step 5: Testing and Local Verification

Create an admin user:

```bash
python manage.py createsuperuser
```

Run the app:

```bash
python manage.py runserver
```

Verify:

* Registration
* Login / logout
* Profile access
* Admin panel

At this point, the app is fully runnable and coherent.

---

## Production Notes (Preview Only)

Deployment, scaling, and billing are covered later. For now, keep these principles in mind:

* `.env` stays out of Git
* Use Postgres in production
* Run `collectstatic`
* Disable `DEBUG`
* Serve via Gunicorn + Nginx
* Add logging and monitoring before launch

---

## Final Thoughts

This tutorial intentionally avoids shortcuts. The goal is not to impress with cleverness, but to create a **boring, reliable SaaS foundation** that survives growth.

In the next tutorials, we’ll layer on:

* Stripe subscriptions
* Feature gating
* Production deployment
* CI and operational hardening

Start free. Build trust. Monetize later.

That’s how SaaS actually works.
