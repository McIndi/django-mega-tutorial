# Production-Ready Docker: Permissions, TLS, and "Frozen" Builds (Tutorial 007.2)

**Published February 9, 2026**
*By Cliff*

---

## TL;DR

We hit several real-world Docker issues while trying to keep a production-ready workflow:

- Runtime env vars are not available at build time.
- SELinux can block bind mounts even when permissions look correct.
- `collectstatic` fails when the host owns `staticfiles` and the container user cannot write it.
- Multiple services can rebuild the same image unless you explicitly share a tag.

We resolved each issue and ended up with a stable, predictable build workflow that behaves like production, without sacrificing debugging flexibility.

---

## 1) Build-Time vs Runtime Configuration

**Symptom**

During the image build, Django crashed with:

```
ImproperlyConfigured: Set the DJANGO_SECRET_KEY environment variable
```

**Root cause**

`docker-compose environment:` only applies when a container runs. A `docker build` or `podman build` has no access to those runtime values.

**Fix**

We stopped running `collectstatic` during image build and moved it to a runtime step after containers start. That kept the build stage clean and made configuration more explicit.

---

## 2) Permission Denied on /app/manage.py

**Symptom**

```
python: can't open file '/app/manage.py': [Errno 13] Permission denied
```

**Root cause**

SELinux was denying access to bind-mounted files. Even with correct UNIX permissions, SELinux blocks access when the container and mount labels do not match.

**Fix**

We updated bind mounts with SELinux labels:

```yaml
volumes:
  - .:/app:Z
```

Then switched to `:z` when multiple containers needed to read the same mount.

---

## 3) collectstatic Permission Errors

**Symptom**

```
PermissionError: [Errno 13] Permission denied: '/app/staticfiles/admin/css/autocomplete.css'
```

**Root cause**

`/app/staticfiles` was owned by `root:root` on the host, while the container ran as `appuser` (uid 1000). With a bind mount, the container inherits host ownership and cannot write to the directory.

**Fix options**

- Fix host permissions:
  ```bash
  sudo chown -R 1000:1000 staticfiles
  chmod -R u+rwX,g+rwX staticfiles
  ```

- Or avoid host ownership entirely by moving to an immutable image workflow (next section), where `staticfiles/` is created inside the image and not bind-mounted.

---

## 4) Three Services, Three Builds

**Symptom**

Running `podman-compose up --build -d` built the same image three times.

**Root cause**

Each service had its own `build: .` directive, so Compose treated them as independent builds.

**Fix**

We tagged a shared image once and reused it in other services:

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

Now only `web` builds; the other services reuse the same image.

---

## 5) "Immutable" Images (and a Better Term)

We wanted a production-like workflow where containers run a specific, built version of the code, not whatever happens to be on the developer machine. This is not fully immutable (you can still `exec` into a container), but a better term is:

- **"Image-based"** workflow
- **"Artifact-based"** workflow
- **"Build-and-run"** workflow

The key idea is simple: the container runs what the image contains, and code changes require a rebuild.

**What we changed**

- Removed bind mounts for `/app`.
- Ensured `staticfiles/` exists inside the image and is owned by `appuser`.
- Added `staticfiles` to `.dockerignore` to avoid build context noise.
- Documented the rebuild requirement in the README.

---

## Final Workflow Summary

### Build and Run (image-based)

```bash
# Build once
podman-compose build

# Start services
podman-compose up -d

# Collect static assets (one-time or per release)
podman-compose exec web python manage.py collectstatic --noinput

# Run migrations
podman-compose exec web python manage.py migrate
```

### Debug Mode (optional)

You can still set:

```dotenv
DJANGO_DEBUG=True
```

But the runtime still uses the built image, so debugging is deliberate and reproducible.

---

## Troubleshooting Checklist

**Permission denied on /app/*:**
- Check SELinux labels (`:Z` or `:z` on bind mounts).
- Verify container UID matches host file ownership.
- Confirm you are not bind-mounting over image directories by accident.

**collectstatic fails:**
- Ensure `/app/staticfiles` is writable by `appuser`.
- Prefer image-based workflow to avoid host ownership conflicts.

**Multiple rebuilds:**
- Use a single `build:` and share the image tag.

**Unexpected runtime config:**
- Remember: `environment:` only applies at runtime.

**Missing console email output in worker logs:**
- Celery may be redirecting stdout. Set `CELERY_WORKER_REDIRECT_STDOUTS=False` to keep console backend output visible.
- If you want a single-run sanity check, run the task eagerly with `CELERY_ALWAYS_EAGER=True` and invoke `python manage.py test_email`.

---

## Takeaway

These issues were not random; they were all mismatches between build-time and runtime assumptions. Once those were made explicit, the system became predictable:

- Build images once.
- Run containers as `appuser`.
- Collect static assets on demand.
- Keep TLS and security settings flexible but safe.

That is the balance we want in a production-ready tutorial: clarity, repeatability, and minimal surprises.
