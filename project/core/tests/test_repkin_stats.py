from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.exercise_logging import log_exercise
from core.models_repkin import Repkin

START = {"strength": 50, "dexterity": 50, "endurance": 50}
NO_PROGRESS = {"strength": 0, "dexterity": 0, "endurance": 0}


def flat(exercise_type, sets=None, reps=None, duration_seconds=None, distance_miles=None):
    return {
        "exercise_type": exercise_type,
        "sets": sets,
        "reps": reps,
        "duration_seconds": duration_seconds,
        "distance_miles": distance_miles,
    }


@pytest.fixture
def user(db):
    return User.objects.create_user("lifter", password="pw12345!")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("runner", password="pw12345!")


@pytest.fixture
def repkin(user):
    return Repkin.objects.create(owner=user, mood="content", color="green")


@pytest.fixture
def other_repkin(other_user):
    return Repkin.objects.create(owner=other_user, mood="content", color="green")


# The stats are real, saved, per-Repkin fields vvvvvvvvvvvvvvvvvvvvvvvvvv

def test_new_repkin_starts_with_default_stats(repkin):
    assert repkin.stats == START
    assert repkin.progress_stats == NO_PROGRESS


def test_stats_are_saved_to_the_database(repkin):
    repkin.set_stats({"strength": 70, "dexterity": 55, "endurance": 60})
    repkin.save()

    fresh = Repkin.objects.get(pk=repkin.pk)
    assert fresh.stats == {"strength": 70, "dexterity": 55, "endurance": 60}


def test_changing_one_repkin_does_not_change_another(repkin, other_repkin):
    repkin.update_progress({"strength": 24, "dexterity": 0, "endurance": 6})
    repkin.save()

    other_repkin.refresh_from_db()
    assert other_repkin.progress_stats == NO_PROGRESS


# Brandon's methods still work the same way vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_update_progress_adds_to_progress_only(repkin):
    repkin.update_progress({"strength": 10, "dexterity": 5, "endurance": 0})
    repkin.update_progress({"strength": 4, "dexterity": 0, "endurance": 6})

    assert repkin.progress_stats == {"strength": 14, "dexterity": 5, "endurance": 6}
    assert repkin.stats == START


def test_add_prog_to_stats_moves_progress_and_resets_it(repkin):
    repkin.set_progress({"strength": 14, "dexterity": 5, "endurance": 6})
    repkin.add_prog_to_stats()

    assert repkin.stats == {"strength": 64, "dexterity": 55, "endurance": 56}
    assert repkin.progress_stats == NO_PROGRESS


def test_update_progress_with_missing_stat_raises_error(repkin):
    with pytest.raises(KeyError):
        repkin.update_progress({"strength": 10})


# Logging a workout reaches the Repkin vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_logging_exercise_adds_to_users_repkin_progress(user, repkin):
    log_exercise(user, flat("push_ups", sets=3, reps=10))

    repkin.refresh_from_db()
    assert repkin.progress_stats == {"strength": 24, "dexterity": 0, "endurance": 6}
    assert repkin.stats == START


def test_several_workouts_add_up(user, repkin):
    log_exercise(user, flat("push_ups", sets=3, reps=10))
    log_exercise(user, flat("running", distance_miles=Decimal("1.00")))

    repkin.refresh_from_db()
    assert repkin.progress_stats == {"strength": 24, "dexterity": 12, "endurance": 34}


def test_logging_only_affects_that_users_repkin(user, repkin, other_repkin):
    log_exercise(user, flat("curls", sets=2, reps=10))

    other_repkin.refresh_from_db()
    assert other_repkin.progress_stats == NO_PROGRESS


def test_logging_creates_repkin_if_user_has_none(user):
    log_exercise(user, flat("planks", duration_seconds=60))

    repkin = Repkin.objects.get(owner=user)
    assert repkin.progress_stats == {"strength": 12, "dexterity": 0, "endurance": 18}


def test_submitting_the_exercise_form_updates_the_repkin(client, user, repkin):
    client.force_login(user)

    response = client.post(
        reverse("core:submit_exercise"),
        {"exercise_type": "push_ups", "sets": 3, "reps": 10},
    )

    assert response.status_code == 200
    repkin.refresh_from_db()
    assert repkin.progress_stats == {"strength": 24, "dexterity": 0, "endurance": 6}
