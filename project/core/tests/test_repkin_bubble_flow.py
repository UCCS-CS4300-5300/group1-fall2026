import re

import pytest
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import Client
from django.urls import reverse
from firebase_admin import auth as firebase_auth

from core import repkin_voice
from core.models_exercise import ExerciseLog
from core.models_repkin import Repkin
from core.views_message import GREETING_PENDING_KEY #GREETING_PENDING_KEY #LAST_SERVED_KEY

MESSAGE_URL = "core:repkin_message"
VALID_EXERCISE = {"exercise_type": "push_ups", "sets": 3, "reps": 10}


# --- helpers ---------------------------------------------------------------

@pytest.fixture
def fake_chat(monkeypatch):
    state = {"reply": "You crushed it!", "prompts": []}

    def fake(messages):
        state["prompts"].append(messages[0]["content"])
        return state["reply"]

    monkeypatch.setattr(repkin_voice, "chat", fake)
    return state


@pytest.fixture
def firebase_login(monkeypatch):
    """Log in the way the real site does: through firebase_session."""
    monkeypatch.setattr(
        "core.views.verify_firebase_id_token",
        lambda token: {"uid": "abc123", "email": "sam@example.com"},
    )

    def log_in(client):
        return client.post(reverse("core:firebase_session"), {"idToken": "signed-token"})

    return log_in


def greeting(client):
    return client.post(reverse(MESSAGE_URL), {"kind": "greeting"}).json()["message"]


@pytest.fixture
def user(db):
    return User.objects.create_user("firebase_abc123", password="x")


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


# --- every login is greeted once ---------------------------------------------

def test_logging_in_marks_the_session_as_owed_a_greeting(client, db, firebase_login):
    assert firebase_login(client).status_code == 200
    assert client.session[GREETING_PENDING_KEY] is True #GREETING_PENDING_KEY #LAST_SERVED_KEY


def test_each_login_gets_exactly_one_greeting(client, db, firebase_login, fake_chat):
    firebase_login(client)
    assert greeting(client) == "You crushed it!"
    assert greeting(client) is None            # a refresh or second tab: nothing more
    assert greeting(client) is None

    client.post(reverse("core:logout"))
    firebase_login(client)                      # straight back in
    assert greeting(client) == "You crushed it!"
    assert greeting(client) is None

    assert len(fake_chat["prompts"]) == 2       # two logins, two greetings, no more


def test_logging_out_takes_away_a_greeting_that_was_never_used(
    client, db, firebase_login, fake_chat
):
    firebase_login(client)
    client.post(reverse("core:logout"))
    assert GREETING_PENDING_KEY not in client.session #GREETING_PENDING_KEY #LAST_SERVED_KEY


def test_a_failed_login_is_not_owed_a_greeting(client, db, monkeypatch, fake_chat):
    def reject(token):
        raise firebase_auth.InvalidIdTokenError("bad token")

    monkeypatch.setattr("core.views.verify_firebase_id_token", reject)
    response = client.post(reverse("core:firebase_session"), {"idToken": "nope"})
    assert response.status_code == 401
    assert GREETING_PENDING_KEY not in client.session #GREETING_PENDING_KEY #LAST_SERVED_KEY
    assert "_auth_user_id" not in client.session
    assert fake_chat["prompts"] == []


def test_opening_the_home_page_does_not_use_up_the_greeting(
    client, db, firebase_login, fake_chat
):
    firebase_login(client)
    for _ in range(3):
        client.get(reverse("core:home"))
    assert greeting(client) == "You crushed it!"


# --- the bubble on the home page ----------------------------------------------

def test_home_page_contains_the_bubble(logged_in_client):
    html = logged_in_client.get(reverse("core:home")).content.decode()
    assert 'id="repkin-bubble"' in html
    assert f'data-message-url="{reverse(MESSAGE_URL)}"' in html
    assert 'aria-label="Dismiss message"' in html
    assert 'role="status"' in html
    assert "core/repkin_bubble.js" in html
    assert "css/repkin_bubble.css" in html


def test_the_bubble_starts_hidden(logged_in_client):
    html = logged_in_client.get(reverse("core:home")).content.decode()
    tag = re.search(r'<div id="repkin-bubble"[^>]*>', html, re.S).group(0)
    assert re.search(r"\bhidden\b", tag)


def test_the_bubble_sits_inside_the_stage(logged_in_client):
    html = logged_in_client.get(reverse("core:home")).content.decode()
    assert html.index('class="stage"') < html.index('id="repkin-bubble"')
    assert html.index('id="repkin-bubble"') < html.index('id="mainMenu"')


def test_the_token_on_the_page_really_works_for_the_message_request(user, fake_chat):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    html = client.get(reverse("core:home")).content.decode()
    token = re.search(r'data-csrf-token="([^"]+)"', html).group(1)

    response = client.post(
        reverse(MESSAGE_URL), {"kind": "idle", "csrfmiddlewaretoken": token}
    )
    assert response.status_code == 200


def test_the_bubble_files_can_be_found_by_django():
    assert finders.find("core/repkin_bubble.js")
    assert finders.find("css/repkin_bubble.css")


def test_the_bubble_script_never_inserts_text_as_html():
    path = finders.find("core/repkin_bubble.js")
    source = open(path, encoding="utf-8").read()
    for dangerous in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert dangerous not in source, f"{dangerous} would let model text act as code"
    assert "textContent" in source


def test_the_page_and_the_script_agree_on_the_event_name():
    """The exercise form announces a new log; the bubble listens for it."""
    js_source = open(finders.find("core/repkin_bubble.js"), encoding="utf-8").read()
    home_source = open(get_template("core/home.html").origin.name, encoding="utf-8").read()
    assert 'new CustomEvent("exercise:logged"' in home_source
    assert "logIds: [result.log_id]" in home_source
    assert 'addEventListener("exercise:logged"' in js_source


# --- logging an exercise and hearing about it ---------------------------------

def test_submitting_an_exercise_returns_the_new_logs_id(logged_in_client, user):
    response = logged_in_client.post(reverse("core:submit_exercise"), VALID_EXERCISE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    log = ExerciseLog.objects.get(pk=body["log_id"])
    assert log.user == user
    assert (log.exercise_type, log.sets, log.reps) == ("push_ups", 3, 10)


def test_a_rejected_exercise_returns_no_log_id(logged_in_client):
    response = logged_in_client.post(
        reverse("core:submit_exercise"), {"exercise_type": "push_ups"}
    )
    assert response.status_code == 400
    assert "log_id" not in response.json()


def test_the_compliment_describes_the_exercise_that_was_just_submitted(
    logged_in_client, user, fake_chat
):
    Repkin.objects.create(owner=user, mood="happy", color="blue", name="Biscuit")
    ExerciseLog.objects.create(user=user, exercise_type="sit_ups", sets=2, reps=20)

    submitted = logged_in_client.post(reverse("core:submit_exercise"), VALID_EXERCISE).json()
    reply = logged_in_client.post(
        reverse(MESSAGE_URL), {"kind": "workout", "log_ids": str(submitted["log_id"])}
    )

    assert reply.status_code == 200
    just_logged = fake_chat["prompts"][0].split("Just logged:")[1].split("Rules:")[0]
    assert "Push Ups: 3 sets of 10 reps" in just_logged
    assert "Sit Ups" not in just_logged


def test_a_user_cannot_get_a_compliment_about_someone_elses_exercise(
    client, user, fake_chat, db
):
    other = User.objects.create_user("firebase_other", password="x")
    theirs = ExerciseLog.objects.create(user=other, exercise_type="running", distance_miles="5.00")
    client.force_login(user)

    reply = client.post(
        reverse(MESSAGE_URL), {"kind": "workout", "log_ids": str(theirs.id)}
    )

    assert reply.status_code == 200
    assert "Running" not in fake_chat["prompts"][0]
    assert "5 miles" not in fake_chat["prompts"][0]
