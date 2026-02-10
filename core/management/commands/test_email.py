import logging
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.tasks import send_welcome_email

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
            User = get_user_model()
            user = User.objects.filter(email=recipient).first()
            if not user:
                username = f"testuser_{uuid4().hex[:8]}"
                user = User.objects.create_user(username=username, email=recipient)

            task = send_welcome_email.delay(
                user_id=user.id,
                login_url="http://localhost:8000/accounts/login/",
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Test email task queued for {recipient} (task_id={task.id})"
                )
            )

            if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                self.stdout.write(self.style.SUCCESS("Tasks run eagerly; waiting for result..."))
                result = task.get(timeout=30)
                self.stdout.write(self.style.SUCCESS(f"Task result: {result}"))
            else:
                self.stdout.write(
                    "Check the celery worker logs for the email output."
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to enqueue test email: {str(e)}")
            )
            logger.error(f"Test email task failed: {e}", exc_info=True)
            raise
