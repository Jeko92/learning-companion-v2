from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model

from profiles.admin import ProfileInline


@admin.register(get_user_model())
class UserAdmin(auth_admin.UserAdmin):
    # Registered once, here, so the inline doesn't depend on INSTALLED_APPS order.
    inlines = (ProfileInline,)

    def get_inlines(self, request, obj):
        # Not on the add page: the post_save signal creates the profile, and a
        # filled-in inline would try to save a second one.
        return self.inlines if obj else ()
