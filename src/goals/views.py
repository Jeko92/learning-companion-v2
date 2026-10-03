from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from django.views.generic.detail import SingleObjectMixin

from ai import services
from goals.forms import GoalForm
from goals.models import Goal
from goals.prompts import summary_messages
from learning_sessions.models import LearningSession
from resources.forms import ResourceForm
from resources.models import Resource


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
        # Before filtering: tells "filter hides everything" from "no goals".
        context["has_goals"] = super().get_queryset().exists()
        return context


class GoalDetailView(OwnGoalsMixin, DetailView):
    RECENT_SESSIONS = 5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Sessions only through owned_by, even for a goal that is already the
        # user's own (see CLAUDE.md, Learning sessions).
        sessions = LearningSession.objects.owned_by(self.request.user).filter(
            goal=self.object
        )
        context["recent_sessions"] = sessions.with_tags()[: self.RECENT_SESSIONS]
        # Over all sessions, not just those shown; an empty Sum() is None.
        context["total_minutes"] = (
            sessions.aggregate(total=Sum("duration_minutes"))["total"] or 0
        )
        # Resources too only through owned_by; one query for all the groups.
        context["resource_groups"] = (
            Resource.objects.owned_by(self.request.user)
            .filter(goal=self.object)
            .grouped_by_type()
        )
        context["resource_form"] = ResourceForm()
        return context


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # The sessions and resources that cascade with the goal, for the warnings.
        context["session_count"] = (
            LearningSession.objects.owned_by(self.request.user)
            .filter(goal=self.object)
            .count()
        )
        context["resource_count"] = (
            Resource.objects.owned_by(self.request.user)
            .filter(goal=self.object)
            .count()
        )
        return context


class GoalSummaryView(OwnGoalsMixin, SingleObjectMixin, View):
    """POST only (anything else is a 405): generate the goal's AI progress
    summary, then back to the goal page."""

    http_method_names = ("post",)
    SUMMARY_SESSIONS = 10
    SUMMARY_RESOURCES = 20

    def post(self, request, *args, **kwargs):
        # Through OwnGoalsMixin: another user's goal is a 404 like a missing one.
        goal = self.get_object()
        sessions = LearningSession.objects.owned_by(request.user).filter(goal=goal)
        resources = Resource.objects.owned_by(request.user).filter(goal=goal)
        if not sessions.exists() and not resources.exists():
            # Nothing to summarise: don't spend an API call on it.
            messages.info(request, "Log a session or attach a resource first.")
            return redirect(goal)
        system, user = summary_messages(
            goal,
            list(sessions.with_tags()[: self.SUMMARY_SESSIONS]),
            sessions.aggregate(total=Sum("duration_minutes"))["total"] or 0,
            list(resources[: self.SUMMARY_RESOURCES]),
        )
        # No retries: the user is waiting on this page (see ai.services.complete).
        goal.summary = services.complete(system, user, max_retries=0).strip()
        goal.summary_generated_at = timezone.now()
        # update_fields leaves updated_at alone: the goal itself didn't change.
        goal.save(update_fields=["summary", "summary_generated_at"])
        messages.success(request, "Summary generated.")
        return redirect(goal)
