from django.urls import path
from . import views
app_name = "core"
urlpatterns = [
    # This address lets Django check Firebase's sign-in proof and remember the user.
    path("auth/firebase/session/", views.firebase_session, name="firebase_session"),
    path("", views.home, name="home"),
    path("logout/", views.logout_view, name="logout"),
]
