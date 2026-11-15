import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from core.models_workout import Workout, WorkoutExercise


@pytest.fixture
def user(db):
    return User.objects.create_user("firebase_abc123", password="x")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("firebase_zzz999", password="x")


@pytest.fixture
def workout(user):
    return Workout.objects.create(user=user, name="Leg Day")


def add(workout, section="working_sets", position=1, **fields):
    fields.setdefault("exercise_type", "push_ups")
    return WorkoutExercise.objects.create(workout=workout, section=section, position=position, **fields)


# --- names -------------------------------------------------------------------

def test_a_user_cannot_have_two_workouts_with_the_same_name(user, workout):
    with pytest.raises(IntegrityError), transaction.atomic():
        Workout.objects.create(user=user, name="Leg Day")


def test_names_that_differ_only_in_capitals_count_as_the_same(user, workout):
    with pytest.raises(IntegrityError), transaction.atomic():
        Workout.objects.create(user=user, name="leg DAY")


def test_two_users_may_use_the_same_name(other_user, workout):
    assert Workout.objects.create(user=other_user, name="Leg Day").pk


def test_a_name_can_be_reused_after_the_workout_is_deleted(user, workout):
    workout.delete()
    assert Workout.objects.create(user=user, name="Leg Day").pk


# --- positions -----------------------------------------------------------------

def test_two_exercises_cannot_share_a_position_in_one_section(workout):
    add(workout, position=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        add(workout, position=1)


def test_the_same_position_is_fine_in_different_sections(workout):
    add(workout, section="warmup_sets", position=1)
    add(workout, section="working_sets", position=1)
    assert workout.exercises.count() == 2


@pytest.mark.parametrize("position", [1, 5])
def test_positions_one_to_five_are_allowed(workout, position):
    assert add(workout, position=position).pk


@pytest.mark.parametrize("position", [0, 6, 100])
def test_positions_outside_one_to_five_are_rejected_by_the_database(workout, position):
    with pytest.raises(IntegrityError), transaction.atomic():
        add(workout, position=position)


# --- ownership and clean-up ------------------------------------------------------

def test_deleting_a_workout_deletes_its_exercises(workout):
    add(workout, position=1)
    add(workout, position=2)
    workout.delete()
    assert WorkoutExercise.objects.count() == 0


def test_deleting_a_user_deletes_their_workouts_and_exercises(user, workout):
    add(workout)
    user.delete()
    assert Workout.objects.count() == 0
    assert WorkoutExercise.objects.count() == 0


def test_workouts_belong_to_their_user(user, other_user, workout):
    assert list(user.workouts.all()) == [workout]
    assert list(other_user.workouts.all()) == []


def test_the_most_recently_updated_workout_comes_first(user, workout):
    newer = Workout.objects.create(user=user, name="Arm Day")
    assert list(Workout.objects.filter(user=user)) == [newer, workout]
    workout.name = "Leg Day!"
    workout.save()
    assert list(Workout.objects.filter(user=user)) == [workout, newer]


def test_how_they_read_in_the_admin(workout):
    exercise = add(workout, exercise_type="back_squat", section="working_sets", position=2)
    assert "Leg Day" in str(workout)
    assert str(exercise) == "Leg Day: Back Squat (working_sets #2)"


def test_the_measurements_default_to_empty(workout):
    exercise = add(workout)
    assert (exercise.sets, exercise.reps, exercise.duration_seconds) == (None, None, None)
    assert (exercise.distance_miles, exercise.weight_kg) == (None, None)
