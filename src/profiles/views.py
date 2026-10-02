from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from profiles.models import Profile


class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "profiles/profile_detail.html"
