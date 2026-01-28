"""Celery tasks for the core app."""

import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.conf import settings
from django.utils import timezone

from core.email import send_templated_email

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def send_welcome_email(self, user_id: int, login_url: str) -> str:
    """
    Send a welcome email to a newly registered user.

    Args:
        user_id: ID of the user to send welcome email to
        login_url: Absolute URL to the login page

    Returns:
        Status message

    Retries: Up to CELERY_TASK_MAX_RETRIES times with exponential backoff

    Note:
        If user is not found (e.g., deleted between registration and task
        execution), we log a warning but don't raise an exception. This
        prevents task failures for edge cases.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(f"send_welcome_email: User with id {user_id} not found")
        return f"User {user_id} not found"

    try:
        send_templated_email(
            subject="Welcome to Django SaaS",
            template_base="emails/welcome_email",
            context={"user": user, "login_url": login_url},
            to=[user.email],
        )
        logger.info(
            "Welcome email sent",
            extra={"user_id": user.id, "email": user.email},
        )
        return f"Welcome email sent to {user.email}"
    except Exception as e:
        logger.error(
            f"Failed to send welcome email to user {user_id}",
            exc_info=True,
            extra={"user_id": user_id},
        )
        # Re-raise to trigger retry mechanism
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def send_password_reset_email(self, user_id: int, reset_link: str) -> str:
    """
    Send a password reset email to a user.

    Args:
        user_id: ID of the user to send password reset email to
        reset_link: Absolute URL to the password reset confirmation page

    Returns:
        Status message

    Retries: Up to CELERY_TASK_MAX_RETRIES times with exponential backoff

    Security Note:
        If user is not found, we log a warning but do NOT raise an exception.
        This prevents user enumeration attacks - attackers shouldn't be able
        to determine which emails are registered by observing different error
        responses. This follows Django's built-in PasswordResetForm behavior.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(f"send_password_reset_email: User with id {user_id} not found")
        return f"User {user_id} not found"

    try:
        send_templated_email(
            subject="Password Reset Request",
            template_base="emails/password_reset_email",
            context={"user": user, "reset_link": reset_link},
            to=[user.email],
        )
        logger.info(
            "Password reset email sent",
            extra={"user_id": user.id, "email": user.email},
        )
        return f"Password reset email sent to {user.email}"
    except Exception as e:
        logger.error(
            f"Failed to send password reset email to user {user_id}",
            exc_info=True,
            extra={"user_id": user_id},
        )
        # Re-raise to trigger retry mechanism
        raise


@shared_task()
def cleanup_expired_tokens() -> str:
    """
    Clean up expired session tokens from the database.

    This is a periodic task that should be scheduled with Celery Beat
    to run daily.

    Returns:
        Status message with count of deleted sessions
    """
    now = timezone.now()

    # Count and delete expired sessions
    expired_sessions = Session.objects.filter(expire_date__lt=now)
    count = expired_sessions.count()
    deleted_count, _ = expired_sessions.delete()

    logger.info(
        f"Cleanup task completed: {deleted_count} expired sessions deleted",
        extra={"deleted_count": deleted_count, "timestamp": now.isoformat()},
    )

    return f"Cleanup completed: {deleted_count} expired sessions deleted"
