import ast
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from core import exercises
from core.exercises import (
    DISTANCE, DURATION, EXERCISES, GROUPS, MAX_PER_SECTION, POINTS_PER_MILE, REPS,
    SECTIONS, STAT_NAMES, calculate_stats, effort_points, exercise_label,
    exercises_for_section,
)
from core.forms_exercise import ExerciseInputForm
from core.models_exercise import ExerciseLog

# Saved history refers to these by name, so they must never change.
ORIGINAL_EXERCISES = {
    "push_ups": (REPS, {"strength": 80, "endurance": 20}),
    "sit_ups": (REPS, {"strength": 60, "endurance": 40}),
    "squats": (REPS, {"strength": 70, "endurance": 30}),
    "curls": (REPS, {"strength": 100}),
    "lunges": (REPS, {"strength": 50, "dexterity": 30, "endurance": 20}),
    "planks": (DURATION, {"strength": 40, "endurance": 60}),
    "butterfly_stretch": (DURATION, {"dexterity": 100}),
    "shoulder_stretch": (DURATION, {"dexterity": 100}),
    "walking": (DISTANCE, {"endurance": 100}),
    "jogging": (DISTANCE, {"dexterity": 20, "endurance": 80}),
    "running": (DISTANCE, {"dexterity": 30, "endurance": 70}),
}

SAMPLE_DATA = {
    REPS: {"sets": 3, "reps": 10},
    DURATION: {"duration_seconds": 60},
    DISTANCE: {"distance_miles": 2},
}


def test_the_original_exercises_are_unchanged():
    for key, (input_type, split) in ORIGINAL_EXERCISES.items():
        assert EXERCISES[key]["input_type"] == input_type, key
        assert EXERCISES[key]["split"] == split, key


@pytest.mark.parametrize("key", list(EXERCISES))
def test_each_exercise_is_well_formed(key):
    entry = EXERCISES[key]
    assert key == key.lower() and key.replace("_", "").isalnum()
    assert len(key) <= 40                                   # fits the database column
    assert entry["input_type"] in (REPS, DURATION, DISTANCE)
    assert set(entry["split"]) <= set(STAT_NAMES)
    assert sum(entry["split"].values()) == 100
    assert entry["sections"] and set(entry["sections"]) <= set(SECTIONS)
    assert entry["group"] in GROUPS
    assert isinstance(entry["weighted"], bool)


def test_only_rep_based_exercises_can_record_a_weight():
    for key, entry in EXERCISES.items():
        if entry["weighted"]:
            assert entry["input_type"] == REPS, key


def test_only_distance_exercises_override_points_per_mile():
    for key, entry in EXERCISES.items():
        if "points_per_mile" in entry:
            assert entry["input_type"] == DISTANCE, key
            assert entry["points_per_mile"] > 0


def test_labels_are_unique():
    labels = [exercise_label(key).lower() for key in EXERCISES]
    assert len(labels) == len(set(labels))


def test_labels_are_title_case_unless_a_special_one_is_given():
    assert exercise_label("push_ups") == "Push Ups"
    assert exercise_label("worlds_greatest_stretch") == "World's Greatest Stretch"
    assert exercise_label("childs_pose") == "Child's Pose"
    assert exercise_label("cat_cow") == "Cat-Cow"


def test_no_exercise_key_is_written_twice_in_the_catalog():
    """A repeated key in a Python dict silently replaces the earlier one."""
    tree = ast.parse(Path(exercises.__file__).read_text(encoding="utf-8"))
    catalog = next(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(getattr(target, "id", None) == "EXERCISES" for target in node.targets)
    )
    keys = [key.value for key in catalog.keys]
    assert len(keys) == len(set(keys)) == len(EXERCISES)


# --- the four sections -----------------------------------------------------------

def test_the_sections_are_in_the_order_they_appear_on_the_page():
    assert list(SECTIONS) == ["warmup_stretch", "warmup_sets", "working_sets", "cooldown_stretch"]
    assert list(SECTIONS.values()) == [
        "Warm up and stretches", "Warm-up sets/exercises",
        "Working sets/exercises", "Cooldown and stretches",
    ]
    assert MAX_PER_SECTION == 5


@pytest.mark.parametrize("section", list(SECTIONS))
def test_every_section_offers_plenty_of_choice(section):
    assert len(exercises_for_section(section)) >= 15


def test_exercises_for_a_section_only_includes_those_tagged_for_it():
    for section in SECTIONS:
        for key in exercises_for_section(section):
            assert section in EXERCISES[key]["sections"]
    assert "hamstring_stretch" not in exercises_for_section("working_sets")
    assert "back_squat" not in exercises_for_section("cooldown_stretch")


def test_stretch_sections_offer_stretches():
    stretches = {key for key, entry in EXERCISES.items() if entry["group"] == "Stretches"}
    assert len(stretches) >= 10
    for key in stretches:
        assert EXERCISES[key]["input_type"] == DURATION
        assert EXERCISES[key]["split"] == {"dexterity": 100}
    assert len(stretches & set(exercises_for_section("warmup_stretch"))) >= 8
    assert len(stretches & set(exercises_for_section("cooldown_stretch"))) >= 8


def test_working_sets_cover_every_kind_of_training():
    groups = {EXERCISES[key]["group"] for key in exercises_for_section("working_sets")}
    assert {"Legs", "Chest", "Back", "Shoulders", "Arms", "Core", "Full body", "Cardio"} <= groups


def test_the_catalog_is_much_bigger_than_the_original_eleven():
    assert len(EXERCISES) >= 80


# --- everything else reads from the catalog -----------------------------------------

def test_the_exercise_form_reads_its_lists_from_the_catalog():
    assert {key for key, _ in ExerciseInputForm.EXERCISE_CHOICES} == set(EXERCISES)
    for input_type, attribute in [
        (REPS, "REPETITION_EXERCISES"), (DURATION, "DURATION_EXERCISES"), (DISTANCE, "DISTANCE_EXERCISES"),
    ]:
        expected = {key for key, entry in EXERCISES.items() if entry["input_type"] == input_type}
        assert getattr(ExerciseInputForm, attribute) == expected


def test_the_database_choices_include_every_exercise():
    assert {key for key, _ in ExerciseLog.EXERCISE_CHOICES} == set(EXERCISES)


def test_the_catalog_and_the_models_have_no_unmigrated_changes(db):
    """Changing the catalog changes the model's choices, which needs a migration."""
    output = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=output, stderr=output)
    except SystemExit:
        pytest.fail("Run `python manage.py makemigrations`. Pending: " + output.getvalue())


# --- points ---------------------------------------------------------------------------------

@pytest.mark.parametrize("key", list(EXERCISES))
def test_every_exercise_can_be_scored(key):
    data = SAMPLE_DATA[EXERCISES[key]["input_type"]]
    stats = calculate_stats(key, data)
    assert set(stats) == set(STAT_NAMES)
    assert all(value >= 0 for value in stats.values())
    assert abs(sum(stats.values()) - effort_points(key, data)) <= 2     # only rounding differs


def test_a_mile_of_cycling_is_worth_less_than_a_mile_of_running():
    ride = effort_points("cycling", {"distance_miles": 10})
    run = effort_points("running", {"distance_miles": 10})
    assert ride == 150 and run == 10 * POINTS_PER_MILE
    assert ride < run


def test_other_distance_exercises_use_the_standard_points_per_mile():
    for key in ("walking", "jogging", "running"):
        assert effort_points(key, {"distance_miles": 1}) == POINTS_PER_MILE


def test_the_weight_lifted_does_not_change_the_points():
    plain = calculate_stats("back_squat", {"sets": 3, "reps": 8})
    heavy = calculate_stats("back_squat", {"sets": 3, "reps": 8, "weight_kg": 200})
    assert plain == heavy
