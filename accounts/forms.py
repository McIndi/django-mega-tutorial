import logging

from django import forms
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.tasks import send_password_reset_email

logger = logging.getLogger(__name__)

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Required. Enter a valid email address.",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your username"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Confirm your password"}
        )
        self.fields["password1"].help_text = (
            "Your password must contain at least 8 characters."
        )
        self.fields["password2"].help_text = "Enter the same password as above."

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            logger.debug(
                "User created via form",
                extra={"user_id": user.id},
            )
        return user


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your email"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your password"}
        )


class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter your email"}
        )

    def save(
        self,
        domain_override=None,
        subject_template_name=None,
        email_template_name=None,
        use_https=False,
        token_generator=default_token_generator,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        """Queue password reset emails via Celery instead of sending inline."""
        email = self.cleaned_data["email"]
        protocol = "https" if use_https else "http"

        for user in self.get_users(email):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            path = reverse(
                "password_reset_confirm",
                kwargs={"uidb64": uid, "token": token},
            )

            if request is not None:
                reset_link = request.build_absolute_uri(path)
            else:
                domain = domain_override
                if not domain:
                    domain = "localhost"
                reset_link = f"{protocol}://{domain}{path}"

            try:
                send_password_reset_email.delay(
                    user_id=user.id,
                    reset_link=reset_link,
                )
                logger.info(
                    "Password reset email task queued",
                    extra={"user_id": user.id},
                )
            except Exception:
                logger.error(
                    "Failed to queue password reset email",
                    exc_info=True,
                    extra={"user_id": user.id},
                )


class CustomSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Enter new password"}
        )
        self.fields["new_password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Confirm new password"}
        )
