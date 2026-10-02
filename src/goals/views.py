from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from goals.forms import GoalForm
from goals.models import Goal


class OwnGoalsMixin(LoginRequiredMixin):
    """Only ever the logged-in user's own goals, via Goal.objects.owned_by.

    List it *first* in a view's bases, and never set `model` on a goal view:
    listed after the generic view, Django's own get_queryset() wins. Without a
    model that raises ImproperlyConfigured; with `model = Goal` on the view it
    would silently serve every user's goals."""

    def get_queryset(self):
        return Goal.objects.owned_by(self.request.user)


class GoalListView(OwnGoalsMixin, ListView):
    template_name = "goals/goal_list.html"
    paginate_by = 20

    def active_status(self):
        """The status to filter by, or "" (All) for a missing or unknown one."""
        status = self.request.GET.get("status")
        return status if status in Goal.Status.values else ""

    def get_queryset(self):
        goals = super().get_queryset()
        if status := self.active_status():
            goals = goals.filter(status=status)
        return goals

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_status"] = self.active_status()
        context["statuses"] = Goal.Status.choices
        return context


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


class GoalDeleteView(OwnGoalsMixin, SuccessMessageMixin, DeleteView):
    success_url = reverse_lazy("goals:list")

    def get_success_message(self, cleaned_data):
        # A fixed text: DeleteView's cleaned_data is empty, so a %(title)s
        # success_message would raise KeyError after the row is gone.
        return "Goal deleted."
