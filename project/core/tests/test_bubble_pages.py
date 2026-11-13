import re

import pytest
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse

from core.models_repkin import Repkin
from core.repkin_voice import KINDS

HOME = "core:home"
LOCKER = "core:locker_room"


@pytest.fixture
def user(db):
    return User.objects.create_user("firebase_abc123", password="x")


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    Repkin.objects.create(owner=user, mood="happy", color="blue", name="Biscuit", setup_complete=True)
    return client


def page(client, url_name):
    return client.get(reverse(url_name)).content.decode()


def bubble_tag(html):
    return re.search(r'<div id="repkin-bubble"[^>]*>', html, re.S).group(0)


def allowed_kinds(html):
    value = re.search(r'data-messages="([^"]*)"', bubble_tag(html)).group(1)
    return [kind.strip() for kind in value.split(",")]


# --- which messages each room allows -------------------------------------------

INCLUDE_HINT = (
    'Check the {% include "core/_repkin_bubble.html" ... %} line in locker_room.html. '
    'It should read exactly: '
    '{% include "core/_repkin_bubble.html" with bubble_kinds="idle" bubble_left="42%" %} '
    "(a misspelled option name is silently ignored by Django)"
)


def test_the_workout_room_allows_all_three_kinds_of_message(logged_in_client):
    assert allowed_kinds(page(logged_in_client, HOME)) == ["greeting", "workout", "idle"]


def test_the_locker_room_allows_only_idle_messages(logged_in_client):
    assert allowed_kinds(page(logged_in_client, LOCKER)) == ["idle"], INCLUDE_HINT


@pytest.mark.parametrize("url_name", [HOME, LOCKER])
def test_every_kind_a_page_asks_for_is_one_the_server_understands(logged_in_client, url_name):
    """Catches typos such as 'idel' that would make a page silently ask for nothing."""
    for kind in allowed_kinds(page(logged_in_client, url_name)):
        assert kind in KINDS


# --- exactly one bubble per page ----------------------------------------------

#@pytest.mark.parametrize("url_name", [HOME, LOCKER])
#def test_each_page_has_exactly_one_bubble_and_one_script(logged_in_client, url_name):
    """Two copies would run the script twice, so every message would be requested twice."""
    '''html = page(logged_in_client, url_name)
        assert html.count('id="repkin-bubble"') == 1, (
            "The bubble appears more than once. Look for a repeated "
            '{% include "core/_repkin_bubble.html" ... %} line.'
        )'''
    #html = page(logged_in_client, url_name)
    #assert html.count("core/repkin_bubble.js") == 1
    #assert html.count("css/repkin_bubble.css") == 1


# --- the bubble is really on the locker room page ------------------------------

def test_the_locker_room_page_loads_the_bubble_script_and_styles(logged_in_client):
    html = page(logged_in_client, LOCKER)
    assert "core/repkin_bubble.js" in html
    assert "css/repkin_bubble.css" in html
    assert f'data-message-url="{reverse("core:repkin_message")}"' in html


def test_the_locker_room_bubble_starts_hidden_inside_the_stage(logged_in_client):
    html = page(logged_in_client, LOCKER)
    assert re.search(r"\bhidden\b", bubble_tag(html))
    assert html.index('class="stage"') < html.index('id="repkin-bubble"')
    assert html.index('id="repkin-bubble"') < html.index('id="mainMenu"')


def test_the_bubble_points_at_the_repkin_in_each_room(logged_in_client):
    assert "--bubble-left: 50%" in bubble_tag(page(logged_in_client, HOME))
    assert "--bubble-left: 42%" in bubble_tag(page(logged_in_client, LOCKER)), INCLUDE_HINT


def test_the_bubble_stylesheet_reads_the_position_variable():
    css = open(finders.find("css/repkin_bubble.css"), encoding="utf-8").read()
    assert "var(--bubble-left, 50%)" in css


def test_the_token_on_the_locker_room_page_really_works(user, monkeypatch):
    from core import repkin_voice

    monkeypatch.setattr(repkin_voice, "chat", lambda messages: "Hello from the locker room!")
    Repkin.objects.create(owner=user, mood="happy", color="blue", name="Biscuit", setup_complete=True)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    html = client.get(reverse(LOCKER)).content.decode()
    token = re.search(r'data-csrf-token="([^"]+)"', html).group(1)

    response = client.post(
        reverse("core:repkin_message"), {"kind": "idle", "csrfmiddlewaretoken": token}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Hello from the locker room!"


def test_the_locker_room_does_not_use_up_the_greeting_on_the_server(
    user, logged_in_client, monkeypatch
):
    """Loading the page never touches the greeting. Only a greeting request does."""
    from core.views_message import GREETING_PENDING_KEY

    session = logged_in_client.session
    session[GREETING_PENDING_KEY] = True
    session.save()
    page(logged_in_client, LOCKER)
    page(logged_in_client, LOCKER)
    assert logged_in_client.session[GREETING_PENDING_KEY] is True