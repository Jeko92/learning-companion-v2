from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from goals.forms import GoalForm
from goals.models import Goal


class OwnGoalsMixin(LoginRequiredMixin):
    """Only ever the logged-in user's own goals, via Goal.objects.owned_by."""

    model = Goal

    def get_queryset(self):
        return Goal.objects.owned_by(self.request.user)


class GoalListView(OwnGoalsMixin, ListView):
    template_name = "goals/goal_list.html"
    paginate_by = 20


class GoalDetailView(OwnGoalsMixin, DetailView):
    pass


class GoalCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    form_class = GoalForm
    template_name = "goals/goal_form.html"
    # No success_url: CreateView redirects to the new goal's get_absolute_url.
    success_message = "Goal created."

    def form_valid(self, form):
        # The owner is the logged-in user, never form input.
        form.instance.owner = self.request.user
        return super().form_valid(form)


class GoalUpdateView(OwnGoalsMixin, SuccessMessageMixin, UpdateView):
    form_class = GoalForm
    success_message = "Goal updated."
