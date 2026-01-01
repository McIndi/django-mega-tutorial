import secrets
import string

from django.conf import settings
from django.db import models


SLUG_ALPHABET = string.ascii_lowercase + string.digits
SLUG_LENGTH = 8


def generate_slug(length: int = SLUG_LENGTH) -> str:
    return "".join(secrets.choice(SLUG_ALPHABET) for _ in range(length))


class Link(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="links",
    )
    target_url = models.URLField(max_length=500)
    slug = models.SlugField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "slug"], name="unique_link_slug_per_user"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"{self.user.username}/{self.slug} -> {self.target_url}"

    @property
    def public_path(self) -> str:
        return f"/{self.user.username}/{self.slug}/"

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self) -> str:
        # Simple loop because collisions are rare; retries are inexpensive at this scale.
        while True:
            candidate = generate_slug()
            if not Link.objects.filter(user=self.user, slug=candidate).exists():
                return candidate


class Click(models.Model):
    link = models.ForeignKey(Link, on_delete=models.CASCADE, related_name="clicks")
    created_at = models.DateTimeField(auto_now_add=True)
    referrer = models.URLField(max_length=500, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"Click on {self.link} at {self.created_at.isoformat()}"
