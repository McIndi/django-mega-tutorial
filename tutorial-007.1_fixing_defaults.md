# Fixing Defaults: TLS, Docker, and Safer Production Behavior (Tutorial 007.1)

**Published February 7, 2026**
*By Cliff*

---

## TL;DR

We traced a build-time error into a more complete configuration story:

- Build-time env vars are not the same as runtime env vars.
- SELinux can block bind mounts without proper labels.
- TLS should be optional, but HTTPS-only security settings should be smart defaults when TLS is present.
- Production behavior should be strict, while development should be forgiving.

By the end, we have a flexible configuration that supports both:

1) **TLS handled directly by our custom `serve` / `serve_async` commands**, and
2) **Plain HTTP behind a TLS-terminating reverse proxy**.

---

## The Original Symptom: Build-Time Errors

The first failure came from image builds:

```
ImproperlyConfigured: Set the DJANGO_SECRET_KEY environment variable
```

That happened while running `collectstatic` during the image build. Docker Compose `environment:` only applies **at container runtime**, not during `docker build`. So even though runtime env vars were correct, the build step could not see them.

**Resolution**: move `collectstatic` to runtime (or provide build args). In our case, we dropped the build-time `collectstatic` and ran it after the containers come up. We also updated the `README.md`.

---

## The Next Surprise: Permission Denied on /app/manage.py

We then hit:

```
python: can't open file '/app/manage.py': [Errno 13] Permission denied
```

That was a classic SELinux issue caused by bind-mounting the source directory without a label. On SELinux-enabled hosts (common with Podman), the container cannot read the mount unless it has an SELinux label.

**Resolution**: use `:Z` (or `:z`) on bind mounts:

```yaml
volumes:
  - .:/app:Z
```

---

## The Real Goal: TLS That Is Optional but Safe

Our `serve` and `serve_async` management commands already support TLS when both a cert and key are provided. The problem was how settings behaved when those files were missing.

Originally, the production security settings assumed HTTPS unconditionally when `DEBUG=False`. That would force redirects and secure cookies even if TLS was not enabled, breaking plain HTTP and reverse-proxy deployments.

### The Goal

We wanted configuration that:

- **Automatically enables HTTPS security defaults** if TLS cert/key are present.
- **Allows overrides** via env vars if those defaults are too strict for a deployment.
- **Keeps HTTP working** when TLS is not configured.
- **Is strict in production**, but loud and forgiving in development.

---

## The Final Settings Strategy

We now detect TLS based on whether both `SERVER_TLS_CERT` and `SERVER_TLS_KEY` are provided, then set secure defaults accordingly. All security flags remain overridable via env vars.

### Key behavior

- If both cert and key are provided:
  - HTTPS security settings default to `True` (or HSTS 1 year).
- If neither is provided:
  - HTTPS settings default to safe HTTP values (no redirects, no HSTS).
- If only one is provided:
  - In development: warn and continue without TLS.
  - In production: raise an error to avoid accidental insecure deployment.

This matches how the management commands behave: TLS is enabled only when both paths exist.

---

## Example: TLS Directly in `serve` / `serve_async`

**.env**
```dotenv
SERVER_TLS_CERT=/app/certs/dev.crt
SERVER_TLS_KEY=/app/certs/dev.key
```

**docker-compose.yaml**
```yaml
services:
  web:
    command: python manage.py serve --host 0.0.0.0
    volumes:
      - .:/app:Z
      - ./deploy/certs:/app/certs:ro,Z
```

Result:
- TLS enabled in Cheroot or Daphne.
- HTTPS security defaults enabled automatically.
- You can still override any of these with env vars if needed.

---

## Example: HTTP Behind a TLS-Terminating Reverse Proxy

If you are using a reverse proxy (Caddy, Nginx, Traefik, ELB, etc.), the Django app should stay on plain HTTP. In that case:

```dotenv
# Leave both empty
SERVER_TLS_CERT=
SERVER_TLS_KEY=

# If you still want HTTPS security settings, set them explicitly:
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

You should also set:

```dotenv
TRUST_PROXY_HEADERS=True
```

That tells Django to honor `X-Forwarded-*` headers from your proxy. (This project already guards that behind a flag, so you only opt in when you trust the proxy.)

---

## Why This Balances Flexibility and Safety

- **Developer velocity**: local TLS is optional. You can run plain HTTP without fighting redirects.
- **Production safety**: if you intend to use in-process TLS, you must provide both cert and key.
- **Explicit overrides**: you can disable or enable HTTPS settings regardless of TLS state.
- **Works with both deployment styles**: direct TLS or reverse-proxy TLS.

This gives us predictable behavior without forcing a single deployment pattern.

---

## Checklist

**Local dev (no TLS):**
- `SERVER_TLS_CERT=`
- `SERVER_TLS_KEY=`
- `DJANGO_DEBUG=True`

**Local dev (TLS):**
- `SERVER_TLS_CERT=/app/certs/dev.crt`
- `SERVER_TLS_KEY=/app/certs/dev.key`

**Production with direct TLS (serve/serve_async):**
- `SERVER_TLS_CERT=/path/to/fullchain.pem`
- `SERVER_TLS_KEY=/path/to/privkey.pem`
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS=your.domain`

**Production behind TLS proxy:**
- `SERVER_TLS_CERT=`
- `SERVER_TLS_KEY=`
- `TRUST_PROXY_HEADERS=True`
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_SECONDS=31536000`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
- `SECURE_HSTS_PRELOAD=True`

---

## Takeaway

The initial error was about a missing secret at build time, but the real fix was clarity around configuration phases and TLS expectations. The updated defaults now support both the tutorial server and real-world reverse-proxy setups, without surprising redirects or security gaps. That is the right balance: sensible defaults, strict when it matters, and always overridable when the deployment requires it.
