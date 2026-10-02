from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from profiles.models import Profile


class OwnProfileMixin(LoginRequiredMixin):
    """Only ever finds the logged-in user's own profile: another user's pk is
    a 404, exactly like a pk that doesn't exist, so it reveals nothing."""

    model = Profile

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)


class ProfileDetailView(OwnProfileMixin, DetailView):
    template_name = "profiles/profile_detail.html"
