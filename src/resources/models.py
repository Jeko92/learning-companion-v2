from django.core.validators import URLValidator
from django.db import models


def strip(value):
    """Trim the ends of free text; other values reach field validation."""
    return value.strip() if isinstance(value, str) else value


class HttpURLField(models.URLField):
    """A URLField for http(s) only. Resources are rendered as links, so
    javascript:, data: or ftp: URLs must never get in. This *replaces*
    URLField's default validator (which also allows ftp and ftps) rather than
    adding to it, so a bad URL gets one error, not two."""

    default_validators = (URLValidator(schemes=("http", "https")),)


class Resource(models.Model):
    """Reference material (an article, video, repo or doc) for one goal.
    Ownership is the goal's owner; look resources up through owned_by."""

    goal = models.ForeignKey(
        "goals.Goal", on_delete=models.CASCADE, related_name="resources"
    )
    url = HttpURLField(max_length=2048)

    def clean_fields(self, exclude=None):
        # Model fields don't strip: trim first so "  " fails as blank.
        self.url = strip(self.url)
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self.url = strip(self.url)
        super().save(*args, **kwargs)
