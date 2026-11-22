from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from core import workout_presets
from core.exercises import EXERCISES, MAX_PER_SECTION, SECTIONS
from core.models_workout import MAX_NAME_LENGTH, Workout, WorkoutExercise
from core.workout_presets import (
    NameTaken, PresetNotFound, PresetValidationError, TooManyPresets, catalog_payload,
    clean_name, list_presets, save_preset, serialize_preset, validate_payload,
)


@pytest.fixture
def user(db):
    return User.objects.create_user("firebase_abc123", password="x")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("firebase_zzz999", password="x")


def good(**changes):
    payload = {
        "name": "Leg Day",
        "unit_system": "imperial",
        "sections": {
            "warmup_stretch": [{"exercise_type": "hamstring_stretch", "duration_seconds": 45}],
            "working_sets": [
                {"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": 135},
                {"exercise_type": "cycling", "distance": 5},
            ],
            "cooldown_stretch": [{"exercise_type": "childs_pose", "duration_seconds": 60}],
        },
    }
    payload.update(changes)
    return payload


def problems(payload):
    with pytest.raises(PresetValidationError) as info:
        validate_payload(payload)
    return info.value.errors


def one_error(payload, where):
    found = [error for error in problems(payload) if error["where"] == where]
    assert found, f"no {where} error in {problems(payload)}"
    return found[0]


# --- names ------------------------------------------------------------------------------------

def test_names_are_tidied_into_one_line():
    assert clean_name("  Leg \t  Day\n") == "Leg Day"


@pytest.mark.parametrize("bad", [None, "", "   ", "\n\t", 42, ["Leg Day"]])
def test_a_missing_or_blank_name_is_rejected(bad):
    assert "name" in one_error(good(name=bad), "name")["message"].lower()


def test_names_up_to_the_limit_are_fine_and_longer_ones_are_not():
    assert validate_payload(good(name="x" * MAX_NAME_LENGTH))["name"] == "x" * MAX_NAME_LENGTH
    assert str(MAX_NAME_LENGTH) in one_error(good(name="x" * (MAX_NAME_LENGTH + 1)), "name")["message"]


def test_the_name_is_measured_after_tidying():
    padded = "  " + "x" * MAX_NAME_LENGTH + "   "
    assert validate_payload(good(name=padded))["name"] == "x" * MAX_NAME_LENGTH


# --- the shape of the request --------------------------------------------------------------------

@pytest.mark.parametrize("not_a_preset", [None, [], "Leg Day", 5])
def test_the_payload_must_be_an_object(not_a_preset):
    assert problems(not_a_preset)[0]["where"] == "preset"


@pytest.mark.parametrize("bad", [None, "", "martian", "IMPERIAL", 1])
def test_the_unit_system_must_be_imperial_or_si(bad):
    assert "unit_system" in one_error(good(unit_system=bad), "preset")["message"]


@pytest.mark.parametrize("system", ["imperial", "si"])
def test_both_unit_systems_are_accepted(system):
    assert validate_payload(good(unit_system=system))["unit_system"] == system


@pytest.mark.parametrize("bad", ["12", 1.5, True, [1]])
def test_an_id_must_be_a_whole_number(bad):
    assert "id must be" in one_error(good(id=bad), "preset")["message"]


@pytest.mark.parametrize("bad", [None, [], "working_sets"])
def test_sections_must_be_an_object(bad):
    assert "sections must be" in one_error(good(sections=bad), "preset")["message"]


def test_an_unknown_section_is_reported_by_name():
    sections = good()["sections"] | {"bonus_round": [{"exercise_type": "push_ups", "sets": 1, "reps": 1}]}
    error = one_error(good(sections=sections), "section")
    assert error["section"] == "bonus_round"


def test_a_section_must_be_a_list():
    error = one_error(good(sections={"working_sets": {"exercise_type": "push_ups"}}), "section")
    assert error["section"] == "working_sets"


def test_each_exercise_must_be_an_object():
    error = one_error(good(sections={"working_sets": ["push_ups"]}), "item")
    assert (error["section"], error["index"]) == ("working_sets", 0)


def test_a_section_holds_at_most_five_exercises():
    five = [{"exercise_type": "push_ups", "sets": 3, "reps": 10}] * MAX_PER_SECTION
    assert validate_payload(good(sections={"working_sets": five}))
    error = one_error(good(sections={"working_sets": five + five[:1]}), "section")
    assert error["section"] == "working_sets" and "at most 5" in error["message"]


def test_the_limit_applies_to_each_section_separately():
    five = [{"exercise_type": "push_ups", "sets": 3, "reps": 10}] * MAX_PER_SECTION
    cleaned = validate_payload(good(sections={"warmup_sets": five, "working_sets": five}))
    assert len(cleaned["items"]["warmup_sets"]) == len(cleaned["items"]["working_sets"]) == 5


def test_a_workout_needs_at_least_one_exercise():
    for empty in ({}, {"working_sets": []}, {key: [] for key in SECTIONS}):
        assert "at least one exercise" in one_error(good(sections=empty), "preset")["message"]


# --- problems are reported where they happened -----------------------------------------------------------

def test_a_bad_exercise_is_reported_with_its_section_position_and_field():
    sections = {"working_sets": [
        {"exercise_type": "push_ups", "sets": 3, "reps": 10},
        {"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": "abc"},
    ]}
    error = one_error(good(sections=sections), "item")
    assert (error["section"], error["index"], error["field"]) == ("working_sets", 1, "weight")


def test_every_problem_is_reported_at_once_not_one_at_a_time():
    sections = {
        "working_sets": [{"exercise_type": "push_ups", "sets": 3}, {"exercise_type": "moonwalk"}],
        "cooldown_stretch": [{"exercise_type": "back_squat", "sets": 1, "reps": 1}],
    }
    errors = problems(good(name="", sections=sections))
    places = {(e["where"], e.get("section"), e.get("index")) for e in errors}
    assert ("name", None, None) in places
    assert ("item", "working_sets", 0) in places
    assert ("item", "working_sets", 1) in places
    assert ("item", "cooldown_stretch", 0) in places


def test_exercises_are_not_checked_when_the_unit_system_is_unknown():
    errors = problems(good(unit_system="martian"))
    assert [e["where"] for e in errors] == ["preset"]


# --- what a valid request turns into ------------------------------------------------------------------------

def test_a_valid_request_is_cleaned_into_stored_units():
    cleaned = validate_payload(good())
    squat = cleaned["items"]["working_sets"][0]
    ride = cleaned["items"]["working_sets"][1]
    assert squat["weight_kg"] == Decimal("61.235")
    assert ride["distance_miles"] == Decimal("5.000")
    assert cleaned["items"]["warmup_sets"] == []


# --- saving ------------------------------------------------------------------------------------------------------

def test_saving_creates_the_preset_and_numbers_the_exercises_in_each_section(user):
    workout, created = save_preset(user, good())
    assert created is True and workout.user == user and workout.name == "Leg Day"
    rows = list(workout.exercises.order_by("section", "position"))
    assert [(r.section, r.position, r.exercise_type) for r in rows] == [
        ("cooldown_stretch", 1, "childs_pose"),
        ("warmup_stretch", 1, "hamstring_stretch"),
        ("working_sets", 1, "back_squat"),
        ("working_sets", 2, "cycling"),
    ]


def test_measurements_are_saved_in_stored_units(user):
    workout, _ = save_preset(user, good())
    squat = workout.exercises.get(exercise_type="back_squat")
    ride = workout.exercises.get(exercise_type="cycling")
    assert (squat.sets, squat.reps, squat.weight_kg) == (3, 8, Decimal("61.235"))
    assert (ride.distance_miles, ride.sets, ride.weight_kg) == (Decimal("5.000"), None, None)


def test_metric_input_is_converted_before_saving(user):
    payload = good(unit_system="si", sections={"working_sets": [
        {"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": 60},
        {"exercise_type": "cycling", "distance": 10},
    ]})
    workout, _ = save_preset(user, payload)
    assert workout.exercises.get(exercise_type="back_squat").weight_kg == Decimal("60.000")
    assert workout.exercises.get(exercise_type="cycling").distance_miles == Decimal("6.214")


def test_an_invalid_preset_saves_nothing(user):
    with pytest.raises(PresetValidationError):
        save_preset(user, good(name=""))
    assert Workout.objects.count() == 0 and WorkoutExercise.objects.count() == 0


def test_updating_replaces_the_exercises_and_keeps_the_same_preset(user):
    workout, _ = save_preset(user, good())
    new_sections = {"working_sets": [{"exercise_type": "push_ups", "sets": 4, "reps": 12}]}
    updated, created = save_preset(user, good(id=workout.pk, name="Chest Day", sections=new_sections))
    assert created is False and updated.pk == workout.pk
    assert Workout.objects.count() == 1
    rows = list(updated.exercises.all())
    assert [(r.exercise_type, r.sets, r.reps) for r in rows] == [("push_ups", 4, 12)]
    assert updated.name == "Chest Day"


def test_a_preset_may_be_saved_again_under_its_own_name(user):
    workout, _ = save_preset(user, good())
    again, created = save_preset(user, good(id=workout.pk, name="LEG DAY"))
    assert created is False and again.name == "LEG DAY"


def test_a_failed_update_leaves_the_old_exercises_untouched(user, monkeypatch):
    workout, _ = save_preset(user, good())
    before = list(workout.exercises.values_list("exercise_type", flat=True))

    def explode(*args, **kwargs):
        raise RuntimeError("disk full")
    monkeypatch.setattr(workout_presets, "_create_items", explode)
    with pytest.raises(RuntimeError):
        save_preset(user, good(id=workout.pk, sections={"working_sets": [{"exercise_type": "push_ups", "sets": 1, "reps": 1}]}))
    assert list(workout.exercises.values_list("exercise_type", flat=True)) == before


def test_creating_a_preset_with_a_taken_name_says_which_one(user):
    first, _ = save_preset(user, good())
    for clash in ("Leg Day", "leg day", "  LEG   DAY "):
        with pytest.raises(NameTaken) as info:
            save_preset(user, good(name=clash))
        assert info.value.existing_id == first.pk
    assert Workout.objects.count() == 1


def test_renaming_a_preset_to_another_ones_name_is_refused(user):
    save_preset(user, good())
    other, _ = save_preset(user, good(name="Arm Day"))
    first = Workout.objects.get(name="Leg Day")
    with pytest.raises(NameTaken) as info:
        save_preset(user, good(id=other.pk, name="leg day"))
    assert info.value.existing_id == first.pk
    assert Workout.objects.get(pk=other.pk).name == "Arm Day"


def test_two_users_can_use_the_same_name(user, other_user):
    save_preset(user, good())
    workout, created = save_preset(other_user, good())
    assert created is True and workout.user == other_user


def test_a_simultaneous_save_with_the_same_name_is_reported_as_a_name_clash(user, monkeypatch):
    """Both requests pass the check; the database's rule stops the second one."""
    first, _ = save_preset(user, good())
    real = workout_presets._find_clash
    answers = iter([None])                      # the first look says "no clash" ...
    monkeypatch.setattr(
        workout_presets, "_find_clash",
        lambda *args, **kwargs: next(answers, None) or real(*args, **kwargs),   # ... later looks tell the truth
    )
    with pytest.raises(NameTaken) as info:
        save_preset(user, good())
    assert info.value.existing_id == first.pk


def test_a_simultaneous_clash_with_nothing_visible_still_reports_a_clash(user, monkeypatch):
    def racing_create(**kwargs):
        raise IntegrityError("unique")
    monkeypatch.setattr(workout_presets.Workout.objects, "create", racing_create)
    with pytest.raises(NameTaken) as info:
        save_preset(user, good())
    assert info.value.existing_id is None


def test_updating_someone_elses_preset_or_one_that_does_not_exist_is_refused(user, other_user):
    theirs, _ = save_preset(other_user, good())
    with pytest.raises(PresetNotFound):
        save_preset(user, good(id=theirs.pk))
    with pytest.raises(PresetNotFound):
        save_preset(user, good(id=99999))
    assert Workout.objects.get(pk=theirs.pk).exercises.count() == 4          # untouched


def test_there_is_a_limit_on_how_many_presets_one_person_keeps(user, monkeypatch):
    monkeypatch.setattr(workout_presets, "MAX_PRESETS_PER_USER", 3)
    for number in range(3):
        save_preset(user, good(name=f"Workout {number}"))
    with pytest.raises(TooManyPresets):
        save_preset(user, good(name="One too many"))
    assert Workout.objects.filter(user=user).count() == 3


def test_updating_is_still_allowed_when_a_person_is_at_the_limit(user, monkeypatch):
    monkeypatch.setattr(workout_presets, "MAX_PRESETS_PER_USER", 2)
    first, _ = save_preset(user, good(name="A"))
    save_preset(user, good(name="B"))
    again, created = save_preset(user, good(id=first.pk, name="A2"))
    assert created is False and again.name == "A2"


def test_the_limit_is_per_person(user, other_user, monkeypatch):
    monkeypatch.setattr(workout_presets, "MAX_PRESETS_PER_USER", 1)
    save_preset(user, good())
    assert save_preset(other_user, good())[1] is True


# --- loading -----------------------------------------------------------------------------------------------------------

def test_a_preset_is_loaded_grouped_by_section_in_order(user):
    workout, _ = save_preset(user, good())
    data = serialize_preset(workout, "imperial")
    assert list(data["sections"]) == list(SECTIONS)
    assert [i["exercise_type"] for i in data["sections"]["working_sets"]] == ["back_squat", "cycling"]
    assert data["sections"]["warmup_sets"] == []
    assert (data["id"], data["name"]) == (workout.pk, "Leg Day")


def test_weights_and_distances_are_shown_in_the_requested_units(user):
    workout, _ = save_preset(user, good())
    imperial = serialize_preset(workout, "imperial")
    metric = serialize_preset(workout, "si")
    squat_lb, ride_mi = imperial["sections"]["working_sets"]
    squat_kg, ride_km = metric["sections"]["working_sets"]
    assert (squat_lb["weight"], ride_mi["distance"]) == (135.0, 5.0)
    assert (squat_kg["weight"], ride_km["distance"]) == (61.2, 8.05)
    assert imperial["units"] == {"weight": "lb", "distance": "mi"}
    assert metric["units"] == {"weight": "kg", "distance": "km"}


def test_each_loaded_item_carries_only_its_own_measurements(user):
    data = serialize_preset(save_preset(user, good())[0], "imperial")
    stretch = data["sections"]["warmup_stretch"][0]
    squat, ride = data["sections"]["working_sets"]
    assert stretch == {"exercise_type": "hamstring_stretch", "label": "Hamstring Stretch",
                       "input_type": "duration", "duration_seconds": 45}
    assert set(squat) == {"exercise_type", "label", "input_type", "sets", "reps", "weight"}
    assert set(ride) == {"exercise_type", "label", "input_type", "distance"}


def test_loading_in_an_unknown_unit_system_is_refused(user):
    with pytest.raises(ValueError):
        serialize_preset(save_preset(user, good())[0], "martian")


def test_saving_what_was_loaded_changes_nothing(user):
    """Load a preset, save it back unchanged: the same workout, in either unit system."""
    workout, _ = save_preset(user, good())
    for system in ("imperial", "si", "imperial"):
        loaded = serialize_preset(Workout.objects.get(pk=workout.pk), system)
        payload = {"id": loaded["id"], "name": loaded["name"], "unit_system": system,
                   "sections": {k: [{f: v for f, v in item.items() if f not in ("label", "input_type")}
                                    for item in items] for k, items in loaded["sections"].items()}}
        save_preset(user, payload)
        assert serialize_preset(Workout.objects.get(pk=workout.pk), system) == loaded


# --- the list ----------------------------------------------------------------------------------------------------------------

def test_the_list_shows_only_the_users_own_presets_newest_first(user, other_user):
    old, _ = save_preset(user, good(name="Old"))
    save_preset(other_user, good(name="Not Mine"))
    save_preset(user, good(name="New"))
    names = [p["name"] for p in list_presets(user)]
    assert names == ["New", "Old"]
    assert old.pk in [p["id"] for p in list_presets(user)]


def test_the_list_counts_each_presets_exercises(user):
    save_preset(user, good())
    (entry,) = list_presets(user)
    assert entry["exercise_count"] == 4
    assert entry["updated_at"].startswith("20")


def test_the_list_is_empty_for_a_new_user(user):
    assert list_presets(user) == []


# --- the catalog for the picker -------------------------------------------------------------------------------------------------

def test_the_catalog_payload_lists_the_four_sections_with_their_options():
    payload = catalog_payload()
    assert [s["key"] for s in payload["sections"]] == list(SECTIONS)
    assert payload["limits"] == {"max_per_section": 5, "max_name_length": 40, "max_presets": 50}
    for section in payload["sections"]:
        assert section["max_items"] == 5 and len(section["exercises"]) >= 15
        for option in section["exercises"]:
            assert set(option) == {"key", "label", "group", "input_type", "weighted"}
            assert section["key"] in EXERCISES[option["key"]]["sections"]


def test_the_picker_groups_exercises_together_and_sorts_them():
    working = next(s for s in catalog_payload()["sections"] if s["key"] == "working_sets")
    groups = [option["group"] for option in working["exercises"]]
    seen = []
    for group in groups:
        if not seen or seen[-1] != group:
            seen.append(group)
    assert len(seen) == len(set(seen))                            # each group appears as one block
    legs = [o["label"] for o in working["exercises"] if o["group"] == "Legs"]
    assert legs == sorted(legs, key=str.lower)
