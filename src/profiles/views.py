from django.views.generic import DetailView

from profiles.models import Profile


class ProfileDetailView(DetailView):
    model = Profile
    template_name = "profiles/profile_detail.html"
