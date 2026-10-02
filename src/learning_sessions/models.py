from django.db import models


class LearningSession(models.Model):
    """Time spent learning towards one goal."""

    goal = models.ForeignKey(
        "goals.Goal", on_delete=models.CASCADE, related_name="sessions"
    )
