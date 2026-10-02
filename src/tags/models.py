from django.db import models
from django.db.models.functions import Lower


class Tag(models.Model):
    """A shared label, e.g. a profile's focus area (and later a session tag)."""

    name = models.CharField(max_length=50)

    class Meta:
        ordering = ("name",)
        constraints = (
            # "Python" and "python" are one tag. SQLite's LOWER() is ASCII-only.
            models.UniqueConstraint(
                Lower("name"),
                name="tags_tag_name_ci_unique",
                violation_error_message="A tag with this name already exists.",
            ),
        )

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
