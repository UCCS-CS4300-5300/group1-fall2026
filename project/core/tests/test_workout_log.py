"""Logging a whole workout (Phase 4): POST /workouts/log/ and core/workout_logs.py."""

import json
import types
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.template.loader import get_template
from django.urls import reverse

from core import views_workout, workout_logs, workout_presets
from core.exercises import STAT_NAMES, calculate_stats
from core.models_exercise import ExerciseLog
from core.models_repkin import Repkin
from core.models_workout import MAX_PRESETS_PER_USER, Workout
from core.repkin_voice import gather_facts
from core.workout_presets import (
    PresetValidationError, save_preset, serialize_preset, validate_payload,
)

LOG = "core:workout_log"
STATIC = Path(__file__).resolve().parents[2] / "static"


@pytest.fixture
def user(db):
    return User.objects.create_user("firebase_abc123", password="x")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("firebase_zzz999", password="x")


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


def workout(**changes):
    """A stretch, a weighted lift and a ride. No name: logging doesn't need one."""
    payload = {
        "unit_system": "imperial",
        "sections": {
            "warmup_stretch": [{"exercise_type": "hamstring_stretch", "duration_seconds": 45}],
            "working_sets": [
                {"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight": 135},
                {"exercise_type": "cycling", "distance": 5},
            ],
        },
    }
    payload.update(changes)
    return payload


def post_log(client, payload):
    return client.post(reverse(LOG), data=json.dumps(payload), content_type="application/json")


# ---- The URL ---------------------------------------------------------------------------


def test_the_log_url():
    assert reverse(LOG) == "/workouts/log/"


@pytest.mark.django_db
def test_logging_requires_login(client):
    response = post_log(client, workout())
    assert response.status_code == 302
    assert ExerciseLog.objects.count() == 0


def test_logging_only_allows_post(logged_in_client):
    assert logged_in_client.get(reverse(LOG)).status_code == 405


# ---- What gets logged ------------------------------------------------------------------


def test_every_exercise_is_logged_in_the_order_on_the_page(logged_in_client, user):
    response = post_log(logged_in_client, workout())
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["count"] == 3
    assert len(data["log_ids"]) == 3
    types = [ExerciseLog.objects.get(pk=pk).exercise_type for pk in data["log_ids"]]
    assert types == ["hamstring_stretch", "back_squat", "cycling"]
    assert ExerciseLog.objects.filter(user=user).count() == 3


def test_logs_belong_to_the_signed_in_user_only(logged_in_client, user, other_user):
    post_log(logged_in_client, workout())
    assert ExerciseLog.objects.filter(user=other_user).count() == 0
    assert Repkin.objects.filter(owner=other_user).count() == 0


def test_a_name_is_not_needed_and_is_ignored(logged_in_client):
    assert "name" not in workout()
    assert post_log(logged_in_client, workout()).status_code == 201
    too_long = post_log(logged_in_client, workout(name="x" * 500))
    assert too_long.status_code == 201


def test_without_the_save_flag_logging_saves_no_preset(logged_in_client):
    data = post_log(logged_in_client, workout(name="Leg Day")).json()
    assert Workout.objects.count() == 0
    assert data["preset"] is None


def test_the_weight_is_recorded_in_kilograms(logged_in_client):
    data = post_log(logged_in_client, workout()).json()
    squat = ExerciseLog.objects.get(pk=data["log_ids"][1])
    assert abs(squat.weight_kg - Decimal("61.235")) <= Decimal("0.001")      # 135 lb
    assert ExerciseLog.objects.get(pk=data["log_ids"][0]).weight_kg is None
    assert ExerciseLog.objects.get(pk=data["log_ids"][2]).weight_kg is None


def test_kilogram_users_log_what_they_typed(logged_in_client):
    payload = workout(unit_system="si")
    payload["sections"]["working_sets"][0]["weight"] = 60
    data = post_log(logged_in_client, payload).json()
    assert ExerciseLog.objects.get(pk=data["log_ids"][1]).weight_kg == Decimal("60.000")


def test_distances_are_logged_in_miles_to_two_places(logged_in_client):
    data = post_log(logged_in_client, workout()).json()
    assert ExerciseLog.objects.get(pk=data["log_ids"][2]).distance_miles == Decimal("5.00")

    payload = workout(unit_system="si")           # 5 km is 3.10686 miles
    payload["sections"]["working_sets"][1]["distance"] = 5
    data = post_log(logged_in_client, payload).json()
    assert ExerciseLog.objects.get(pk=data["log_ids"][2]).distance_miles == Decimal("3.11")


def test_the_sets_reps_and_time_are_recorded(logged_in_client):
    data = post_log(logged_in_client, workout()).json()
    stretch, squat, ride = (ExerciseLog.objects.get(pk=pk) for pk in data["log_ids"])
    assert stretch.duration_seconds == 45
    assert (squat.sets, squat.reps) == (3, 8)
    assert ride.sets is None and ride.reps is None


# ---- Saving the workout as a preset while logging it ------------------------------------------


TODAY = date(2026, 11, 16)


@pytest.fixture
def today_is_nov_16(monkeypatch):
    monkeypatch.setattr(views_workout, "timezone", types.SimpleNamespace(localdate=lambda: TODAY))


def saved(user, name="Leg Day", **changes):
    """A preset the user already has."""
    preset, _ = save_preset(user, {**workout(), "name": name, **changes})
    return preset


def test_the_save_flag_saves_the_workout_along_with_the_logs(logged_in_client, user):
    response = post_log(logged_in_client, workout(name="Leg Day", save_preset=True))
    assert response.status_code == 201
    data = response.json()
    preset = Workout.objects.get(user=user)
    assert data["preset"] == {"id": preset.pk, "name": "Leg Day", "created": True}
    assert ExerciseLog.objects.filter(user=user).count() == 3
    assert [row.exercise_type for row in preset.exercises.order_by("id")] == [
        "hamstring_stretch", "back_squat", "cycling",
    ]


def test_the_saved_preset_matches_what_was_logged(logged_in_client, user):
    post_log(logged_in_client, workout(name="Leg Day", save_preset=True))
    sections = serialize_preset(Workout.objects.get(user=user), "imperial")["sections"]
    squat = sections["working_sets"][0]
    assert (squat["sets"], squat["reps"]) == (3, 8)
    assert squat["weight"] == pytest.approx(135, abs=0.1)
    assert sections["working_sets"][1]["distance"] == pytest.approx(5, abs=0.01)
    assert sections["warmup_stretch"][0]["duration_seconds"] == 45


@pytest.mark.parametrize("flag", [False, None, "true", "yes", 1, 0, [], {}])
def test_only_a_real_true_saves_a_preset(logged_in_client, flag):
    response = post_log(logged_in_client, workout(name="Leg Day", save_preset=flag))
    assert response.status_code == 201
    assert Workout.objects.count() == 0


def test_a_blank_name_gets_a_dated_one(logged_in_client, user, today_is_nov_16):
    data = post_log(logged_in_client, workout(save_preset=True)).json()
    assert data["preset"]["name"] == "Workout Nov 16"
    assert Workout.objects.get(user=user).name == "Workout Nov 16"


@pytest.mark.parametrize("name", ["", "   ", None, 42])
def test_a_missing_or_blank_name_is_treated_the_same(logged_in_client, today_is_nov_16, name):
    data = post_log(logged_in_client, workout(name=name, save_preset=True)).json()
    assert data["preset"]["name"] == "Workout Nov 16"


def test_unnamed_workouts_on_the_same_day_get_numbered_names(logged_in_client, user, today_is_nov_16):
    names = [
        post_log(logged_in_client, workout(save_preset=True)).json()["preset"]["name"]
        for _ in range(3)
    ]
    assert names == ["Workout Nov 16", "Workout Nov 16 (2)", "Workout Nov 16 (3)"]
    assert Workout.objects.filter(user=user).count() == 3


def test_a_typed_name_is_used_and_tidied(logged_in_client):
    data = post_log(logged_in_client, workout(name="  Leg    Day ", save_preset=True)).json()
    assert data["preset"]["name"] == "Leg Day"


def test_a_loaded_preset_that_was_changed_is_updated_not_copied(logged_in_client, user):
    original = saved(user)
    payload = workout(id=original.pk, name="Leg Day v2", save_preset=True)
    payload["sections"]["working_sets"] = [{"exercise_type": "push_ups", "sets": 2, "reps": 15}]
    data = post_log(logged_in_client, payload).json()
    assert data["preset"] == {"id": original.pk, "name": "Leg Day v2", "created": False}
    assert Workout.objects.filter(user=user).count() == 1
    original.refresh_from_db()
    assert original.name == "Leg Day v2"
    assert sorted(row.exercise_type for row in original.exercises.all()) == ["hamstring_stretch", "push_ups"]
    assert ExerciseLog.objects.filter(user=user).count() == 2, "what was logged is what was on screen"


def test_another_users_preset_can_not_be_overwritten(logged_in_client, user, other_user):
    theirs = saved(other_user, name="Their Plan")
    response = post_log(logged_in_client, workout(id=theirs.pk, name="Mine", save_preset=True))
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    theirs.refresh_from_db()
    assert theirs.name == "Their Plan"
    assert ExerciseLog.objects.count() == 0


def test_a_taken_name_changes_nothing_so_the_page_can_ask_to_replace_it(logged_in_client, user):
    existing = saved(user, name="Leg Day", sections={
        "working_sets": [{"exercise_type": "push_ups", "sets": 1, "reps": 1}],
    })
    response = post_log(logged_in_client, workout(name="leg day", save_preset=True))
    assert response.status_code == 409
    body = response.json()
    assert (body["error"], body["existing_id"]) == ("name_taken", existing.pk)
    assert ExerciseLog.objects.count() == 0
    assert Repkin.objects.filter(owner=user).count() == 0
    assert Workout.objects.filter(user=user).count() == 1
    assert [row.exercise_type for row in existing.exercises.all()] == ["push_ups"], "untouched"


def test_replacing_a_taken_name_saves_over_it_and_logs(logged_in_client, user):
    existing = saved(user, name="Leg Day", sections={
        "working_sets": [{"exercise_type": "push_ups", "sets": 1, "reps": 1}],
    })
    data = post_log(logged_in_client, workout(name="Leg Day", id=existing.pk, save_preset=True)).json()
    assert data["preset"] == {"id": existing.pk, "name": "Leg Day", "created": False}
    assert Workout.objects.filter(user=user).count() == 1
    assert existing.exercises.count() == 3
    assert ExerciseLog.objects.filter(user=user).count() == 3


def test_at_the_preset_limit_a_new_preset_is_refused_and_nothing_is_logged(logged_in_client, user):
    Workout.objects.bulk_create(
        [Workout(user=user, name=f"Preset {number}") for number in range(MAX_PRESETS_PER_USER)]
    )
    response = post_log(logged_in_client, workout(name="One too many", save_preset=True))
    assert response.status_code == 409
    assert response.json()["error"] == "too_many_presets"
    assert ExerciseLog.objects.count() == 0
    assert Repkin.objects.filter(owner=user).count() == 0
    assert Workout.objects.filter(user=user).count() == MAX_PRESETS_PER_USER


def test_at_the_limit_a_workout_that_is_not_being_saved_can_still_be_logged(logged_in_client, user):
    Workout.objects.bulk_create(
        [Workout(user=user, name=f"Preset {number}") for number in range(MAX_PRESETS_PER_USER)]
    )
    assert post_log(logged_in_client, workout()).status_code == 201


def test_at_the_limit_updating_an_existing_preset_is_fine(logged_in_client, user):
    first = saved(user, name="First")
    Workout.objects.bulk_create(
        [Workout(user=user, name=f"Preset {number}") for number in range(MAX_PRESETS_PER_USER - 1)]
    )
    response = post_log(logged_in_client, workout(id=first.pk, name="First", save_preset=True))
    assert response.status_code == 201
    assert Workout.objects.filter(user=user).count() == MAX_PRESETS_PER_USER


def test_a_name_that_is_too_long_is_refused_and_nothing_happens(logged_in_client, user):
    response = post_log(logged_in_client, workout(name="x" * 41, save_preset=True))
    assert response.status_code == 400
    assert [e["where"] for e in response.json()["errors"]] == ["name"]
    assert ExerciseLog.objects.count() == 0
    assert Workout.objects.count() == 0


def test_a_bad_exercise_means_nothing_is_saved_or_logged(logged_in_client, user):
    payload = workout(name="Leg Day", save_preset=True)
    del payload["sections"]["working_sets"][0]["reps"]
    assert post_log(logged_in_client, payload).status_code == 400
    assert ExerciseLog.objects.count() == 0
    assert Workout.objects.count() == 0


def test_if_logging_fails_the_preset_is_not_saved_either(logged_in_client, user, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(views_workout, "log_workout", broken)
    with pytest.raises(RuntimeError):
        post_log(logged_in_client, workout(name="Leg Day", save_preset=True))
    assert Workout.objects.count() == 0
    assert ExerciseLog.objects.count() == 0


def test_kilogram_users_get_a_preset_that_loads_back_in_kilograms(logged_in_client, user):
    payload = workout(unit_system="si", name="Metric", save_preset=True)
    payload["sections"]["working_sets"][0]["weight"] = 60
    post_log(logged_in_client, payload)
    sections = serialize_preset(Workout.objects.get(user=user), "si")["sections"]
    assert sections["working_sets"][0]["weight"] == pytest.approx(60, abs=0.1)


def test_the_save_endpoint_still_gives_the_same_replies(logged_in_client, user):
    """Saving and logging share their error replies. Spot-check that Save still has them."""
    save_url = reverse("core:workout_preset_save")
    body = json.dumps({**workout(), "name": "Leg Day"})
    assert logged_in_client.post(save_url, body, content_type="application/json").status_code == 201
    clash = logged_in_client.post(save_url, body, content_type="application/json")
    assert (clash.status_code, clash.json()["error"]) == (409, "name_taken")
    missing = logged_in_client.post(
        save_url, json.dumps({**workout(), "name": "X", "id": 999999}), content_type="application/json"
    )
    assert (missing.status_code, missing.json()["error"]) == (404, "not_found")


# ---- The automatic name -----------------------------------------------------------------------


def test_default_name_is_the_date_without_a_leading_zero(user):
    assert workout_presets.default_preset_name(user, date(2026, 3, 5)) == "Workout Mar 5"
    assert workout_presets.default_preset_name(user, date(2026, 11, 16)) == "Workout Nov 16"


def test_default_name_skips_names_already_taken_ignoring_capitals(user):
    saved(user, name="workout NOV 16")
    assert workout_presets.default_preset_name(user, TODAY) == "Workout Nov 16 (2)"
    saved(user, name="Workout Nov 16 (2)")
    assert workout_presets.default_preset_name(user, TODAY) == "Workout Nov 16 (3)"


def test_default_name_only_looks_at_this_users_presets(user, other_user):
    saved(other_user, name="Workout Nov 16")
    assert workout_presets.default_preset_name(user, TODAY) == "Workout Nov 16"


def test_with_default_name_fills_in_only_a_missing_name(user):
    fill = workout_presets.with_default_name
    assert fill(user, {"name": "Leg Day"}, TODAY) == {"name": "Leg Day"}
    for blank in ({}, {"name": ""}, {"name": "   "}, {"name": None}, {"name": 7}):
        assert fill(user, blank, TODAY)["name"] == "Workout Nov 16"


def test_with_default_name_leaves_the_original_alone_and_ignores_non_objects(user):
    original = {"unit_system": "imperial"}
    result = workout_presets.with_default_name(user, original, TODAY)
    assert "name" not in original and result["name"] == "Workout Nov 16"
    assert workout_presets.with_default_name(user, [1, 2], TODAY) == [1, 2]


# ---- Points ----------------------------------------------------------------------------


def expected_totals():
    parts = [
        calculate_stats("hamstring_stretch", {"duration_seconds": 45}),
        calculate_stats("back_squat", {"sets": 3, "reps": 8}),
        calculate_stats("cycling", {"distance_miles": Decimal("5.00")}),
    ]
    return {name: sum(part[name] for part in parts) for name in STAT_NAMES}


def test_each_log_earns_the_same_points_as_logging_it_alone(logged_in_client):
    data = post_log(logged_in_client, workout()).json()
    stretch, squat, ride = (ExerciseLog.objects.get(pk=pk) for pk in data["log_ids"])
    for log, wanted in (
        (stretch, calculate_stats("hamstring_stretch", {"duration_seconds": 45})),
        (squat, calculate_stats("back_squat", {"sets": 3, "reps": 8})),
        (ride, calculate_stats("cycling", {"distance_miles": Decimal("5.00")})),
    ):
        assert {name: getattr(log, name) for name in STAT_NAMES} == wanted


def test_the_response_totals_what_the_workout_earned(logged_in_client):
    data = post_log(logged_in_client, workout()).json()
    assert data["stats"] == expected_totals()
    assert sum(data["stats"].values()) > 0


def test_the_points_go_to_repkins_weekly_progress(logged_in_client, user):
    post_log(logged_in_client, workout())
    repkin = Repkin.objects.get(owner=user)
    for name, total in expected_totals().items():
        assert getattr(repkin, f"progress_{name}") == total


def test_logging_twice_counts_twice(logged_in_client, user):
    post_log(logged_in_client, workout())
    post_log(logged_in_client, workout())
    repkin = Repkin.objects.get(owner=user)
    for name, total in expected_totals().items():
        assert getattr(repkin, f"progress_{name}") == 2 * total


def test_the_weight_lifted_does_not_change_the_points(logged_in_client):
    light = workout()
    heavy = workout()
    heavy["sections"]["working_sets"][0]["weight"] = 400
    light_logs = post_log(logged_in_client, light).json()
    heavy_logs = post_log(logged_in_client, heavy).json()
    assert light_logs["stats"] == heavy_logs["stats"]


# ---- Bad requests ----------------------------------------------------------------------


def test_a_bad_exercise_is_reported_and_nothing_is_logged(logged_in_client, user):
    payload = workout()
    del payload["sections"]["working_sets"][0]["reps"]
    response = post_log(logged_in_client, payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation"
    problem = body["errors"][0]
    assert (problem["where"], problem["section"], problem["index"]) == ("item", "working_sets", 0)
    assert ExerciseLog.objects.count() == 0
    assert Repkin.objects.filter(owner=user).count() == 0


def test_an_empty_workout_is_refused(logged_in_client):
    response = post_log(logged_in_client, workout(sections={}))
    assert response.status_code == 400
    assert any("at least one" in e["message"].lower() for e in response.json()["errors"])
    assert ExerciseLog.objects.count() == 0


def test_a_missing_unit_system_is_refused(logged_in_client):
    payload = workout()
    del payload["unit_system"]
    assert post_log(logged_in_client, payload).status_code == 400
    assert ExerciseLog.objects.count() == 0


def test_too_many_exercises_in_a_section_is_refused(logged_in_client):
    payload = workout()
    payload["sections"]["working_sets"] = [{"exercise_type": "push_ups", "sets": 1, "reps": 1}] * 6
    assert post_log(logged_in_client, payload).status_code == 400
    assert ExerciseLog.objects.count() == 0


def test_an_exercise_from_the_wrong_section_is_refused(logged_in_client):
    payload = workout()
    payload["sections"]["warmup_stretch"] = [{"exercise_type": "back_squat", "sets": 1, "reps": 1}]
    assert post_log(logged_in_client, payload).status_code == 400
    assert ExerciseLog.objects.count() == 0


def test_invalid_json_is_refused(logged_in_client):
    response = logged_in_client.post(reverse(LOG), data="{nope", content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"


def test_a_huge_request_is_refused(logged_in_client):
    response = logged_in_client.post(
        reverse(LOG), data=json.dumps({"junk": "x" * 60_000}), content_type="application/json"
    )
    assert response.status_code == 413
    assert ExerciseLog.objects.count() == 0


def test_a_payload_that_is_not_an_object_is_refused(logged_in_client):
    assert post_log(logged_in_client, [1, 2, 3]).status_code == 400


# ---- All or nothing --------------------------------------------------------------------


def test_if_one_exercise_fails_none_are_logged(user, monkeypatch):
    real = workout_logs.log_exercise
    calls = []

    def flaky(who, data):
        calls.append(data["exercise_type"])
        if len(calls) == 2:
            raise RuntimeError("the database went away")
        return real(who, data)

    monkeypatch.setattr(workout_logs, "log_exercise", flaky)
    cleaned = validate_payload(workout(), require_name=False)
    with pytest.raises(RuntimeError):
        workout_logs.log_workout(user, cleaned["items"])
    assert len(calls) == 2
    assert ExerciseLog.objects.count() == 0
    assert Repkin.objects.filter(owner=user).count() == 0, "the first exercise's points were undone too"


# ---- The service's small pieces ----------------------------------------------------------


def test_distance_rounds_half_up_to_two_places():
    item = {"exercise_type": "running", "distance_miles": Decimal("3.105")}
    assert workout_logs.exercise_data(item)["distance_miles"] == Decimal("3.11")
    item["distance_miles"] = Decimal("3.104")
    assert workout_logs.exercise_data(item)["distance_miles"] == Decimal("3.10")


def test_exercise_data_fills_missing_measurements_with_none():
    data = workout_logs.exercise_data({"exercise_type": "push_ups", "sets": 3, "reps": 10})
    assert data == {
        "exercise_type": "push_ups", "sets": 3, "reps": 10,
        "duration_seconds": None, "distance_miles": None, "weight_kg": None,
    }


def test_exercise_data_passes_the_weight_through():
    data = workout_logs.exercise_data(
        {"exercise_type": "back_squat", "sets": 3, "reps": 8, "weight_kg": Decimal("61.235")}
    )
    assert data["weight_kg"] == Decimal("61.235")


def test_stat_totals_of_nothing_is_zero():
    assert workout_logs.stat_totals([]) == {name: 0 for name in STAT_NAMES}


# ---- Logging needs no name, but is otherwise as strict as saving -------------------------------


def test_validate_payload_can_skip_the_name():
    cleaned = validate_payload(workout(), require_name=False)
    assert cleaned["name"] is None
    assert sum(len(items) for items in cleaned["items"].values()) == 3


def test_validate_payload_still_wants_a_name_by_default():
    with pytest.raises(PresetValidationError) as problem:
        validate_payload(workout())
    assert [e["where"] for e in problem.value.errors] == ["name"]


def test_skipping_the_name_still_needs_an_exercise():
    with pytest.raises(PresetValidationError):
        validate_payload(workout(sections={}), require_name=False)


# ---- RepKin can comment on what was logged -------------------------------------------------


def test_the_returned_log_ids_are_what_repkins_comment_uses(logged_in_client, user):
    data = post_log(logged_in_client, workout()).json()
    facts = gather_facts(user, data["log_ids"])
    assert len(facts.just_logged) == 3


# ---- The page and the home page are wired together ------------------------------------------


def source(template_name):
    return open(get_template(template_name).origin.name, encoding="utf-8").read()


def test_the_page_hands_the_script_the_log_url():
    assert 'data-log-url="{% url \'core:workout_log\' %}"' in source("core/workout_logging.html")


def test_the_builder_and_the_home_page_use_the_same_note_name():
    builder = (STATIC / "js" / "workout_builder.js").read_text(encoding="utf-8")
    home = (STATIC / "js" / "workout_logged.js").read_text(encoding="utf-8")
    key = "repkinz.pendingWorkoutLog"
    assert f'"{key}"' in builder
    assert f'"{key}"' in home


def test_the_home_page_loads_the_handoff_script():
    assert "js/workout_logged.js" in source("core/home.html")


def test_the_handoff_fires_the_event_the_bubble_listens_for():
    handoff = (STATIC / "js" / "workout_logged.js").read_text(encoding="utf-8")
    bubble = (STATIC / "core" / "repkin_bubble.js").read_text(encoding="utf-8")
    assert 'CustomEvent("exercise:logged"' in handoff
    assert "logIds" in handoff
    assert 'addEventListener("exercise:logged"' in bubble
