from django import forms
from django.db import transaction

from profiles.models import Profile
from tags.forms import TagListField, tags_as_text
from tags.models import Tag


class ProfileForm(forms.ModelForm):
    focus_areas = TagListField(noun="focus areas")

    class Meta:
        model = Profile
        fields = ("name", "cohort")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank on the model (auto-created profiles start empty), required here.
        self.fields["name"].required = True
        # An unsaved profile has no focus areas (and can't be queried for them).
        self.fields["focus_areas"].initial = (
            tags_as_text(self.instance.focus_areas.all()) if self.instance.pk else ""
        )

    @transaction.atomic
    def save(self, commit=True):
        return super().save(commit=commit)

    def _save_m2m(self):
        # Django calls this from save(commit=True), or later from save_m2m()
        # after save(commit=False), so tags are only created with the profile.
        super()._save_m2m()
        self.instance.focus_areas.set(
            Tag.objects.get_or_create_by_name(name)[0]
            for name in self.cleaned_data["focus_areas"]
        )
