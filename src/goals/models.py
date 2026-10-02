from django.conf import settings
from django.db import models
from django.db.models import Q


def strip(value):
    """Trim the ends of free text; other values reach field validation."""
    return value.strip() if isinstance(value, str) else value


class Goal(models.Model):
    """A learning goal, owned by one user."""

    class Status(models.TextChoices):
        # "in-progress" matches the goals list's ?status= filter values.
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in-progress", "In progress"
        DONE = "done", "Done"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest first; the id breaks ties between goals created together.
        ordering = ("-created_at", "-id")
        constraints = (
            # choices are only checked by full_clean() and forms; this stops
            # update() and bulk_create() from storing anything else.
            models.CheckConstraint(
                condition=Q(status__in=("planned", "in-progress", "done")),
                name="goals_goal_status_valid",
            ),
        )

    def clean_fields(self, exclude=None):
        # Model CharFields don't strip: trim first so "   " fails as blank.
        self.title = strip(self.title)
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self.title = strip(self.title)
        super().save(*args, **kwargs)
