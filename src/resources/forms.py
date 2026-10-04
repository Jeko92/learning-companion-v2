from django import forms
from django.core.exceptions import ValidationError

from core.forms import StyledFormMixin
from resources.models import Resource


class ResourceForm(StyledFormMixin, forms.ModelForm):
    """Expects the goal already set on the instance (the view passes
    instance=Resource(goal=...))."""

    class Meta:
        model = Resource
        # An explicit allow-list: the goal comes from the URL, never the form.
        fields = ("url", "title", "type")

    def validate_constraints(self):
        # `goal` isn't a form field, so Django would exclude it and skip the
        # (goal, url) unique constraint. Keep it in, so a duplicate URL is the
        # model's own non-field error instead of an IntegrityError on save.
        exclude = self._get_validation_exclusions() - {"goal"}
        try:
            self.instance.validate_constraints(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e)
