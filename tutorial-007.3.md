# Async Click Tracking with Celery (Tutorial 007.3)

**Published February 10, 2026**
*By Cliff*

---

## TL;DR

We moved click tracking off the request-response path:

- Clicks are recorded via a **Celery task** instead of an inline DB write
- Redirects return faster under load (no synchronous write contention)
- Click stats become **eventually consistent** (seconds behind during peaks)
- New tests verify task behavior and that the redirect queues work

**Estimated time**: **30-45 minutes**
**Prerequisites**: Completed Tutorials 001-007.2

---

## Why This Change Matters

The redirect endpoint is the hottest path in a link shortener. Every request used to write to the database synchronously:

- High volume = more writes per second
- Writes compete with reads (and other writes)
- Response time becomes tied to DB contention

We can trade a small amount of freshness for better latency: enqueue the click write, return immediately, and let a worker handle it.

---

## Part 1: Add a Click Tracking Task

Create a dedicated task in the `links` app:

```python
# links/tasks.py
from celery import shared_task
from django.conf import settings

from .models import Click, Link


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def record_link_click(self, link_id, referrer, user_agent, ip_address):
    link = Link.objects.filter(id=link_id).first()
    if not link:
        return f"Link {link_id} not found"

    Click.objects.create(
        link=link,
        referrer=referrer,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return f"Click recorded for link {link_id}"
```

This follows the same retry strategy as our email tasks.

---

## Part 2: Queue the Task in the Redirect View

Instead of writing the click directly, we queue the task and return the redirect immediately:

```python
# links/views.py
from .tasks import record_link_click

# ...

referrer = request.META.get("HTTP_REFERER", "")
user_agent = request.META.get("HTTP_USER_AGENT", "")
ip_address = self._get_client_ip(request)

try:
    record_link_click.delay(
        link_id=link.id,
        referrer=referrer,
        user_agent=user_agent,
        ip_address=ip_address,
    )
except Exception:
    # Broker outages should never block redirects.
    pass

return redirect(link.target_url)
```

We also wrap task queuing in a `try/except` so a broker outage does not block redirects. Users should never see a 500 due to analytics.

---

## Part 3: Route Click Tasks to Their Own Queue

We keep click writes isolated from email tasks by routing to a dedicated queue:

```python
# config/settings.py
CELERY_TASK_ROUTES = {
    "core.tasks.send_welcome_email": {"queue": "email"},
    "core.tasks.send_password_reset_email": {"queue": "email"},
    "core.tasks.cleanup_expired_tokens": {"queue": "celery"},
    "links.tasks.record_link_click": {"queue": "clicks"},
}

CELERY_QUEUES = {
    "email": {"exchange": "email", "routing_key": "email"},
    "clicks": {"exchange": "clicks", "routing_key": "clicks"},
    "celery": {"exchange": "celery", "routing_key": "celery"},
}
```

Start the worker with both queues:

```bash
celery -A config worker -Q email,clicks,celery -l info --concurrency=4
```

---

## Part 4: Tests for Async Clicks

We added tests that:

- Verify the task creates a click
- Ensure missing links do not raise
- Confirm the redirect queues the task

```python
# links/tests.py
from unittest.mock import patch

class ClickTaskTests(TestCase):
    def test_record_link_click_task_creates_click(self):
        result = record_link_click.delay(
            link_id=self.link.id,
            referrer="https://referrer.test",
            user_agent="TestBrowser/1.0",
            ip_address="203.0.113.5",
        )
        self.assertTrue(result.successful())

    def test_record_link_click_task_handles_missing_link(self):
        result = record_link_click.delay(
            link_id=99999,
            referrer="",
            user_agent="",
            ip_address=None,
        )
        self.assertTrue(result.successful())


class LinkPublicRedirectTests(TestCase):
    @patch("links.views.record_link_click.delay")
    def test_redirect_queues_click_task(self, mock_delay):
        response = self.client.get(
            reverse("link_redirect", args=[self.alice.username, self.link.slug]),
            HTTP_REFERER="https://social.example.com",
            HTTP_USER_AGENT="TestBrowser/1.0",
            REMOTE_ADDR="203.0.113.9",
        )
        self.assertEqual(response.status_code, 302)
        mock_delay.assert_called_once()
```

Run the tests:

```bash
python manage.py test links.tests.ClickTaskTests links.tests.LinkPublicRedirectTests
```

---

## Operational Notes

- **Eventual consistency**: dashboards and analytics can lag by a few seconds.
- **Queue isolation**: if click volume spikes, email tasks are not slowed down.
- **Broker outages**: if Redis is down, redirects still work, but clicks are skipped.
- **Scaling**: you can add a dedicated `clicks` worker pool later for high-volume traffic.

---

## Takeaway

Click tracking belongs in the background. By enqueueing writes with Celery, we keep the redirect path fast, reduce DB contention, and preserve user experience under load. The analytics are still reliable, just slightly delayed, which is the right trade for a high-traffic link shortener.
