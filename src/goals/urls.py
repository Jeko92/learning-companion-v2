from django.urls import path

from goals import views

app_name = "goals"

urlpatterns = [
    path("", views.GoalListView.as_view(), name="list"),
    path("new/", views.GoalCreateView.as_view(), name="create"),
    path("<int:pk>/", views.GoalDetailView.as_view(), name="detail"),
]
