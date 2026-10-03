from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse


def strip(value):
    """Trim the ends of free text; other values reach field validation."""
    return value.strip() if isinstance(value, str) else value


class GoalQuerySet(models.QuerySet):
    def owned_by(self, user):
        """The one way views look up goals: only the given user's own."""
        return self.filter(owner=user)

    def status_counts(self):
        """Goals per status, every status in choice order (0 if none), one query."""
        # order_by() drops the default ordering, which would split the groups.
        counted = self.order_by().values_list("status").annotate(count=Count("id"))
        found = dict(counted)
        return {status: found.get(status, 0) for status in Goal.Status.values}


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
    # One limit for forms, full_clean() and the admin (TextField's own
    # max_length would only shape the form widget).
    description = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # The latest AI progress summary (see goals.views.GoalSummaryView). Not in
    # GoalForm; saved with update_fields, so it doesn't move updated_at.
    summary = models.TextField(blank=True)
    summary_generated_at = models.DateTimeField(null=True, blank=True)
    # The latest 2-3 AI next steps, a list of strings in order (see
    # goals.views.GoalNextStepsView). Kept like the summary.
    next_steps = models.JSONField(default=list, blank=True)
    next_steps_generated_at = models.DateTimeField(null=True, blank=True)

    objects = GoalQuerySet.as_manager()

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

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("goals:detail", args=[self.pk])

    def clean_fields(self, exclude=None):
        # Model CharFields don't strip: trim first so "   " fails as blank.
        self.title = strip(self.title)
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self.title = strip(self.title)
        super().save(*args, **kwargs)
