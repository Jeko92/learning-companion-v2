from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from goals.models import Goal
from learning_sessions.models import LearningSession


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard.html"
    http_method_names = ("get", "head")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = Goal.objects.owned_by(self.request.user).status_counts()
        context["status_rows"] = [
            (value, label, counts[value]) for value, label in Goal.Status.choices
        ]
        # Summed from the counts, so the total needs no second query.
        context["total_goals"] = sum(counts.values())
        sessions = LearningSession.objects.owned_by(self.request.user)
        context["tag_rows"] = sessions.minutes_per_tag()
        return context
