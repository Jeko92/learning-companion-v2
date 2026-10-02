from django import forms

from profiles.models import Profile


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
