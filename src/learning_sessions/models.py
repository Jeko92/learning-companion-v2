from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import Prefetch, Q, Sum
from django.db.models.functions import Lower, TruncWeek
from django.utils import timezone


def reject_future_dates(value):
    """A session logs time already spent, so it can't happen after today."""
    if value > timezone.localdate():
        raise ValidationError("A session can't be in the future.", code="future")


class LearningSessionQuerySet(models.QuerySet):
    def owned_by(self, user):
        """The one way views look up sessions: only those on the user's goals."""
        return self.filter(goal__owner=user)

    def with_tags(self):
        """Tags fetched in one query for all the sessions, alphabetical
        regardless of case (Tag's own ordering is case-sensitive)."""
        from tags.models import Tag

        tags = Tag.objects.order_by(Lower("name"), "id")
        return self.prefetch_related(Prefetch("tags", queryset=tags))

    def minutes_per_tag(self):
        """(tag name, minutes) per tag, largest total first and ties by name
        regardless of case, then (None, minutes) for untagged time if any, in
        one query. A session with several tags counts in full under each."""
        # The explicit order_by() replaces any incoming ordering, which would
        # otherwise add its columns to GROUP BY and split the groups.
        rows = (
            self.values("tags", "tags__name")
            .annotate(total=Sum("duration_minutes"))
            .order_by("-total", Lower("tags__name"))
        )
        totals = [(row["tags__name"], row["total"]) for row in rows]
        # Untagged sessions form the one group without a tag (the outer join).
        return sorted(totals, key=lambda total: total[0] is None)

    def minutes_per_week(self, today, weeks):
        """(Monday, minutes) for the `weeks` weeks ending with the one that
        contains `today`, newest first and 0 for a week without sessions, in
        one query. Sessions dated outside those weeks don't count."""
        newest = today - timedelta(days=today.weekday())
        mondays = [newest - timedelta(weeks=n) for n in range(weeks)]
        # order_by() clears any incoming ordering, which would split the groups.
        rows = (
            self.order_by()
            .filter(date__gte=mondays[-1], date__lt=newest + timedelta(weeks=1))
            .annotate(week=TruncWeek("date"))
            .values("week")
            .annotate(total=Sum("duration_minutes"))
        )
        found = {row["week"]: row["total"] for row in rows}
        return [(monday, found.get(monday, 0)) for monday in mondays]


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
