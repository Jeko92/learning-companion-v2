from django.core.validators import URLValidator
from django.db import models
from django.db.models import Q


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
    title = models.CharField(max_length=200)

    class Meta:
        constraints = (
            # The validator only runs through full_clean()/forms; this stops
            # update()/bulk_create() from storing javascript: or data: links.
            models.CheckConstraint(
                condition=Q(url__istartswith="http://")
                | Q(url__istartswith="https://"),
                name="resources_resource_url_http",
            ),
        )

    def trim(self):
        self.url, self.title = strip(self.url), strip(self.title)

    def clean_fields(self, exclude=None):
        # Model fields don't strip: trim first, so "  " fails as blank.
        self.trim()
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self.trim()
        super().save(*args, **kwargs)
