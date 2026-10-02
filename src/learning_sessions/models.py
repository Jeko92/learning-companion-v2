from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone


def reject_future_dates(value):
    """A session logs time already spent, so it can't happen after today."""
    if value > timezone.localdate():
        raise ValidationError("A session can't be in the future.", code="future")


class LearningSessionQuerySet(models.QuerySet):
    def owned_by(self, user):
        """The one way views look up sessions: only those on the user's goals."""
        return self.filter(goal__owner=user)


class LearningSession(models.Model):
    """Time spent learning towards one goal."""

    goal = models.ForeignKey(
        "goals.Goal", on_delete=models.CASCADE, related_name="sessions"
    )
    date = models.DateField(
        default=timezone.localdate, validators=[reject_future_dates]
    )
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    # A TextField's max_length only shapes the form widget; the validator
    # holds the limit for forms, full_clean() and the admin alike.
    notes = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    tags = models.ManyToManyField("tags.Tag", blank=True, related_name="sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LearningSessionQuerySet.as_manager()

    class Meta:
        # Newest first: by the day it happened, then by when it was logged;
        # the id breaks ties between sessions recorded together.
        ordering = ("-date", "-created_at", "-id")
        constraints = (
            # The validators are only checked by full_clean() and forms; this
            # stops update() and bulk_create() too. PositiveIntegerField's own
            # database check would still allow 0.
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=1, duration_minutes__lte=1440),
                name="learning_sessions_learningsession_duration_valid",
            ),
        )

    def __str__(self):
        return f"{self.goal} · {self.date:%Y-%m-%d} · {self.duration_minutes} min"
