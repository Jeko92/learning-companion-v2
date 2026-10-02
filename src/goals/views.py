from django.views.generic import ListView

from goals.models import Goal


class GoalListView(ListView):
    model = Goal
    template_name = "goals/goal_list.html"
