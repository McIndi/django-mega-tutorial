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
