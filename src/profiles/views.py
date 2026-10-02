from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView, RedirectView, UpdateView

from profiles.forms import ProfileForm
from profiles.models import Profile


class OwnProfileMixin(LoginRequiredMixin):
    """Only ever finds the logged-in user's own profile: another user's pk is
    a 404, exactly like a pk that doesn't exist, so it reveals nothing."""

    model = Profile

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)


class ProfileDetailView(OwnProfileMixin, DetailView):
    template_name = "profiles/profile_detail.html"


class MyProfileView(LoginRequiredMixin, RedirectView):
    """/profile/: your own profile, so its id never has to be known."""

    def get_redirect_url(self, *args, **kwargs):
        # get_or_create: users loaded from fixtures have no profile (CLAUDE.md).
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return reverse("profiles:detail", args=[profile.pk])


class ProfileUpdateView(OwnProfileMixin, UpdateView):
    form_class = ProfileForm
    template_name = "profiles/profile_form.html"
