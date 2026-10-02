from django.urls import path

from profiles import views

app_name = "profiles"

urlpatterns = [
    path("", views.MyProfileView.as_view(), name="mine"),
    path("<int:pk>/", views.ProfileDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ProfileUpdateView.as_view(), name="edit"),
]
