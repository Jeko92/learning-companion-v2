from django.contrib import admin

from profiles.models import Profile


class ProfileInline(admin.StackedInline):
    """Shown on the User admin (accounts/admin.py), which owns the registration."""

    model = Profile
    can_delete = False
    fields = ("name", "cohort", "focus_areas")
    autocomplete_fields = ("focus_areas",)
