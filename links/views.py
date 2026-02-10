import logging

from django.views import View
from django.conf import settings
from django.http import Http404
from django.db.models import Count
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.validators import validate_ipv46_address
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)


from .forms import LinkForm
from .models import Link
from .tasks import record_link_click

logger = logging.getLogger(__name__)


class LinkListView(LoginRequiredMixin, ListView):
    model = Link
    template_name = "links/link_list.html"
    context_object_name = "links"

    def get_queryset(self):
        logger.debug(
            f"Fetching links for user {self.request.user.username}",
            extra={"user_id": self.request.user.id},
        )
        return Link.objects.filter(user=self.request.user)


class LinkDetailView(LoginRequiredMixin, DetailView):
    model = Link
    template_name = "links/link_detail.html"
    context_object_name = "link"

    def get_queryset(self):
        return Link.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        link = self.object

        # Build full URL
        context["full_url"] = self.request.build_absolute_uri(link.public_path)

        # Aggregate click statistics with database-side optimizations
        # COUNT(*) is fast even on large tables (uses index)
        context["total_clicks"] = link.clicks.count()

        logger.debug(
            f"Link detail viewed: {link.public_path} ({context['total_clicks']} clicks)",
            extra={"link_id": link.id, "user_id": self.request.user.id},
        )

        # Top referrers - aggregated at DB, limited to 5 rows
        referrer_stats = (
            link.clicks.exclude(referrer="")
            .values("referrer")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
        context["top_referrers"] = referrer_stats

        # Top user agents - aggregated at DB, limited to 5 rows
        user_agent_stats = (
            link.clicks.exclude(user_agent="")
            .values("user_agent")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
        context["top_user_agents"] = user_agent_stats

        # Recent clicks - only select necessary fields to reduce memory/transfer
        context["recent_clicks"] = link.clicks.values(
            "id", "referrer", "user_agent", "created_at", "ip_address"
        ).order_by("-created_at")[:10]

        return context


class LinkCreateView(LoginRequiredMixin, CreateView):
    model = Link
    form_class = LinkForm
    template_name = "links/link_form.html"
    success_url = reverse_lazy("link_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        logger.info(
            f"Link created: {self.object.public_path} -> {self.object.target_url}",
            extra={
                "user_id": self.request.user.id,
                "link_id": self.object.id,
                "slug": self.object.slug,
            },
        )
        return response


class LinkUpdateView(LoginRequiredMixin, UpdateView):
    model = Link
    form_class = LinkForm
    template_name = "links/link_form.html"
    success_url = reverse_lazy("link_list")

    def get_queryset(self):
        return Link.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(
            f"Link updated: {self.object.public_path}",
            extra={"link_id": self.object.id, "user_id": self.request.user.id},
        )
        return response


class LinkDeleteView(LoginRequiredMixin, DeleteView):
    model = Link
    template_name = "links/link_confirm_delete.html"
    success_url = reverse_lazy("link_list")

    def get_queryset(self):
        return Link.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        link = self.get_object()
        logger.info(
            f"Link deleted: {link.public_path}",
            extra={"link_id": link.id, "user_id": request.user.id},
        )
        return super().delete(request, *args, **kwargs)


class LinkPublicRedirectView(View):
    def get(self, request, username, slug):
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
            link = Link.objects.get(user=user, slug=slug)
        except User.DoesNotExist, Link.DoesNotExist:
            logger.warning(
                f"Link not found: /{username}/{slug}/",
                extra={"username": username, "slug": slug},
            )
            raise Http404()

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
        except Exception as exc:
            logger.warning(
                "Failed to queue click record task",
                extra={"link_id": link.id, "error": str(exc)},
            )

        logger.info(
            f"Link redirect: {link.public_path} -> {link.target_url}",
            extra={
                "link_id": link.id,
                "slug": slug,
                "target": link.target_url,
                "ip": ip_address,
            },
        )

        return redirect(link.target_url)

    def _get_client_ip(self, request):
        """Extract client IP safely, validating X-Forwarded-For only if trusted."""
        # Use X-Forwarded-For only if explicitly trusted (behind known proxy)
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for and settings.TRUST_PROXY_HEADERS:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")

        # Validate IP format to prevent malformed data
        if ip:
            try:
                validate_ipv46_address(ip)
            except ValidationError:
                logger.warning(f"Invalid IP format: {ip}", extra={"ip": ip})
                return None

        return ip if ip else None
