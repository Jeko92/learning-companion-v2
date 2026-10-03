from django.db import models


class Resource(models.Model):
    """Reference material (an article, video, repo or doc) for one goal."""

    goal = models.ForeignKey(
        "goals.Goal", on_delete=models.CASCADE, related_name="resources"
    )
