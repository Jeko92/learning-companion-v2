from django.db import models


class Tag(models.Model):
    """A shared label, e.g. a profile's focus area (and later a session tag)."""

    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

    def clean_fields(self, exclude=None):
        # Strip first, so a whitespace-only name fails as blank.
        self.name = self.name.strip()
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        # Model CharFields don't strip; "Python" and " Python" must be one tag.
        self.name = self.name.strip()
        super().save(*args, **kwargs)
