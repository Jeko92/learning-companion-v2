from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from goals.models import Goal


class GoalListView(LoginRequiredMixin, ListView):
    model = Goal
    template_name = "goals/goal_list.html"
