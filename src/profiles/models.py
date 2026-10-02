from django.conf import settings
from django.db import models


class Profile(models.Model):
    """A user's own data; it never goes on the user model (see CLAUDE.md)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    name = models.CharField(max_length=100, blank=True)
    cohort = models.CharField(max_length=50, blank=True)
    focus_areas = models.ManyToManyField(
        "tags.Tag", blank=True, related_name="profiles"
    )
