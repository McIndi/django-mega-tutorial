from django.contrib import admin

from .models import Link, Click


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ("public_path", "target_url", "user", "created_at")
    search_fields = ("public_path", "target_url", "user__username")
    list_filter = ("created_at",)


@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ("link", "created_at", "ip_address", "user_agent")
    search_fields = ("link__public_path", "ip_address", "user_agent")
    list_filter = ("created_at",)
