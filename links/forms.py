from __future__ import annotations

from django import forms

from .models import Link


class LinkForm(forms.ModelForm):
    class Meta:
        model = Link
        fields = ["target_url", "slug"]
        widgets = {
            "target_url": forms.URLInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "slug": "Optional. Leave blank to auto-generate. Per-user unique.",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        if not slug or not self.user:
            return slug
        qs = Link.objects.filter(user=self.user, slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("You already have a link with this slug.")
        return slug
