from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView

from goals.models import Goal
from resources.forms import ResourceForm
from resources.models import Resource


class OwnResourcesMixin(LoginRequiredMixin):
    """Only ever the logged-in user's own resources, via
    Resource.objects.owned_by.

    The same rules as goals.views.OwnGoalsMixin: list it *first* in a view's
    bases and never set `model` on a resource view, or Django's own
    get_queryset() wins and could serve every user's resources."""

    def get_queryset(self):
        return Resource.objects.owned_by(self.request.user).select_related("goal")


class GoalResourcesMixin(OwnResourcesMixin):
    """For the routes under /goals/<goal_pk>/resources/: the goal is looked up
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


class ResourceCreateView(GoalResourcesMixin, CreateView):
    form_class = ResourceForm
    template_name = "resources/resource_form.html"
