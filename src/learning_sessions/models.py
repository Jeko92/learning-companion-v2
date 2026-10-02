from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class LearningSession(models.Model):
    """Time spent learning towards one goal."""

    goal = models.ForeignKey(
        "goals.Goal", on_delete=models.CASCADE, related_name="sessions"
    )
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )

    class Meta:
        constraints = (
            # The validators are only checked by full_clean() and forms; this
            # stops update() and bulk_create() too. PositiveIntegerField's own
            # database check would still allow 0.
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=1, duration_minutes__lte=1440),
                name="learning_sessions_learningsession_duration_valid",
            ),
        )
