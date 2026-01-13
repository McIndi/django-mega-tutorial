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
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

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
                f"User logged in: {user.username}",
                extra={"user_id": user.id, "username": user.username},
            )
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("profile")
        else:
            logger.warning(
                f"Failed login attempt for username: {request.POST.get('username', 'unknown')}",
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
            f"User logged out: {username}",
            extra={"user_id": user_id, "username": username},
        )
        messages.info(request, "You have been logged out.")
        return redirect("core:index")
    else:
        return HttpResponseNotAllowed(["POST"])


@login_required
def profile_view(request):
    logger.debug(
        f"Profile accessed by {request.user.username}",
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
            f"New user registered: {self.object.username} ({self.object.email})",
            extra={"user_id": self.object.id, "username": self.object.username},
        )
        messages.success(self.request, "Account created successfully! Please log in.")
        return response

    def form_invalid(self, form):
        logger.warning(
            f"Registration form invalid: {form.errors.as_json()}",
            extra={"errors": form.errors.as_data()},
        )
        return super().form_invalid(form)
