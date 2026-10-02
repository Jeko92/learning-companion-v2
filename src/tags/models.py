from django.db import models


class Tag(models.Model):
    """A shared label, e.g. a profile's focus area (and later a session tag)."""

    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name
