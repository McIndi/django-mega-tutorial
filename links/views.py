from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import LinkForm
from .models import Click, Link


class LinkListView(LoginRequiredMixin, ListView):
    model = Link
    template_name = "links/link_list.html"
    context_object_name = "links"

    def get_queryset(self):
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

        # Aggregate click statistics
        clicks = link.clicks.all()
        context["total_clicks"] = clicks.count()

        # Top referrers
        referrer_stats = (
            clicks.exclude(referrer="")
            .values("referrer")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
        context["top_referrers"] = referrer_stats

        # Top user agents
        user_agent_stats = (
            clicks.exclude(user_agent="")
            .values("user_agent")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
        context["top_user_agents"] = user_agent_stats

        # Recent clicks
        context["recent_clicks"] = clicks[:10]

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
        return super().form_valid(form)


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


class LinkDeleteView(LoginRequiredMixin, DeleteView):
    model = Link
    template_name = "links/link_confirm_delete.html"
    success_url = reverse_lazy("link_list")

    def get_queryset(self):
        return Link.objects.filter(user=self.request.user)


class LinkPublicRedirectView(View):
    def get(self, request, username, slug):
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
            link = Link.objects.get(user=user, slug=slug)
        except (User.DoesNotExist, Link.DoesNotExist):
            raise Http404()

        Click.objects.create(
            link=link,
            referrer=request.META.get("HTTP_REFERER", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ip_address=self._get_client_ip(request),
        )

        return redirect(link.target_url)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip if ip else None
