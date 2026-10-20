from django.urls import path
from . import views
from .views_exercise import submit_exercise

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("logout/", views.logout_view, name="logout"),
    path("create-account/", views.account_creation, name="account_creation"),
    path("repkin/setup/", views.repkin_setup, name="repkin_setup"),
    path("exercises/submit/", submit_exercise, name="submit_exercise"),
]
