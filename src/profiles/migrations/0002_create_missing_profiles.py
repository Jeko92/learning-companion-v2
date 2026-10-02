from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    """Give every user that existed before the profiles app a profile.

    Historical models don't fire the post_save signal, so the profiles are
    created here. Users that already have one are left alone.
    """
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Profile = apps.get_model("profiles", "Profile")
    users_with_profile = Profile.objects.values("user_id")
    Profile.objects.bulk_create(
        Profile(user_id=pk)
        for pk in User.objects.exclude(pk__in=users_with_profile).values_list(
            "pk", flat=True
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
