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
