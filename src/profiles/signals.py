from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from profiles.models import Profile


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="profiles.create_profile_for_new_user",
)
def create_profile_for_new_user(sender, instance, created, raw, **kwargs):
    """Every user gets a profile, however they were created (sign-up,
    createsuperuser, the admin). Fixture loads (raw) are left alone."""
    if created and not raw:
        Profile.objects.get_or_create(user=instance)
