from django.conf import settings
from django.db import models
from django.db.models import Q


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
        constraints = (
            # choices are only checked by full_clean() and forms; this stops
            # update() and bulk_create() from storing anything else.
            models.CheckConstraint(
                condition=Q(status__in=("planned", "in-progress", "done")),
                name="goals_goal_status_valid",
            ),
        )
