from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, UpdateView

from goals.models import Goal
from learning_sessions.forms import LearningSessionForm
from learning_sessions.models import LearningSession


class OwnSessionsMixin(LoginRequiredMixin):
    """Only ever the logged-in user's own sessions, via
    LearningSession.objects.owned_by.

    The same rules as goals.views.OwnGoalsMixin: list it *first* in a view's
    bases and never set `model` on a session view, or Django's own
    get_queryset() wins and could serve every user's sessions."""

    def get_queryset(self):
        return LearningSession.objects.owned_by(self.request.user).select_related(
            "goal"
        )

    def get_success_url(self):
        # Sessions have no page of their own: back to the goal after a change.
        return self.object.goal.get_absolute_url()


class GoalSessionsMixin(OwnSessionsMixin):
    """For the routes under /goals/<goal_pk>/sessions/: the goal is looked up
    through its owner as soon as the login check has passed, before any form
    handling, so another user's goal is a 404 (never a page of form errors),
    exactly like a missing one."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.goal = self.get_goal()
        return super().dispatch(request, *args, **kwargs)

    def get_goal(self):
        goals = Goal.objects.owned_by(self.request.user)
        return get_object_or_404(goals, pk=self.kwargs["goal_pk"])

    def get_queryset(self):
        return super().get_queryset().filter(goal=self.goal)

    def get_context_data(self, **kwargs):
        return super().get_context_data(goal=self.goal, **kwargs)


class SessionCreateView(GoalSessionsMixin, SuccessMessageMixin, CreateView):
    form_class = LearningSessionForm
    template_name = "learning_sessions/session_form.html"
    success_message = "Session added."

    def get_form_kwargs(self):
        # The goal is the one from the URL (already owner-checked), set before
        # validation, so nothing posted can choose it.
        return {
            **super().get_form_kwargs(),
            "instance": LearningSession(goal=self.goal),
        }


class SessionUpdateView(OwnSessionsMixin, SuccessMessageMixin, UpdateView):
    form_class = LearningSessionForm
    template_name = "learning_sessions/session_form.html"
    success_message = "Session updated."

    def get_context_data(self, **kwargs):
        return super().get_context_data(goal=self.object.goal, **kwargs)
