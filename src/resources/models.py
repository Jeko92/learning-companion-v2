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

    class Type(models.TextChoices):
        # The value is stored, the label is shown. The type constraint in
        # Meta lists the values too (a test keeps the two in step).
        ARTICLE = "article", "Article"
        VIDEO = "video", "Video"
        REPO = "repo", "Repo"
        DOC = "doc", "Doc"

    goal = models.ForeignKey(
        "goals.Goal", on_delete=models.CASCADE, related_name="resources"
    )
    url = HttpURLField(max_length=2048)
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.ARTICLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest first; the id breaks ties between equal timestamps.
        ordering = ("-created_at", "-id")
        constraints = (
            # The validator only runs through full_clean()/forms; this stops
            # update()/bulk_create() from storing javascript: or data: links.
            models.CheckConstraint(
                condition=Q(url__istartswith="http://")
                | Q(url__istartswith="https://"),
                name="resources_resource_url_http",
            ),
            # Choices are only checked by full_clean()/forms; this stops
            # update()/bulk_create() from storing any other type.
            models.CheckConstraint(
                condition=Q(type__in=("article", "video", "repo", "doc")),
                name="resources_resource_type_valid",
            ),
            # Compared exactly as stored (after trimming). full_clean()
            # reports it as a non-field error, but skips it when `goal` is
            # excluded, e.g. by a ModelForm without a goal field, whose view
            # must then check for duplicates itself.
            models.UniqueConstraint(
                fields=("goal", "url"),
                name="resources_resource_goal_url_unique",
                violation_error_message="This goal already has this resource.",
            ),
        )

    def __str__(self):
        return self.title

    def trim(self):
        self.url, self.title = strip(self.url), strip(self.title)

    def clean_fields(self, exclude=None):
        # Model fields don't strip: trim first, so "  " fails as blank.
        self.trim()
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self.trim()
        super().save(*args, **kwargs)
