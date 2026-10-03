from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, DeleteView

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

    def get_success_url(self):
        # Resources have no page of their own: back to the goal after a change.
        return self.object.goal.get_absolute_url()


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


class ResourceCreateView(GoalResourcesMixin, SuccessMessageMixin, CreateView):
    form_class = ResourceForm
    template_name = "resources/resource_form.html"
    success_message = "Resource added."

    def get_form_kwargs(self):
        # The goal is the one from the URL (already owner-checked), set before
        # validation, so nothing posted can choose it.
        return {**super().get_form_kwargs(), "instance": Resource(goal=self.goal)}

    def form_valid(self, form):
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            # Another request attached the same URL after the form validated.
            # Ask the model which constraint now fails, so the error is its own
            # message; anything other than a duplicate is re-raised.
            try:
                form.instance.validate_constraints()
            except ValidationError as error:
                form.add_error(None, error)
                return self.form_invalid(form)
            raise


class ResourceDeleteView(OwnResourcesMixin, SuccessMessageMixin, DeleteView):
    template_name = "resources/resource_confirm_delete.html"

    def get_success_message(self, cleaned_data):
        # A fixed text: DeleteView's cleaned_data is empty.
        return "Resource deleted."
