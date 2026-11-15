from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from core.exercise_logging import log_exercise
from core.models_exercise import ExerciseLog


@pytest.fixture
def user(db):
    return User.objects.create_user("firebase_abc123", password="x")


def test_a_logged_exercise_remembers_the_weight(user):
    log = log_exercise(user, {"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight_kg": Decimal("61.235")})
    log.refresh_from_db()
    assert log.weight_kg == Decimal("61.235")


def test_bodyweight_exercises_have_no_weight(user):
    log = log_exercise(user, {"exercise_type": "push_ups", "sets": 3, "reps": 10})
    log.refresh_from_db()
    assert log.weight_kg is None


def test_the_weight_does_not_change_the_points_earned(user):
    plain = log_exercise(user, {"exercise_type": "back_squat", "sets": 3, "reps": 8})
    heavy = log_exercise(user, {"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight_kg": Decimal("200")})
    assert (plain.strength, plain.dexterity, plain.endurance) == (
        heavy.strength, heavy.dexterity, heavy.endurance,
    )


def test_the_new_exercises_can_be_logged_like_the_old_ones(user):
    log = log_exercise(user, {"exercise_type": "cycling", "distance_miles": Decimal("10.00")})
    assert ExerciseLog.objects.get(pk=log.pk).exercise_type == "cycling"
    assert log.endurance > 0


def test_a_new_exercise_shows_its_readable_name(user):
    log = log_exercise(user, {"exercise_type": "worlds_greatest_stretch", "sets": 1, "reps": 5})
    assert log.get_exercise_type_display() == "World's Greatest Stretch"
