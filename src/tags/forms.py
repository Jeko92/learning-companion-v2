import unicodedata

from django import forms
from django.core.exceptions import ValidationError

from tags.models import Tag

# Each entry costs a tag lookup when the form is saved, so the input is
# bounded before any of that work: by length (checked by CharField) and by
# count (in clean).
MAX_TAGS = 20
MAX_TAGS_LENGTH = 1000


def tags_as_text(tags):
    """The tags as the field's typed value, e.g. "Django, Python"."""
    return ", ".join(tag.name for tag in tags)


class TagListField(forms.CharField):
    """Tag names typed as comma-separated text, so a form never lists other
    users' tags. Cleans to a list of names, validated as tag names, without
    empty entries or entries that differ only in case (the first one wins).
    Creates nothing: an invalid entry fails the whole form before any save,
    and the form turns the names into tags with
    Tag.objects.get_or_create_by_name() when it saves."""

    def __init__(self, *, noun="tags", max_tags=MAX_TAGS, **kwargs):
        self.noun = noun
        self.max_tags = max_tags
        kwargs.setdefault("required", False)
        kwargs.setdefault("max_length", MAX_TAGS_LENGTH)
        kwargs.setdefault(
            "help_text", f"Comma-separated, at most {max_tags}, e.g. Python, Django"
        )
        super().__init__(**kwargs)

    def clean(self, value):
        text = super().clean(value)
        names, seen, errors = [], set(), []
        # NFKC first, so full-width commas (CJK keyboards) separate entries too.
        for entry in unicodedata.normalize("NFKC", text).split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                name = Tag.objects.clean_name(entry)
            except ValidationError as error:
                errors.extend(f"“{entry}”: {message}" for message in error.messages)
                continue
            if name.casefold() not in seen:
                seen.add(name.casefold())
                names.append(name)
        if errors:
            raise ValidationError(errors)
        if len(names) > self.max_tags:
            raise ValidationError(f"You can have at most {self.max_tags} {self.noun}.")
        return names
