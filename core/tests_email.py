import logging
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings

from core.email import send_templated_email

logger = logging.getLogger(__name__)


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
