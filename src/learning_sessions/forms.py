from django import forms
from django.db import transaction
from django.db.models.functions import Lower

from core.forms import StyledFormMixin
from learning_sessions.models import LearningSession
from tags.forms import TagListField, tags_as_text
from tags.models import Tag


class LearningSessionForm(StyledFormMixin, forms.ModelForm):
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
        # Alphabetical regardless of case (Tag's own ordering is
        # case-sensitive). An unsaved session has no tags to query.
        if self.instance.pk:
            self.fields["tags"].initial = tags_as_text(
                self.instance.tags.order_by(Lower("name"), "id")
            )

    @transaction.atomic
    def save(self, commit=True):
        # The session and its tags together, or neither.
        return super().save(commit=commit)

    def _save_m2m(self):
        # Django calls this from save(commit=True), or later from save_m2m()
        # after save(commit=False), so tags are only created with the session.
        super()._save_m2m()
        self.instance.tags.set(
            Tag.objects.get_or_create_by_name(name)[0]
            for name in self.cleaned_data["tags"]
        )
