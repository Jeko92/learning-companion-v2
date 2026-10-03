from django import forms

from learning_sessions.models import LearningSession
from tags.forms import TagListField


class LearningSessionForm(forms.ModelForm):
    tags = TagListField()

    class Meta:
        model = LearningSession
        # An explicit allow-list: the goal comes from the URL, never the form.
        fields = ("date", "duration_minutes", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ISO format: a type="date" input shows nothing for a localised
        # value, which would blank the date on the edit page.
        self.fields["date"].widget = forms.DateInput(
            attrs={"type": "date"}, format="%Y-%m-%d"
        )
