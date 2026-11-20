from django.urls import path
from . import views
from .views_exercise import submit_exercise
from .views_message import repkin_message

app_name = "core"

urlpatterns = [
    # This address lets Django check Firebase's sign-in proof and remember the user.
    path("auth/firebase/session/", views.firebase_session, name="firebase_session"),
    # Route practice-data reads and writes through the authenticated Django session.
    path("practice-data/", views.practice_data, name="practice_data"),
    # Send XP-stat requests to the view that reads and saves the signed-in user's stats.
    path("xp-stats/", views.xp_stats, name="xp_stats"),
    path("", views.home, name="home"),
    path("logout/", views.logout_view, name="logout"),
    path("create-account/", views.account_creation, name="account_creation"),
    path("repkin/setup/", views.repkin_setup, name="repkin_setup"),
    path("exercises/submit/", submit_exercise, name="submit_exercise"),
    path("repkin/message/", repkin_message, name="repkin_message"),
    path("locker-room/", views.locker_room, name="locker_room"),
    path("profile/", views.profile_data, name="profile_data"),
    path("user/name/", views.update_user_name, name="update_user_name"),
    path("repkin/name/", views.update_repkin_name, name="update_repkin_name"),
    # Save the selected arm and leg sprite levels.
    path("repkin/sprite/", views.update_repkin_sprite, name="update_repkin_sprite"),
]
