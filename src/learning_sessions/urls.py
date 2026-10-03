from django.urls import path

from learning_sessions import views

app_name = "learning_sessions"

# Shallow nesting: the routes that need the goal (list, create) sit under it,
# the ones for one session (edit, delete) take only the session's pk.
urlpatterns = [
    path("goals/<int:goal_pk>/sessions/", views.SessionListView.as_view(), name="list"),
    path(
        "goals/<int:goal_pk>/sessions/new/",
        views.SessionCreateView.as_view(),
        name="create",
    ),
    path("sessions/<int:pk>/edit/", views.SessionUpdateView.as_view(), name="edit"),
    path("sessions/<int:pk>/delete/", views.SessionDeleteView.as_view(), name="delete"),
]
