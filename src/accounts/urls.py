from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("login/", views.LogInView.as_view(), name="login"),
    path("logout/", views.LogOutView.as_view(), name="logout"),
]
