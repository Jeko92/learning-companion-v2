from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model

from profiles.admin import ProfileInline


@admin.register(get_user_model())
class UserAdmin(auth_admin.UserAdmin):
    # Registered once, here, so the inline doesn't depend on INSTALLED_APPS order.
    inlines = (ProfileInline,)
