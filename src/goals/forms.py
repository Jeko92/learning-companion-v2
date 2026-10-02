from django import forms

from goals.models import Goal


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        # An explicit allow-list: the owner is never form input (it comes
        # from the logged-in user), so it can't be posted.
        fields = ("title", "description", "status")
