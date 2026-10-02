from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, ListView

from goals.forms import GoalForm
from goals.models import Goal


class OwnGoalsMixin(LoginRequiredMixin):
    """Only ever the logged-in user's own goals, via Goal.objects.owned_by."""

    model = Goal

    def get_queryset(self):
        return Goal.objects.owned_by(self.request.user)


class GoalListView(OwnGoalsMixin, ListView):
    template_name = "goals/goal_list.html"


class GoalCreateView(LoginRequiredMixin, CreateView):
    form_class = GoalForm
    template_name = "goals/goal_form.html"
