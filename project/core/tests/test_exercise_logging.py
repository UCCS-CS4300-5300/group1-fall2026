from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from core import exercise_logging
from core.exercise_logging import log_exercise, send_stats_to_repkin
from core.exercises import EXERCISES, REPS, DURATION, DISTANCE, calculate_stats
from core.forms_exercise import ExerciseInputForm
from core.models_exercise import ExerciseLog
from core.models_repkin import Repkin


def flat(exercise_type, sets=None, reps=None, duration_seconds=None, distance_miles=None):
    """Same shape as the data the exercise view sends to log_exercise."""
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


# The exercise catalog vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_every_split_adds_up_to_100():
    for name, info in EXERCISES.items():
        assert sum(info["split"].values()) == 100, name


def test_catalog_matches_the_form_choices():
    form_choices = {value for value, _ in ExerciseInputForm.EXERCISE_CHOICES}
    assert set(EXERCISES) == form_choices


def test_catalog_input_types_match_the_form():
    by_type = {
        REPS: ExerciseInputForm.REPETITION_EXERCISES,
        DURATION: ExerciseInputForm.DURATION_EXERCISES,
        DISTANCE: ExerciseInputForm.DISTANCE_EXERCISES,
    }
    for name, info in EXERCISES.items():
        assert name in by_type[info["input_type"]], name


# Stat calculation vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_push_ups_stats():
    stats = calculate_stats("push_ups", flat("push_ups", sets=3, reps=10))
    assert stats == {"strength": 24, "dexterity": 0, "endurance": 6}


def test_running_stats_with_decimal_miles():
    stats = calculate_stats("running", flat("running", distance_miles=Decimal("2.50")))
    assert stats == {"strength": 0, "dexterity": 30, "endurance": 70}


def test_plank_stats():
    stats = calculate_stats("planks", flat("planks", duration_seconds=60))
    assert stats == {"strength": 12, "dexterity": 0, "endurance": 18}


def test_single_category_exercise_only_raises_that_stat():
    stats = calculate_stats("curls", flat("curls", sets=2, reps=10))
    assert stats == {"strength": 20, "dexterity": 0, "endurance": 0}


# Saving the exercise history vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_log_exercise_saves_history_entry(user):
    log = log_exercise(user, flat("push_ups", sets=3, reps=10))

    saved = ExerciseLog.objects.get(pk=log.pk)
    assert saved.user == user
    assert saved.exercise_type == "push_ups"
    assert saved.sets == 3
    assert saved.reps == 10
    assert saved.duration_seconds is None
    assert saved.distance_miles is None


def test_log_exercise_saves_earned_stats(user):
    log = log_exercise(user, flat("running", distance_miles=Decimal("2.50")))
    saved = ExerciseLog.objects.get(pk=log.pk)
    assert (saved.strength, saved.dexterity, saved.endurance) == (0, 30, 70)
    assert saved.distance_miles == Decimal("2.50")


def test_log_exercise_records_a_timestamp(user):
    log = log_exercise(user, flat("planks", duration_seconds=60))
    assert log.logged_at is not None


def test_history_is_newest_first(user):
    older = log_exercise(user, flat("squats", sets=3, reps=12))
    newer = log_exercise(user, flat("walking", distance_miles=Decimal("1.00")))
    ExerciseLog.objects.filter(pk=older.pk).update(
        logged_at=newer.logged_at - timedelta(hours=1)
    )

    assert list(user.exercise_logs.all()) == [newer, older]


def test_each_user_only_has_their_own_history(user, other_user):
    log_exercise(user, flat("curls", sets=3, reps=8))
    log_exercise(other_user, flat("jogging", distance_miles=Decimal("3.00")))

    assert [log.exercise_type for log in user.exercise_logs.all()] == ["curls"]
    assert [log.exercise_type for log in other_user.exercise_logs.all()] == ["jogging"]


def test_deleting_user_deletes_their_history(user):
    log_exercise(user, flat("lunges", sets=2, reps=12))
    user.delete()
    assert ExerciseLog.objects.count() == 0



def test_stats_and_timestamp_are_sent_to_repkin(user, monkeypatch):
    calls = []
    monkeypatch.setattr(
        exercise_logging,
        "send_stats_to_repkin",
        lambda u, stats, timestamp: calls.append((u, stats, timestamp)),
    )

    log = log_exercise(user, flat("push_ups", sets=3, reps=10))

    assert calls == [
        (user, {"strength": 24, "dexterity": 0, "endurance": 6}, log.logged_at)
    ]


def test_nothing_is_saved_if_sending_stats_fails(user, monkeypatch):
    def broken(*args):
        raise RuntimeError("repkin code crashed")

    monkeypatch.setattr(exercise_logging, "send_stats_to_repkin", broken)

    with pytest.raises(RuntimeError):
        log_exercise(user, flat("push_ups", sets=3, reps=10))

    assert ExerciseLog.objects.count() == 0

def test_repkin_stats_sent(user):
    stats = {"strength": 10, "dexterity":5, "endurance":6}
    repkin = Repkin.objects.create(owner=user, mood="happy", color="violet")
    # repkin.set_progress({"strength":0, "dexterity":0, "endurance":0})
    send_stats_to_repkin(user, stats, timestamp=0)

    assert repkin.progress_stats == {"strength": 10, "dexterity":5, "endurance":6}
