from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from profiles.models import Profile
from tags.models import Tag


class ProfileForm(forms.ModelForm):
    # Typed as text, so the form never lists other users' tags.
    focus_areas = forms.CharField(
        required=False, help_text="Comma-separated, e.g. Python, Django"
    )

    class Meta:
        model = Profile
        fields = ("name", "cohort")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank on the model (auto-created profiles start empty), required here.
        self.fields["name"].required = True
        self.fields["focus_areas"].initial = ", ".join(
            tag.name for tag in self.instance.focus_areas.all()
        )

    def clean_focus_areas(self):
        """The typed names, validated as tag names, without empty entries or
        entries that differ only in case (the first one wins). Creates
        nothing: an invalid entry fails the whole form before any save."""
        names, seen, errors = [], set(), []
        for entry in self.cleaned_data["focus_areas"].split(","):
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
        return names

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=commit)
        profile.focus_areas.set(
            Tag.objects.get_or_create_by_name(name)[0]
            for name in self.cleaned_data["focus_areas"]
        )
        return profile
