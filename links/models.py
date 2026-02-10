import secrets
import string

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

SLUG_ALPHABET = string.ascii_lowercase + string.digits
SLUG_LENGTH = 10


def generate_slug(length: int = SLUG_LENGTH) -> str:
    return "".join(secrets.choice(SLUG_ALPHABET) for _ in range(length))


class Link(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="links",
    )
    target_url = models.URLField(max_length=500)
    slug = models.SlugField(
        max_length=32,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9_-]+$",
                message="Use only lowercase letters, numbers, hyphens, and underscores.",
            )
        ],
    )
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

    def _generate_unique_slug(self, attempts: int = 10) -> str:
        """Generate a per-user unique slug with bounded retries."""
        for _ in range(attempts):
            candidate = generate_slug(length=SLUG_LENGTH)
            if not Link.objects.filter(user=self.user, slug=candidate).exists():
                return candidate
        raise RuntimeError("Could not generate unique slug after multiple attempts")


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
