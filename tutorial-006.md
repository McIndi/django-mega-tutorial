# Transactional Emails and SMTP Configuration (Tutorial 006)

**Published January 13, 2026**
*By Cliff*

---

## TL;DR

This tutorial adds production-ready email capabilities to your Django SaaS:

- **SMTP configuration**: Environment-based email backend setup supporting Gmail, Mailchimp Transactional, and other providers
- **Welcome emails**: Automatically send branded HTML/text emails when users register
- **Email templates**: Reusable template system for transactional emails
- **Admin notifications**: Configure error reporting via email when things go wrong
- **Test command**: Verify email configuration with a simple management command

Following TDD principles, we'll write tests first, then implement each feature. By the end, your application will send professional transactional emails and you'll understand how to choose and configure email providers.

**Estimated time**: **45–60 minutes**
**Prerequisites**: Completed Tutorials 001–005 (project runs, all tests green)

---

## Introduction: Why Transactional Emails Matter

Tutorials 001–005 built a functional Django SaaS with authentication, link shortening, testing, containerization, and production infrastructure. However, the application currently uses Django's `locmem` backend for password resets, which means emails exist only in memory during development and are never actually sent.

For a real SaaS application, you need:

1. **Welcome emails**: Greet new users and guide their first steps
2. **Password resets**: Send secure reset links via email (already built, needs real delivery)
3. **Admin notifications**: Alert you when errors occur in production
4. **Future capabilities**: Payment confirmations, activity digests, notifications

This tutorial implements a flexible email system that works in development and production.

---

## Part 1: Understanding Email Backend Options

### Django Email Backends

Django supports multiple email backends:

| Backend | Use Case | Configuration Complexity |
|---------|----------|-------------------------|
| **console** | Development (prints to terminal) | None |
| **locmem** | Testing (stores in memory) | None |
| **smtp** | Production (real email) | Medium |
| **filebased** | Debugging (saves to files) | Low |

For production, you'll use the **SMTP backend** with a provider.

---

### Email Provider Comparison

#### Option 1: Gmail SMTP

**Pros:**
- Free for low-volume sending (<100/day)
- Familiar setup for solo founders
- No additional service signup required

**Cons:**
- Strict rate limits (100 emails/day per account)
- Requires app-specific password (not regular password)
- May flag automated sending as suspicious
- Not designed for transactional email

**Best for:** Personal projects, early prototypes, low-volume applications

**Configuration:**
```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=your-email@gmail.com
DJANGO_EMAIL_HOST_PASSWORD=your-app-password  # Not your regular password!
DJANGO_EMAIL_USE_TLS=True
```

**Setup steps:**
1. Enable 2-factor authentication on your Google account
2. Generate an "App Password" at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Use the 16-character app password in `DJANGO_EMAIL_HOST_PASSWORD`

---

#### Option 2: Mailchimp Transactional (Mandrill)

**Pros:**
- Professional transactional email service
- 500 free emails/month (then $0.20/1000)
- Excellent deliverability
- Analytics dashboard (opens, clicks, bounces)
- Templates and API for advanced features

**Cons:**
- Requires separate Mailchimp account
- Mandrill has been folded into Mailchimp (branding confusion)
- Overkill for very small projects

**Best for:** SaaS products expecting moderate to high email volume

**Configuration:**
```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.mandrillapp.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=your-mailchimp-username
DJANGO_EMAIL_HOST_PASSWORD=your-mandrill-api-key
DJANGO_EMAIL_USE_TLS=True
```

**Setup steps:**
1. Sign up for Mailchimp
2. Enable Transactional Email in your account settings
3. Generate an API key in the Transactional section
4. Use API key as `DJANGO_EMAIL_HOST_PASSWORD`

---

#### Option 3: SendGrid, Amazon SES, Postmark

Other popular options:

- **SendGrid**: 100 emails/day free, easy setup, good docs
- **Amazon SES**: $0.10/1000 emails, requires AWS account, excellent for high volume
- **Postmark**: Dedicated to transactional email, great deliverability, $15/month for 10k emails

**Decision criteria:**
- **Volume**: How many emails per day?
- **Budget**: Free tier sufficient or need paid?
- **Deliverability**: How critical is inbox placement?
- **Analytics**: Do you need open/click tracking?
- **Integration**: Existing relationship with provider?

**Recommendation for this tutorial:**
- **Development**: Use `console` backend (see emails in terminal)
- **Production (< 100 emails/day)**: Gmail SMTP
- **Production (> 100 emails/day)**: Mailchimp Transactional or SendGrid

---

## Part 2: Email Configuration (TDD)

### Step 1: Write Email Configuration Tests (Red)

Create `core/tests_email.py` and add configuration tests:

```python
import logging
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings

from core.email import send_templated_email

logger = logging.getLogger(__name__)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailConfigurationTests(TestCase):
    """Tests for email configuration settings."""

    def test_default_from_email_is_configured(self):
        """Test that DEFAULT_FROM_EMAIL is configured."""
        from django.conf import settings

        self.assertTrue(hasattr(settings, "DEFAULT_FROM_EMAIL"))
        self.assertIsInstance(settings.DEFAULT_FROM_EMAIL, str)
        self.assertGreater(len(settings.DEFAULT_FROM_EMAIL), 0)

    def test_server_email_is_configured(self):
        """Test that SERVER_EMAIL is configured."""
        from django.conf import settings

        self.assertTrue(hasattr(settings, "SERVER_EMAIL"))
        self.assertIsInstance(settings.SERVER_EMAIL, str)

    def test_email_backend_is_configured(self):
        """Test that EMAIL_BACKEND is configured."""
        from django.conf import settings

        self.assertTrue(hasattr(settings, "EMAIL_BACKEND"))
        self.assertIn("EmailBackend", settings.EMAIL_BACKEND)

    def test_email_host_is_configured(self):
        """Test that EMAIL_HOST is configured."""
        from django.conf import settings

        self.assertTrue(hasattr(settings, "EMAIL_HOST"))
        self.assertIsInstance(settings.EMAIL_HOST, str)

    def test_email_port_is_configured(self):
        """Test that EMAIL_PORT is configured."""
        from django.conf import settings

        self.assertTrue(hasattr(settings, "EMAIL_PORT"))
        self.assertIsInstance(settings.EMAIL_PORT, int)

    def test_email_timeout_is_configured(self):
        """Test that EMAIL_TIMEOUT is configured."""
        from django.conf import settings

        self.assertTrue(hasattr(settings, "EMAIL_TIMEOUT"))
        self.assertIsInstance(settings.EMAIL_TIMEOUT, int)
        self.assertGreater(settings.EMAIL_TIMEOUT, 0)
```

Run tests (Red phase):

```bash
python manage.py test core.tests_email.EmailConfigurationTests
```

---

### Step 2: Configure Email Settings (Green)

Edit `config/settings.py` to add comprehensive email configuration:

```python
# Email configuration
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=1025 if DEBUG else 587)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_SSL = env.bool("DJANGO_EMAIL_USE_SSL", default=False)
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=not EMAIL_USE_SSL)
EMAIL_SUBJECT_PREFIX = env("DJANGO_EMAIL_SUBJECT_PREFIX", default="")

EMAIL_TIMEOUT = env.int("DJANGO_EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="noreply@example.com")
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_REPLY_TO = env.list("DJANGO_EMAIL_REPLY_TO", default=[])

# Admin email notifications for errors (500s)
ADMINS = [
    (name.strip(), email.strip())
    for name, email in [
        tuple(admin.split(":"))
        for admin in env.list("DJANGO_ADMINS", default=[])
    ]
]
MANAGERS = ADMINS
```

**Configuration explained:**

- **EMAIL_BACKEND**: Console in development, SMTP in production
- **EMAIL_HOST**: SMTP server hostname
- **EMAIL_PORT**: 587 for TLS, 465 for SSL, 25 for unencrypted (avoid)
- **EMAIL_HOST_USER**: SMTP username (often same as email address)
- **EMAIL_HOST_PASSWORD**: SMTP password or API key
- **EMAIL_USE_TLS**: Enable TLS (recommended, port 587)
- **EMAIL_USE_SSL**: Enable SSL (port 465, less common)
- **EMAIL_TIMEOUT**: Seconds before connection times out
- **DEFAULT_FROM_EMAIL**: Address used for outgoing emails
- **SERVER_EMAIL**: Address for error notifications
- **EMAIL_REPLY_TO**: List of addresses for Reply-To header
- **ADMINS**: List of admin emails for error notifications

---

### Step 3: Update Environment Configuration

Edit `.env.example` to document email settings:

```env
# Email configuration
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DJANGO_DEFAULT_FROM_EMAIL="Your SaaS <noreply@example.com>"
DJANGO_SERVER_EMAIL=alerts@example.com
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=your-email@example.com
DJANGO_EMAIL_HOST_PASSWORD=your-app-password
DJANGO_EMAIL_USE_TLS=True
DJANGO_EMAIL_USE_SSL=False
DJANGO_EMAIL_TIMEOUT=10
DJANGO_EMAIL_REPLY_TO=support@example.com
DJANGO_EMAIL_SUBJECT_PREFIX="[Django SaaS] "

# Admin error notifications (emails sent on 500 errors when DEBUG=False)
# Format: "Name:email@example.com,Another Name:another@example.com"
DJANGO_ADMINS="Admin:admin@example.com"

# Gmail quickstart (requires an app password; username/password login will fail)
# DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# DJANGO_EMAIL_HOST=smtp.gmail.com
# DJANGO_EMAIL_PORT=587
# DJANGO_EMAIL_HOST_USER=your-email@gmail.com
# DJANGO_EMAIL_HOST_PASSWORD=your-app-password
# DJANGO_EMAIL_USE_TLS=True

# Mailchimp Transactional (Mandrill) via SMTP
# DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# DJANGO_EMAIL_HOST=smtp.mandrillapp.com
# DJANGO_EMAIL_PORT=587
# DJANGO_EMAIL_HOST_USER=your-mailchimp-username
# DJANGO_EMAIL_HOST_PASSWORD=your-mailchimp-api-key
# DJANGO_EMAIL_USE_TLS=True
```

Verify tests pass:

```bash
python manage.py test core.tests_email.EmailConfigurationTests
```

---

## Part 3: Email Utility and Templates (TDD)

### Step 1: Write Email Utility Tests (Red)

Add utility tests to `core/tests_email.py`:

```python
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="test@example.com",
    EMAIL_REPLY_TO=["support@example.com"],
)
class EmailUtilsTests(TestCase):
    """Tests for the email utility functions."""

    def test_send_templated_email_text_only(self):
        """Test sending email renders both text and HTML templates."""
        send_templated_email(
            subject="Test Subject",
            template_base="emails/welcome_email",
            context={"user": type("User", (), {"username": "testuser"})()},
            to=["recipient@example.com"],
        )

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        self.assertEqual(email.subject, "Test Subject")
        self.assertEqual(email.from_email, "test@example.com")
        self.assertEqual(email.to, ["recipient@example.com"])
        self.assertEqual(email.reply_to, ["support@example.com"])

        # Verify body contains text content
        self.assertIn("testuser", email.body)
        self.assertIn("Welcome to Django SaaS", email.body)

        # Verify HTML alternative is attached
        self.assertEqual(len(email.alternatives), 1)
        html_content, mime_type = email.alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn("testuser", html_content)
        self.assertIn("<h2>", html_content)

    def test_send_templated_email_multiple_recipients(self):
        """Test sending email to multiple recipients."""
        send_templated_email(
            subject="Test Multiple",
            template_base="emails/welcome_email",
            context={"user": type("User", (), {"username": "multi"})()},
            to=["one@example.com", "two@example.com", "three@example.com"],
        )

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(len(email.to), 3)
        self.assertIn("one@example.com", email.to)
        self.assertIn("two@example.com", email.to)
        self.assertIn("three@example.com", email.to)

    @override_settings(EMAIL_REPLY_TO=[])
    def test_send_templated_email_no_reply_to(self):
        """Test sending email when EMAIL_REPLY_TO is not configured."""
        send_templated_email(
            subject="Test No Reply",
            template_base="emails/welcome_email",
            context={"user": type("User", (), {"username": "noreply"})()},
            to=["test@example.com"],
        )

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.reply_to, [])

    def test_send_templated_email_logs_info(self):
        """Test that email sending logs appropriate information."""
        with self.assertLogs("core.email", level="INFO") as cm:
            send_templated_email(
                subject="Log Test",
                template_base="emails/welcome_email",
                context={"user": type("User", (), {"username": "logger"})()},
                to=["log@example.com"],
            )

        self.assertTrue(any("Email sent" in message for message in cm.output))
```

Run tests (Red phase):

```bash
python manage.py test core.tests_email.EmailUtilsTests
```

---

### Step 2: Create Email Utility (Green)

Create `core/email.py`:

```python
import logging
from typing import Mapping, Sequence

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_templated_email(
    *,
    subject: str,
    template_base: str,
    context: Mapping[str, object],
    to: Sequence[str],
):
    """Render text/HTML email templates and send the message."""
    text_body = render_to_string(f"{template_base}.txt", context)
    html_body = render_to_string(f"{template_base}.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=list(to),
        reply_to=getattr(settings, "EMAIL_REPLY_TO", []),
    )
    message.attach_alternative(html_body, "text/html")

    sent_count = message.send(fail_silently=False)
    logger.info(
        "Email sent",
        extra={"subject": subject, "to": list(to), "sent": sent_count},
    )
    return message
```

**Why this design?**

- **Template-based**: Separates content from code
- **Dual format**: Sends both text and HTML versions (best practice)
- **Flexible**: Context dict allows any data to be passed
- **Logged**: Records email activity for debugging
- **Type-hinted**: Clear function signature

---

### Step 3: Create Email Templates (Green)

Create `templates/emails/welcome_email.txt`:

```text
Hi {{ user.username }},

Welcome to Django SaaS! We're glad you're here.

You can log in at {{ login_url }} and start creating and sharing links.

If you have any questions, just reply to this email and we will help.

Thanks,
The Django SaaS Team
```

Create `templates/emails/welcome_email.html`:

```html
<div style="font-family: Arial, sans-serif; line-height: 1.6;">
  <h2>Welcome to Django SaaS, {{ user.username }}!</h2>
  <p>We're glad you're here.</p>
  <p>
    You can <a href="{{ login_url }}">log in</a> to start creating and sharing links.
  </p>
  <p>If you have any questions, just reply to this email and we will help.</p>
  <p>Thanks,<br />The Django SaaS Team</p>
</div>
```

**Email template best practices:**

- **Plain text required**: Some users prefer text-only email
- **Inline styles**: Email clients strip `<style>` tags
- **Simple HTML**: Complex CSS often breaks in email
- **Mobile-friendly**: Most email is read on phones
- **Clear CTAs**: Obvious links and actions

Verify tests pass:

```bash
python manage.py test core.tests_email.EmailUtilsTests
```

---

## Part 4: Welcome Email on Registration (TDD)

### Step 1: Write Welcome Email Test (Red)

Add test to `accounts/tests.py`:

```python
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="product@example.com",
)
class RegistrationEmailTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_welcome_email_sent_on_registration(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "welcomeuser",
                "email": "welcome@example.com",
                "password1": "securepassword123",
                "password2": "securepassword123",
            },
        )

        self.assertRedirects(response, reverse("login"))
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.subject, "Welcome to Django SaaS")
        self.assertEqual(email.from_email, "product@example.com")
        self.assertIn("welcomeuser", email.body)
        self.assertGreaterEqual(len(email.alternatives), 1)
        self.assertEqual(email.alternatives[0][1], "text/html")
```

Run test (Red phase):

```bash
python manage.py test accounts.tests.RegistrationEmailTests
```

---

### Step 2: Send Welcome Email (Green)

Edit `accounts/views.py` to import and use the email utility:

```python
from django.urls import reverse, reverse_lazy
from core.email import send_templated_email

class RegisterView(CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(
            "New user registered",
            extra={"user_id": self.object.id},
        )
        # Use an absolute URL for emails and avoid breaking registration on failures
        try:
            login_url = self.request.build_absolute_uri(reverse("login"))
            send_templated_email(
                subject="Welcome to Django SaaS",
                template_base="emails/welcome_email",
                context={"user": self.object, "login_url": login_url},
                to=[self.object.email],
            )
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}", exc_info=True)
        messages.success(self.request, "Account created successfully! Please log in.")
        return response
```

Verify test passes:

```bash
python manage.py test accounts.tests.RegistrationEmailTests
```

Verify all accounts tests still pass:

```bash
python manage.py test accounts
```

---

## Part 5: Test Email Command

### Create Management Command

Create `core/management/commands/test_email.py`:

```python
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from core.email import send_templated_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send a test email to verify email configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            type=str,
            help="Email address to send the test email to",
        )

    def handle(self, *args, **options):
        recipient = options["recipient"]

        self.stdout.write(f"Sending test email to {recipient}...")
        self.stdout.write(f"Using backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"SMTP host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")

        try:
            # Create a mock user object for the template
            mock_user = type("User", (), {"username": "Test User"})()

            send_templated_email(
                subject="Test Email from Django SaaS",
                template_base="emails/welcome_email",
                context={
                    "user": mock_user,
                    "login_url": "http://localhost:8000/accounts/login/",
                },
                to=[recipient],
            )

            self.stdout.write(
                self.style.SUCCESS(f"✓ Test email sent successfully to {recipient}")
            )
            self.stdout.write("\nCheck your inbox (and spam folder).")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to send test email: {str(e)}")
            )
            logger.error(f"Test email failed: {e}", exc_info=True)
            raise
```

### Test the Command

```bash
# With console backend (default in development)
python manage.py test_email your-email@example.com
```

You should see the email printed to your terminal.

**To test with real SMTP:**

1. Update your `.env` file with real credentials:

```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=your-email@gmail.com
DJANGO_EMAIL_HOST_PASSWORD=your-app-password
DJANGO_EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL="Django SaaS <noreply@example.com>"
```

2. Run the command again:

```bash
python manage.py test_email your-email@example.com
```

3. Check your inbox (and spam folder)!

---

## Part 6: Verification and Best Practices

### Run Full Test Suite

```bash
python manage.py test
```

You should see 89+ tests passing, including new email tests.

---

### Email Best Practices

#### 1. SPF, DKIM, and DMARC

For production, configure these DNS records to improve deliverability:

- **SPF**: Authorizes servers to send email for your domain
- **DKIM**: Cryptographic signature proving email authenticity
- **DMARC**: Policy for handling failed SPF/DKIM checks

Most email providers (Mailchimp, SendGrid, etc.) provide these records in their setup documentation.

#### 2. From Address

Use a real domain you control:

```python
DEFAULT_FROM_EMAIL = "Django SaaS <noreply@yourdomain.com>"
```

Avoid:
- `@gmail.com` addresses (looks unprofessional)
- `noreply@` if you actually want replies (use `support@` instead)

#### 3. Reply-To Header

Always provide a way for users to respond:

```env
DJANGO_EMAIL_REPLY_TO=support@yourdomain.com
```

#### 4. Error Handling

In production, wrap email sending in try/except to avoid breaking user flows:

```python
try:
    send_templated_email(...)
except Exception as e:
    logger.error(f"Failed to send welcome email: {e}")
    # Don't prevent registration from completing
```

#### 5. Rate Limiting

Be mindful of provider limits:

- Gmail: 100/day
- Mailchimp free: 500/month
- SendGrid free: 100/day

For high volume, upgrade to a paid plan.

---

## Summary: What We Built

| Feature | Purpose | Tests Added |
|---------|---------|-------------|
| **Email configuration** | Environment-based SMTP setup | 6 |
| **Email utility** | Template-based email sending | 4 |
| **Welcome emails** | Greet new registrations | 1 |
| **Test command** | Verify configuration | N/A |

### Key Files Created/Modified

- `config/settings.py` - Email settings and admin configuration
- `core/email.py` - Reusable email utility
- `core/tests_email.py` - Email configuration and utility tests
- `core/management/commands/test_email.py` - Test email command
- `templates/emails/welcome_email.txt` - Plain text template
- `templates/emails/welcome_email.html` - HTML template
- `accounts/views.py` - Welcome email integration
- `accounts/tests.py` - Registration email test
- `.env.example` - Documented email configuration
- `README.md` - Updated with email features

### Production Readiness Achieved

Your Django SaaS now has:

✅ **Flexible email backend** supporting development and production
✅ **SMTP configuration** for Gmail, Mailchimp, SendGrid, and others
✅ **Welcome emails** sent on registration
✅ **HTML and text formats** for maximum compatibility
✅ **Admin notifications** configured for error reporting
✅ **Test command** to verify setup
✅ **89+ tests** all passing

---

## Next Steps

1. **Choose a provider**: Gmail for small projects, Mailchimp/SendGrid for production
2. **Configure DNS**: Set up SPF, DKIM, and DMARC records
3. **Test thoroughly**: Send test emails to multiple providers (Gmail, Outlook, etc.)
4. **Monitor deliverability**: Watch for bounces and spam complaints
5. **Add more templates**: Password reset confirmation, link creation notifications, etc.

Future tutorials will cover:

- **Tutorial 007**: Background tasks with Celery (for bulk email)
- **Tutorial 008**: Subscription billing with Stripe (payment confirmations)
- **Tutorial 009**: Production deployment with Let's Encrypt
- **Tutorial 010**: Monitoring and observability

---

## Troubleshooting

### Email not sending (Gmail)

**Problem**: `SMTPAuthenticationError`

**Solution**: You must use an App Password, not your regular Gmail password:
1. Enable 2-factor authentication on your Google account
2. Visit [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Generate a new app password
4. Use the 16-character password in `DJANGO_EMAIL_HOST_PASSWORD`

---

### Emails going to spam

**Problem**: Welcome emails landing in spam folder

**Solutions**:
1. Configure SPF, DKIM, and DMARC records
2. Use a professional `From` address with your own domain
3. Avoid spam trigger words ("free", "click here", excessive caps)
4. Include an unsubscribe link (required for marketing, good practice for transactional)
5. Send from a warmed-up IP address (established sender reputation)

---

### Timeout errors

**Problem**: `SMTPServerDisconnected` or timeout errors

**Solutions**:
1. Verify `EMAIL_HOST` and `EMAIL_PORT` are correct
2. Check if your hosting provider blocks outbound SMTP (ports 25, 587, 465)
3. Increase `EMAIL_TIMEOUT` setting
4. Try a different email provider

---

## References

- [Django Email Documentation](https://docs.djangoproject.com/en/stable/topics/email/)
- [Gmail SMTP Setup](https://support.google.com/mail/answer/7126229)
- [Mailchimp Transactional](https://mailchimp.com/developer/transactional/docs/)
- [Email HTML Best Practices](https://www.campaignmonitor.com/dev-resources/guides/coding-html-emails/)
- [SPF, DKIM, DMARC Explained](https://www.cloudflare.com/learning/dns/dns-records/)

---

**Published January 13, 2026**
*By Cliff*
