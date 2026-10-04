from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
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
from goals.forms import GoalForm, GoalMoveForm
from goals.models import Goal
from goals.prompts import (
    NEXT_STEPS_SCHEMA,
    next_steps_messages,
    parse_next_steps,
    summary_messages,
)
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
    """The goal board: a column per status (just one for a ?status= filter),
    each newest first. Not paginated: a board shows every goal."""

    template_name = "goals/goal_list.html"

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
        # (value, label, goals) per shown column, from the one list query.
        goals = list(context["object_list"])
        context["columns"] = [
            (value, label, [g for g in goals if g.status == value])
            for value, label in Goal.Status.choices
            if value == self.active_status() or not self.active_status()
        ]
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


PROMPT_SESSIONS = 10
PROMPT_RESOURCES = 20


def prompt_data(goal, user):
    """What the AI actions send about `goal`, all through owned_by(user): its
    PROMPT_SESSIONS newest sessions (tags prefetched), the total minutes over
    all its sessions, and its PROMPT_RESOURCES newest resources."""
    sessions = LearningSession.objects.owned_by(user).filter(goal=goal)
    resources = Resource.objects.owned_by(user).filter(goal=goal)
    return (
        list(sessions.with_tags()[:PROMPT_SESSIONS]),
        sessions.aggregate(total=Sum("duration_minutes"))["total"] or 0,
        list(resources[:PROMPT_RESOURCES]),
    )


class GoalSummaryView(OwnGoalsMixin, SingleObjectMixin, View):
    """POST only (anything else is a 405): generate the goal's AI progress
    summary, then back to the goal page."""

    http_method_names = ("post",)

    def post(self, request, *args, **kwargs):
        # Through OwnGoalsMixin: another user's goal is a 404 like a missing one.
        goal = self.get_object()
        sessions, total_minutes, resources = prompt_data(goal, request.user)
        if not sessions and not resources:
            # Nothing to summarise: don't spend an API call on it.
            messages.info(request, "Log a session or attach a resource first.")
            return redirect(goal)
        system, user = summary_messages(goal, sessions, total_minutes, resources)
        try:
            # No retries: the user is waiting on this page (see
            # ai.services.complete).
            reply = services.complete(system, user, max_retries=0)
        except services.AIServiceError as error:
            # Always caught: a 500 would print the chained SDK error, whose
            # text can echo part of the key. The message itself is user-safe.
            messages.error(request, str(error))
            return redirect(goal)
        goal.summary = reply.strip()
        goal.summary_generated_at = timezone.now()
        # update_fields leaves updated_at alone: the goal itself didn't change.
        goal.save(update_fields=["summary", "summary_generated_at"])
        messages.success(request, "Summary generated.")
        return redirect(goal)


class GoalMoveView(OwnGoalsMixin, SingleObjectMixin, View):
    """POST only (anything else is a 405): move a goal to another board column,
    that is, change its status. The board's drag and drop posts with
    Accept: application/json and gets JSON back; the cards' Move menu is a
    plain form, redirected to a same-site `next` or the board."""

    http_method_names = ("post",)

    def post(self, request, *args, **kwargs):
        # Through OwnGoalsMixin: another user's goal is a 404 like a missing one.
        goal = self.get_object()
        wants_json = request.headers.get("Accept") == "application/json"
        form = GoalMoveForm(request.POST)
        if not form.is_valid():
            (error,) = form.errors["status"]
            if wants_json:
                return JsonResponse({"error": error}, status=400)
            messages.error(request, error)
            return redirect(self.next_url())
        goal.status = form.cleaned_data["status"]
        # A status change is a change to the goal, so updated_at moves too.
        goal.save(update_fields=["status", "updated_at"])
        if wants_json:
            # The page doesn't reload: no flash message for the next one.
            return JsonResponse(
                {"status": goal.status, "label": goal.get_status_display()}
            )
        messages.success(
            request, f"Moved “{goal.title}” to {goal.get_status_display()}."
        )
        return redirect(self.next_url())

    def next_url(self):
        """The posted `next` if it's on this site, else the board."""
        next_url = self.request.POST.get("next", "")
        if url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        return reverse("goals:list")


class GoalNextStepsView(OwnGoalsMixin, SingleObjectMixin, View):
    """POST only (anything else is a 405): suggest 2-3 AI next learning steps
    for the goal, then back to the goal page."""

    http_method_names = ("post",)

    def post(self, request, *args, **kwargs):
        # Through OwnGoalsMixin: another user's goal is a 404 like a missing one.
        goal = self.get_object()
        system, user = next_steps_messages(goal, *prompt_data(goal, request.user))
        try:
            # No retries, as for the summary: the user is waiting on this page.
            reply = services.complete_json(
                system, user, name="next_steps", schema=NEXT_STEPS_SCHEMA, max_retries=0
            )
            steps = parse_next_steps(reply)
        except services.AIServiceError as error:
            # Always caught, as for the summary; the earlier steps are kept.
            messages.error(request, str(error))
            return redirect(goal)
        goal.next_steps = steps
        goal.next_steps_generated_at = timezone.now()
        # update_fields leaves updated_at alone: the goal itself didn't change.
        goal.save(update_fields=["next_steps", "next_steps_generated_at"])
        messages.success(request, "Next steps suggested.")
        return redirect(goal)
