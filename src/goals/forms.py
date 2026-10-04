from django import forms

from core.forms import StyledFormMixin
from goals.models import Goal


class GoalForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Goal
        # An explicit allow-list: the owner is never form input (it comes
        # from the logged-in user), so it can't be posted.
        fields = ("title", "description", "status")


class GoalMoveForm(StyledFormMixin, forms.Form):
    """A goal's new status on the board (goals.views.GoalMoveView)."""

    status = forms.ChoiceField(
        choices=Goal.Status.choices,
        error_messages={
            "required": "Choose a valid status.",
            "invalid_choice": "Choose a valid status.",
        },
    )
