from django.urls import path

from goals import views

app_name = "goals"

urlpatterns = [
    path("", views.GoalListView.as_view(), name="list"),
    path("new/", views.GoalCreateView.as_view(), name="create"),
    path("<int:pk>/", views.GoalDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.GoalUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.GoalDeleteView.as_view(), name="delete"),
    path("<int:pk>/summary/", views.GoalSummaryView.as_view(), name="summary"),
    path("<int:pk>/next-steps/", views.GoalNextStepsView.as_view(), name="next_steps"),
    path("<int:pk>/move/", views.GoalMoveView.as_view(), name="move"),
]
