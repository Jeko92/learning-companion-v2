from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    name = "profiles"

    def ready(self):
        from profiles import signals  # noqa: F401 (connects the receivers)
