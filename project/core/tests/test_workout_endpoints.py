import json
import re

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core import views_workout, workout_presets
from core.models_workout import Workout

SAVE = "core:workout_preset_save"
LIST = "core:workout_presets"
DETAIL = "core:workout_preset_detail"
DELETE = "core:workout_preset_delete"
CATALOG = "core:workout_catalog"


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
        },
    }
    payload.update(changes)
    return payload


def save(client, payload):
    return client.post(reverse(SAVE), json.dumps(payload), content_type="application/json")


def detail(client, pk, system="imperial"):
    return client.get(reverse(DETAIL, args=[pk]) + f"?unit_system={system}")


# --- who may use these ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method, url_name, args",
    [("get", CATALOG, []), ("get", LIST, []), ("get", DETAIL, [1]), ("post", SAVE, []), ("post", DELETE, [1])],
)
def test_logged_out_visitors_are_sent_to_login(client, db, method, url_name, args):
    url = reverse(url_name, args=args)
    response = getattr(client, method)(url)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.parametrize(
    "method, url_name, args",
    [("post", CATALOG, []), ("post", LIST, []), ("post", DETAIL, [1]), ("get", SAVE, []), ("get", DELETE, [1])],
)
def test_each_address_accepts_only_its_own_kind_of_request(logged_in_client, method, url_name, args):
    response = getattr(logged_in_client, method)(reverse(url_name, args=args))
    assert response.status_code == 405


@pytest.mark.parametrize("url_name, args", [(SAVE, []), (DELETE, [1])])
def test_saving_and_deleting_are_protected_against_forged_requests(user, url_name, args):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.post(reverse(url_name, args=args), "{}", content_type="application/json")
    assert response.status_code == 403


def test_a_csrf_token_in_the_header_is_accepted(user):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get(reverse("core:home"))
    token = client.cookies["csrftoken"].value
    response = client.post(
        reverse(SAVE), json.dumps(good()), content_type="application/json", HTTP_X_CSRFTOKEN=token
    )
    assert response.status_code == 201


# --- the catalog and the list ----------------------------------------------------------------------------

def test_the_catalog_is_served_as_json(logged_in_client):
    response = logged_in_client.get(reverse(CATALOG))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert [s["key"] for s in response.json()["sections"]] == [
        "warmup_stretch", "warmup_sets", "working_sets", "cooldown_stretch",
    ]


def test_the_list_starts_empty(logged_in_client):
    assert logged_in_client.get(reverse(LIST)).json() == {"presets": [], "max_presets": 50}


def test_the_list_shows_only_my_presets(client, user, other_user):
    client.force_login(other_user)
    save(client, good(name="Not Mine"))
    client.force_login(user)
    save(client, good(name="Mine"))
    names = [p["name"] for p in client.get(reverse(LIST)).json()["presets"]]
    assert names == ["Mine"]


# --- saving ---------------------------------------------------------------------------------------------------

def test_saving_a_new_preset_returns_201_and_its_id(logged_in_client, user):
    response = save(logged_in_client, good())
    assert response.status_code == 201
    body = response.json()
    assert body == {"id": Workout.objects.get(user=user).pk, "name": "Leg Day", "created": True}


def test_saving_with_an_id_updates_and_returns_200(logged_in_client):
    pk = save(logged_in_client, good()).json()["id"]
    response = save(logged_in_client, good(id=pk, name="Leg Day v2"))
    assert response.status_code == 200
    assert response.json() == {"id": pk, "name": "Leg Day v2", "created": False}
    assert Workout.objects.count() == 1


@pytest.mark.parametrize("body", ["not json", "{", "", "null"])
def test_a_body_that_is_not_a_json_object_is_rejected(logged_in_client, body):
    response = logged_in_client.post(reverse(SAVE), body, content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"] in ("invalid_json", "validation")
    assert Workout.objects.count() == 0


def test_validation_problems_come_back_as_a_list_saying_where(logged_in_client):
    payload = good(name="", sections={"working_sets": [{"exercise_type": "push_ups", "sets": 3}]})
    response = save(logged_in_client, payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation"
    wheres = {(e["where"], e.get("section"), e.get("index"), e.get("field")) for e in body["errors"]}
    assert ("name", None, None, None) in wheres
    assert ("item", "working_sets", 0, "reps") in wheres
    assert Workout.objects.count() == 0


def test_a_taken_name_is_a_409_naming_the_existing_preset(logged_in_client):
    first = save(logged_in_client, good()).json()["id"]
    response = save(logged_in_client, good(name="leg day"))
    assert response.status_code == 409
    assert response.json()["error"] == "name_taken"
    assert response.json()["existing_id"] == first


def test_the_limit_on_presets_is_a_409(logged_in_client, monkeypatch):
    monkeypatch.setattr(workout_presets, "MAX_PRESETS_PER_USER", 1)
    save(logged_in_client, good(name="One"))
    response = save(logged_in_client, good(name="Two"))
    assert response.status_code == 409
    assert response.json()["error"] == "too_many_presets"


def test_updating_a_preset_that_is_not_mine_is_a_404(client, user, other_user):
    client.force_login(other_user)
    theirs = save(client, good()).json()["id"]
    client.force_login(user)
    response = save(client, good(id=theirs, name="Hijacked"))
    assert response.status_code == 404
    assert Workout.objects.get(pk=theirs).name == "Leg Day"


def test_a_request_that_is_far_too_large_is_refused(logged_in_client):
    huge = json.dumps(good(name="x" * (views_workout.MAX_BODY_BYTES + 10)))
    response = logged_in_client.post(reverse(SAVE), huge, content_type="application/json")
    assert response.status_code == 413
    assert Workout.objects.count() == 0


# --- loading one preset -------------------------------------------------------------------------------------------

def test_a_preset_loads_in_the_requested_unit_system(logged_in_client):
    pk = save(logged_in_client, good()).json()["id"]
    pounds = detail(logged_in_client, pk, "imperial").json()
    kilos = detail(logged_in_client, pk, "si").json()
    assert pounds["sections"]["working_sets"][0]["weight"] == 135.0
    assert kilos["sections"]["working_sets"][0]["weight"] == 61.2
    assert kilos["sections"]["working_sets"][1]["distance"] == 8.05
    assert kilos["units"] == {"weight": "kg", "distance": "km"}


@pytest.mark.parametrize("query", ["", "?unit_system=", "?unit_system=martian", "?unit_system=SI"])
def test_loading_needs_a_valid_unit_system(logged_in_client, query):
    pk = save(logged_in_client, good()).json()["id"]
    response = logged_in_client.get(reverse(DETAIL, args=[pk]) + query)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_unit_system"


def test_a_preset_that_does_not_exist_is_a_404(logged_in_client):
    assert detail(logged_in_client, 99999).status_code == 404


def test_someone_elses_preset_looks_like_it_does_not_exist(client, user, other_user):
    client.force_login(other_user)
    theirs = save(client, good()).json()["id"]
    client.force_login(user)
    assert detail(client, theirs).status_code == 404


# --- deleting --------------------------------------------------------------------------------------------------------------

def test_deleting_a_preset_removes_it_and_its_exercises(logged_in_client):
    pk = save(logged_in_client, good()).json()["id"]
    response = logged_in_client.post(reverse(DELETE, args=[pk]))
    assert response.status_code == 200 and response.json() == {"deleted": True}
    assert Workout.objects.count() == 0
    assert detail(logged_in_client, pk).status_code == 404


def test_deleting_someone_elses_preset_is_a_404_and_changes_nothing(client, user, other_user):
    client.force_login(other_user)
    theirs = save(client, good()).json()["id"]
    client.force_login(user)
    assert client.post(reverse(DELETE, args=[theirs])).status_code == 404
    assert Workout.objects.filter(pk=theirs).exists()


def test_deleting_something_that_does_not_exist_is_a_404(logged_in_client):
    assert logged_in_client.post(reverse(DELETE, args=[99999])).status_code == 404


# --- the whole journey ---------------------------------------------------------------------------------------------------------

def test_create_list_load_edit_and_delete(logged_in_client):
    pk = save(logged_in_client, good()).json()["id"]
    assert [p["id"] for p in logged_in_client.get(reverse(LIST)).json()["presets"]] == [pk]

    loaded = detail(logged_in_client, pk, "si").json()
    loaded["sections"]["working_sets"][0]["weight"] = 70
    edit = {"id": pk, "name": loaded["name"], "unit_system": "si", "sections": loaded["sections"]}
    assert save(logged_in_client, edit).status_code == 200

    assert detail(logged_in_client, pk, "si").json()["sections"]["working_sets"][0]["weight"] == 70.0
    assert logged_in_client.post(reverse(DELETE, args=[pk])).status_code == 200
    assert logged_in_client.get(reverse(LIST)).json()["presets"] == []
