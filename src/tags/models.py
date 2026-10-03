import unicodedata

from django.core.exceptions import ValidationError
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


def reject_invisible_characters(value):
    """Control and format characters (NUL, zero-width space, BOM, ...) would
    make tags that look identical but aren't. Runs after normalize_name, which
    has already turned whitespace controls like tabs into spaces."""
    if any(unicodedata.category(char) in ("Cc", "Cf") for char in value):
        raise ValidationError(
            "Tag names can't contain control or invisible characters.",
            code="invisible_characters",
        )


def reject_commas(value):
    """The comma separates typed tag lists (tags.forms.TagListField), so a
    name containing one could not be typed back unchanged."""
    if "," in value:
        raise ValidationError("Tag names can't contain commas.", code="comma")


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
        the first spelling is kept. An invalid name raises ValidationError.
        Safe when another request creates the same name concurrently."""
        # Validate first: an over-long name must never reach SQLite's LIKE.
        # Uniqueness is left to the database, so a lost race is an
        # IntegrityError we can recover from, not a ValidationError.
        name = self.clean_name(name)
        tag = self.filter(name__iexact=name).first()
        if tag is not None:
            return tag, False
        tag = self.model(name=name)
        try:
            # Savepoint: a failed insert must not break the caller's transaction.
            with transaction.atomic():
                tag.save()
        except IntegrityError:
            return self.get(name__iexact=name), False
        return tag, True


class Tag(models.Model):
    """A shared label, e.g. a profile's focus area (and later a session tag)."""

    name = models.CharField(
        max_length=50, validators=[reject_invisible_characters, reject_commas]
    )

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
