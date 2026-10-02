import unicodedata

from django.db import IntegrityError, models, transaction
from django.db.models.functions import Lower


def normalize_name(value):
    """NFKC (full-width letters, composed vs decomposed accents) and trimmed,
    collapsed whitespace, so look-alike spellings are one tag. Only strings
    are touched, so other values still reach field validation (e.g. None
    gives "cannot be null")."""
    if not isinstance(value, str):
        return value
    return " ".join(unicodedata.normalize("NFKC", value).split())


class TagManager(models.Manager):
    def clean_name(self, name):
        """The name as it would be stored, or ValidationError if it's invalid.
        Field validation only: no database access, nothing is created."""
        tag = self.model(name=name)
        tag.clean_fields()
        return tag.name

    def get_or_create_by_name(self, name):
        """Turn typed input into a tag: (tag, created), matched the way the
        unique constraint compares names (normalised, ASCII case-insensitive), so
        the first spelling is kept. A blank name raises ValidationError.
        Safe when another request creates the same name concurrently."""
        name = normalize_name(name)
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
        # Normalise first, so a whitespace-only name fails as blank.
        self.name = normalize_name(self.name)
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        # "Python", " Python" and "ＰＹＴＨＯＮ" must be one tag.
        self.name = normalize_name(self.name)
        super().save(*args, **kwargs)
