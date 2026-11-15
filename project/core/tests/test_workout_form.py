from decimal import Decimal

import pytest

from core.forms_workout import (
    MAX_DISTANCE_MILES, MAX_DURATION_SECONDS, MAX_REPS, MAX_SETS, MAX_WEIGHT_KG, WorkoutItemForm,
)
from core.units import IMPERIAL, SI

WORKING = "working_sets"


def check(data, section=WORKING, system=IMPERIAL):
    form = WorkoutItemForm(data, section=section, unit_system=system)
    form.is_valid()
    return form


def messages(form, field):
    return form.errors.get(field, [])


# --- what a good item looks like -----------------------------------------------------

def test_a_weighted_lift_in_pounds_is_stored_in_kilograms():
    form = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": 135})
    assert form.is_valid()
    assert form.cleaned_data["weight_kg"] == Decimal("61.235")
    assert (form.cleaned_data["sets"], form.cleaned_data["reps"]) == (3, 8)


def test_a_weighted_lift_in_kilograms_stays_in_kilograms():
    form = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": 60}, system=SI)
    assert form.cleaned_data["weight_kg"] == Decimal("60.000")


def test_a_distance_in_kilometres_is_stored_in_miles():
    form = check({"exercise_type": "cycling", "distance": 10}, system=SI)
    assert form.cleaned_data["distance_miles"] == Decimal("6.214")


def test_a_distance_in_miles_stays_in_miles():
    form = check({"exercise_type": "running", "distance": "3.5"})
    assert form.cleaned_data["distance_miles"] == Decimal("3.500")


def test_a_stretch_needs_only_its_duration():
    form = check({"exercise_type": "hamstring_stretch", "duration_seconds": 45}, section="warmup_stretch")
    assert form.is_valid()
    assert form.cleaned_data["duration_seconds"] == 45


def test_numbers_may_arrive_as_text_like_a_form_sends_them():
    form = check({"exercise_type": "back_squat", "sets": "3", "reps": "8", "weight": "135.5"})
    assert form.is_valid()


def test_a_weighted_exercise_may_be_done_without_weight():
    for blank in (None, "", "   "):
        form = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": blank})
        assert form.is_valid()
        assert form.cleaned_data["weight_kg"] is None


def test_leaving_the_weight_out_entirely_is_fine():
    form = check({"exercise_type": "back_squat", "sets": 3, "reps": 8})
    assert form.is_valid() and form.cleaned_data["weight_kg"] is None


# --- measurements that are required --------------------------------------------------

@pytest.mark.parametrize(
    "data, missing",
    [
        ({"exercise_type": "push_ups", "reps": 10}, ["sets"]),
        ({"exercise_type": "push_ups", "sets": 3}, ["reps"]),
        ({"exercise_type": "push_ups"}, ["sets", "reps"]),
        ({"exercise_type": "planks"}, ["duration_seconds"]),
        ({"exercise_type": "running"}, ["distance"]),
    ],
)
def test_each_kind_of_exercise_needs_its_own_measurements(data, missing):
    form = check(data)
    assert not form.is_valid()
    for field in missing:
        assert any("required" in message for message in messages(form, field)), field


def test_measurements_that_do_not_belong_to_the_exercise_are_dropped():
    form = check({"exercise_type": "planks", "duration_seconds": 60, "sets": 3, "reps": 10, "distance": 5})
    assert form.is_valid()
    assert (form.cleaned_data["sets"], form.cleaned_data["reps"], form.cleaned_data["distance_miles"]) == (None, None, None)


# --- weights ---------------------------------------------------------------------------

def test_an_exercise_that_is_not_weighted_refuses_a_weight():
    form = check({"exercise_type": "push_ups", "sets": 3, "reps": 10, "weight": 20})
    assert "doesn't use a weight" in messages(form, "weight")[0]


@pytest.mark.parametrize("bad", [0, "0", -5, "abc", "12.345", "nan", "inf", "-inf", "1,5"])
def test_nonsense_weights_are_rejected(bad):
    form = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": bad})
    assert not form.is_valid() and messages(form, "weight")


def test_a_number_written_with_an_exponent_is_read_as_that_number():
    """Browsers' number boxes allow '1e2', which just means 100."""
    form = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": "1e2"}, system=SI)
    assert form.is_valid()
    assert form.cleaned_data["weight_kg"] == Decimal("100.000")


def test_a_box_holding_only_spaces_counts_as_empty_for_every_field():
    form = check({"exercise_type": "planks", "duration_seconds": 60, "sets": "  ", "distance": " "})
    assert form.is_valid()
    assert check({"exercise_type": "planks", "duration_seconds": "   "}).errors["duration_seconds"]


def test_a_weight_too_heavy_to_be_right_is_rejected():
    heavy = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": 5000})   # lb: about 2268 kg
    assert "too heavy" in messages(heavy, "weight")[0]
    limit = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": MAX_WEIGHT_KG}, system=SI)
    assert limit.is_valid()
    over = check({"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": "1000.01"}, system=SI)
    assert not over.is_valid()


# --- distances ---------------------------------------------------------------------------

def test_a_distance_too_far_to_be_right_is_rejected():
    far = check({"exercise_type": "cycling", "distance": 900}, system=SI)     # about 559 miles
    assert "too far" in messages(far, "distance")[0]
    limit = check({"exercise_type": "cycling", "distance": MAX_DISTANCE_MILES})
    assert limit.is_valid()


@pytest.mark.parametrize("bad", [0, "0", -1, "far"])
def test_nonsense_distances_are_rejected(bad):
    assert not check({"exercise_type": "running", "distance": bad}).is_valid()


# --- limits -----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "data",
    [
        {"exercise_type": "push_ups", "sets": 0, "reps": 10},
        {"exercise_type": "push_ups", "sets": MAX_SETS + 1, "reps": 10},
        {"exercise_type": "push_ups", "sets": 3, "reps": 0},
        {"exercise_type": "push_ups", "sets": 3, "reps": MAX_REPS + 1},
        {"exercise_type": "push_ups", "sets": 3, "reps": 8.5},
        {"exercise_type": "push_ups", "sets": True, "reps": 10},
        {"exercise_type": "planks", "duration_seconds": 0},
        {"exercise_type": "planks", "duration_seconds": MAX_DURATION_SECONDS + 1},
    ],
)
def test_out_of_range_numbers_are_rejected(data):
    assert not check(data).is_valid()


def test_the_limits_themselves_are_allowed():
    assert check({"exercise_type": "push_ups", "sets": MAX_SETS, "reps": MAX_REPS}).is_valid()
    assert check({"exercise_type": "planks", "duration_seconds": MAX_DURATION_SECONDS}).is_valid()


# --- the exercise and its section --------------------------------------------------------------

def test_an_exercise_can_only_go_in_a_section_it_is_tagged_for():
    form = check({"exercise_type": "hamstring_stretch", "duration_seconds": 30}, section=WORKING)
    assert "can't be added to" in messages(form, "exercise_type")[0]
    assert "Working sets/exercises" in messages(form, "exercise_type")[0]


def test_an_exercise_that_does_not_exist_is_rejected():
    assert messages(check({"exercise_type": "moonwalk", "sets": 1, "reps": 1}), "exercise_type")


def test_a_missing_exercise_is_rejected():
    assert messages(check({"sets": 1, "reps": 1}), "exercise_type")
