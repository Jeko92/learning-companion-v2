from django.db import IntegrityError, models, transaction
from django.db.models.functions import Lower


class TagManager(models.Manager):
    def get_or_create_by_name(self, name):
        """Turn typed input into a tag: (tag, created), matched the way the
        unique constraint compares names (trimmed, ASCII case-insensitive), so
        the first spelling is kept. A blank name raises ValidationError.
        Safe when another request creates the same name concurrently."""
        name = name.strip()
        tag = self.filter(name__iexact=name).first()
        if tag is not None:
            return tag, False
        tag = self.model(name=name)
        # Uniqueness is left to the database, so a lost race is an
        # IntegrityError we can recover from, not a ValidationError.
        tag.full_clean(validate_constraints=False)
        try:
            # Savepoint: a failed insert must not break the caller's transaction.
            with transaction.atomic():
                tag.save()
        except IntegrityError:
            return self.get(name__iexact=name), False
        return tag, True


class Tag(models.Model):
    """A shared label, e.g. a profile's focus area (and later a session tag)."""

    name = models.CharField(max_length=50)

    objects = TagManager()

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
