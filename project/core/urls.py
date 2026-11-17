from django.urls import path
from . import views, views_workout
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
    path("workouts/", views_workout.workout_logging, name="workout_logging"),
    path("workouts/log/", views_workout.workout_log, name="workout_log"),
    path("workouts/catalog/", views_workout.workout_catalog, name="workout_catalog"),
    path("workouts/presets/", views_workout.preset_list, name="workout_presets"),
    path("workouts/presets/save/", views_workout.preset_save, name="workout_preset_save"),
    path("workouts/presets/<int:pk>/", views_workout.preset_detail, name="workout_preset_detail"),
    path("workouts/presets/<int:pk>/delete/", views_workout.preset_delete, name="workout_preset_delete"),
]
