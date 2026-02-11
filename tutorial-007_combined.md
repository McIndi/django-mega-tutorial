# Tutorial 007

## Docker, TLS, and Asynchronous Workloads in Django

**Published February 2026**
*By Cliff*

---

## TL;DR

In this tutorial, we take a Django application that “works” and turn it into one that behaves **predictably under production constraints**.

Along the way, we fix real problems you *will* encounter:

* Environment variables that exist at runtime but not at build time
* Permission errors caused by bind mounts and SELinux
* HTTPS security settings that assume TLS even when none exists
* Slow request paths caused by synchronous background work
* Confusing Celery behavior in tests vs production

By the end, you’ll have:

* A Docker workflow that matches production reality
* TLS that is **optional but safe**
* Asynchronous email and click tracking with Celery
* Clear separation between **build-time**, **runtime**, and **background work**
* Defaults that are strict in production and forgiving in development

This is not about adding complexity.
It’s about removing surprises.

---

## What “Production-Ready” Actually Means

Before we touch code, let’s define terms.

**Production-ready does not mean:**

* more configuration
* harder local development
* more services for the sake of it

**Production-ready means:**

* behavior is predictable
* failures are understandable
* configuration intent is explicit
* shortcuts are intentional, not accidental

Most production bugs come from *implicit assumptions*:

* “This env var will exist”
* “This directory will be writable”
* “HTTPS is always on”
* “This operation is fast enough”

This tutorial systematically removes those assumptions.

---

## Part 1 — Build Time vs Runtime (Docker Reality Check)

### The Symptom

During a Docker image build, Django fails with:

```text
ImproperlyConfigured: Set the DJANGO_SECRET_KEY environment variable
```

But you *did* set it in `docker-compose.yaml`.

So what gives?

### The Root Cause

Docker has **two distinct phases**:

1. **Build time** (`docker build`, `podman build`)
2. **Runtime** (`docker-compose up`, `docker run`)

`docker-compose environment:` applies **only at runtime**.
During the image build, those variables do not exist.

If you run Django commands like `collectstatic` during the build, Django expects configuration that is not yet available.

### The Fix (Explicit Is Better)

We stop pretending the build environment knows runtime secrets.

**Instead of this (build time):**

```dockerfile
RUN python manage.py collectstatic --noinput
```

**We do this (runtime):**

```bash
docker-compose exec web python manage.py collectstatic --noinput
```

This keeps the image build:

* deterministic
* secret-free
* reproducible

And it keeps runtime behavior explicit.

---

## Part 2 — Permissions, Bind Mounts, and SELinux

### The Symptom

At runtime, Python fails to open files that clearly exist:

```text
python: can't open file '/app/manage.py': [Errno 13] Permission denied
```

File permissions look correct. The user ID matches.
Still broken.

### The Hidden Actor: SELinux

On SELinux-enabled systems (common with Podman and many Linux distros), bind mounts require explicit labeling.

Without it, the container can’t access the files — regardless of UNIX permissions.

### The Fix

Add a label to the bind mount:

```yaml
volumes:
  - .:/app:Z
```

Use:

* `:Z` → exclusive access
* `:z` → shared across containers

This is not a Docker bug.
It’s a security feature doing its job.

**Note for this repository:** the current `docker-compose.yaml` does not bind-mount `/app` at all (image-based workflow). This SELinux fix only matters if you choose to reintroduce bind mounts for local development.

---

## Part 3 — Static Files and Ownership

### The Symptom

`collectstatic` fails:

```text
PermissionError: [Errno 13] Permission denied: '/app/staticfiles/...'
```

### Why This Happens

With bind mounts:

* the container inherits host ownership
* your container user (`appuser`) cannot write files owned by `root` on the host

### Two Valid Strategies

#### Option A — Fix Host Permissions (Development)

```bash
sudo chown -R 1000:1000 staticfiles
chmod -R u+rwX,g+rwX staticfiles
```

#### Option B — Image-Based Workflow (Production-like)

* Don’t bind-mount `/app`
* Let the image own its filesystem
* Rebuild when code changes

In this project, the image-based approach is the default. The Dockerfile creates `/app/staticfiles` and assigns it to `appuser`, so `collectstatic` can run without host ownership conflicts.

This tutorial supports **both**, but prefers **image-based** behavior for realism.

---

## Part 3.5 — One Image, Many Services

Docker Compose will rebuild the same image for each service if every service has its own `build:` stanza.

The current setup avoids that by building once and reusing the tag:

```yaml
services:
  web:
    build: .
    image: django-mega-tutorial:local

  celery_worker:
    image: django-mega-tutorial:local

  flower:
    image: django-mega-tutorial:local
```

That keeps builds predictable and avoids three identical image builds.

---

## Part 4 — TLS Without Lying to Yourself

TLS is where many projects silently break.

### The Common Mistake

Tying HTTPS security settings to `DEBUG=False`.

That assumes:

* TLS always exists in production
* reverse proxies don’t exist
* local testing must suffer

All false.

### The Correct Mental Model

TLS is **optional**.
HTTPS assumptions are **not**.

We detect TLS **by intent**, not environment:

```python
HAS_TLS = bool(SERVER_TLS_CERT and SERVER_TLS_KEY)
```

### Behavior Matrix

| Condition          | Result                           |
| ------------------ | -------------------------------- |
| Cert + Key present | Enable HTTPS defaults            |
| Neither present    | Plain HTTP, no redirects         |
| Only one present   | Error in production, warn in dev |

### Why This Works

* Local dev stays frictionless
* Reverse proxy intent is explicit
* Direct TLS is safe by default
* Misconfiguration fails loudly

### Reverse Proxy Case

When TLS terminates upstream (Nginx, Caddy, ELB):

```dotenv
SERVER_TLS_CERT=
SERVER_TLS_KEY=
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
TRUST_PROXY_HEADERS=True
```

Nothing is assumed. Everything is explicit.

### Reverse Proxy Note

`TRUST_PROXY_HEADERS=True` in this project only affects IP extraction for link redirects (it controls whether `X-Forwarded-For` is trusted in the redirect view). It does **not** configure Django's `SECURE_PROXY_SSL_HEADER` or other proxy-related security behavior. If you need Django to trust proxy scheme headers, add `SECURE_PROXY_SSL_HEADER` in settings for your deployment.

---

## Part 5 — Why Asyncronous Tasks Exist

Up to now, everything has happened inside the request.

That works until it doesn't.

### The Problem

Synchronous operations:

* block response time
* amplify database contention
* fail user requests on transient errors

Classic offenders:

* email
* analytics
* webhooks

### The Solution

Move work **off the request path**.

Enter Celery.

---

## Part 6 — Introducing Celery (Once)

### Architecture (Minimal)

* **Broker**: Redis
* **Worker**: Celery
* **Result backend**: Redis
* **Monitor**: Flower (optional)

Celery is not magic. It is:

* a message queue
* worker processes
* retry logic

**Dev note:** when `DJANGO_DEBUG=True`, the defaults fall back to in-memory broker/result backends unless you override them with `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

### Test-Friendly Configuration

In tests:

```python
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

This means:

* no Redis required
* tasks run synchronously
* failures are visible

You get correctness *and* speed.

---

## Part 7 — Async Email (First Use Case)

We move email sending into background tasks.

### Why

* Email servers are slow
* Network failures should not break user flows
* Retries should be automatic

### Key Design Rules

* Invalid users do **not** raise
* Failures retry with backoff
* Logging is server-side only
* User experience is consistent

This mirrors Django’s own password reset behavior.

---

## Part 8 — Async Click Tracking (Performance Use Case)

Now we apply Celery where it really shines.

### The Problem

Redirect endpoints are hot paths.

Every synchronous write:

* increases latency
* increases lock contention
* caps throughput

### The Tradeoff

We accept **eventual consistency**.

Clicks may appear seconds late.
Redirects return immediately.

This is the right trade.

### Implementation Highlights

* Clicks are queued via Celery
* Broker failure does **not** block redirects
* Click tasks use a dedicated queue
* Tests verify queuing behavior

Users never wait on analytics.

---

## Part 9 — Logging Without Shooting Yourself in the Foot

Multiprocess logging is tricky.

### The Safe Default (This Tutorial)

* Per-worker log files
* PID-based filenames
* Errors only
* `delay=True` to avoid empty files

This is:

* safe
* simple
* appropriate for small to medium deployments

### Production Recommendation

For real scale:

* log to stdout/stderr
* let Docker / systemd / Kubernetes handle rotation
* aggregate centrally

The goal is clarity, not cleverness.

---

## Part 10 — Final Mental Model

By now, the pattern should be clear.

### What We Achieved

* **Configuration is phased**

  * build ≠ runtime
* **Security follows intent**

  * TLS detected, not assumed
* **Background work is isolated**

  * requests stay fast
* **Production is strict on purpose**

  * failures are loud
* **Development stays humane**

  * warnings, not walls

### The Big Takeaway

Most production failures aren’t bugs.

They’re assumptions that went unchallenged.

This tutorial exists to challenge them — once — so you don’t have to debug them at 2 a.m.

---

## Where to Go Next

Good follow-ups to this tutorial:

* Periodic tasks with Celery Beat
* Rate-limiting background workloads
* Structured logging and correlation IDs
* Metrics and alerting
* Deployment-specific hardening

But those are **additions**, not prerequisites.

You now have a system that behaves the way you think it does.

That’s what production-ready really means.
