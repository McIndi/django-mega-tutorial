import logging

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.http import HttpResponseNotAllowed
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from core.email import send_templated_email
from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
)
from .models import CustomUser

logger = logging.getLogger(__name__)


def login_view(request):
    if request.method == "POST":
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info(
                "User logged in",
                extra={"user_id": user.id},
            )
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("profile")
        else:
            logger.warning(
                "Failed login attempt",
                extra={"errors": form.errors.as_data()},
            )
    else:
        form = CustomAuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    if request.method == "POST":
        username = request.user.username
        user_id = request.user.id
        logout(request)
        logger.info(
            "User logged out",
            extra={"user_id": user_id},
        )
        messages.info(request, "You have been logged out.")
        return redirect("core:index")
    else:
        return HttpResponseNotAllowed(["POST"])


@login_required
def profile_view(request):
    logger.debug(
        "Profile accessed",
        extra={"user_id": request.user.id},
    )
    return render(request, "accounts/profile.html", {"user": request.user})


class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = "accounts/password_reset.html"
    success_url = reverse_lazy("password_reset_done")
    email_template_name = "accounts/password_reset_email.html"


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = CustomSetPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


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
        # Use absolute URL in emails and avoid breaking registration on send failure
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

    def form_invalid(self, form):
        logger.warning(
            f"Registration form invalid: {form.errors.as_json()}",
            extra={"errors": form.errors.as_data()},
        )
        return super().form_invalid(form)
