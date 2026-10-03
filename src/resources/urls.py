from django.urls import path

from resources import views

app_name = "resources"

# Shallow nesting, as for sessions: attaching needs the goal, so it sits under
# it; the routes for one resource take only the resource's pk.
urlpatterns = [
    path(
        "goals/<int:goal_pk>/resources/new/",
        views.ResourceCreateView.as_view(),
        name="create",
    ),
]
