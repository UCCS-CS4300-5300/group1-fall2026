"""Logging a whole workout (Phase 4): POST /workouts/log/ and core/workout_logs.py."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.template.loader import get_template
from django.urls import reverse

from core import workout_logs
from core.exercises import STAT_NAMES, calculate_stats
from core.models_exercise import ExerciseLog
from core.models_repkin import Repkin
from core.models_workout import Workout
from core.repkin_voice import gather_facts
from core.workout_presets import PresetValidationError, validate_payload

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


def test_logging_does_not_save_a_preset(logged_in_client):
    post_log(logged_in_client, workout(name="Leg Day"))
    assert Workout.objects.count() == 0


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
