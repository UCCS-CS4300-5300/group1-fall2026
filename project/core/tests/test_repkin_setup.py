import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.models_repkin import Repkin

PASSWORD = "pw12345!"
SETUP = "core:repkin_setup"
HOME = "core:home"

VALID = {
    "name": "Biscuit",
    "color": "purple",
    "favorite_activity": "Running",
    "favorite_food": "Bananas",
}


@pytest.fixture
def user(db):
    return User.objects.create_user("sam", password=PASSWORD)


@pytest.fixture
def other_user(db):
    return User.objects.create_user("alex", password=PASSWORD)


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


# The welcome modal on the home page vvvvvvvvvv

def test_new_user_sees_welcome_modal(logged_in_client):
    response = logged_in_client.get(reverse(HOME))
    assert b'id="welcome-modal"' in response.content
    assert b"Welcome to RepKinz!" in response.content
    assert b"your RepKin is eager to meet you" in response.content


def test_welcome_modal_has_create_button(logged_in_client):
    response = logged_in_client.get(reverse(HOME))
    assert b'id="create-repkin-btn"' in response.content


def test_welcome_modal_hidden_once_setup_is_complete(logged_in_client, user):
    Repkin.objects.create(owner=user, mood="happy", color="blue", setup_complete=True)
    response = logged_in_client.get(reverse(HOME))
    assert b'id="welcome-modal"' not in response.content


# The setup modal on the home page vvvvvvvvvvvvvvvvvvvvvvv

def test_home_contains_setup_form_posting_to_setup_url(logged_in_client):
    response = logged_in_client.get(reverse(HOME))
    assert b'id="setup-modal"' in response.content
    assert f'action="{reverse(SETUP)}"'.encode() in response.content
    for field in (b'name="name"', b'name="color"',
                  b'name="favorite_activity"', b'name="favorite_food"'):
        assert field in response.content


def test_customize_button_is_always_available(logged_in_client, user):
    Repkin.objects.create(owner=user, mood="happy", color="blue", setup_complete=True)
    response = logged_in_client.get(reverse(HOME))
    assert b'id="customize-btn"' in response.content
    assert b'id="setup-modal"' in response.content


def test_fresh_home_page_shows_no_form_errors(logged_in_client):
    response = logged_in_client.get(reverse(HOME))
    assert b'class="field-error"' not in response.content


# Submitting the form vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_setup_url_requires_login(client, db):
    response = client.post(reverse(SETUP), VALID)
    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next={reverse(SETUP)}"


def test_visiting_setup_url_directly_goes_home(logged_in_client):
    response = logged_in_client.get(reverse(SETUP))
    assert response.status_code == 302
    assert response["Location"] == reverse(HOME)


def test_valid_setup_saves_to_users_own_repkin(logged_in_client, user):
    response = logged_in_client.post(reverse(SETUP), VALID)
    assert response.status_code == 302
    assert response["Location"] == reverse(HOME)

    repkin = Repkin.objects.get(owner=user)
    assert repkin.name == "Biscuit"
    assert repkin.color == "purple"
    assert repkin.favorite_activity == "Running"
    assert repkin.favorite_food == "Bananas"
    assert repkin.setup_complete is True


def test_welcome_modal_gone_after_finishing_setup(logged_in_client):
    response = logged_in_client.post(reverse(SETUP), VALID, follow=True)
    assert response.request["PATH_INFO"] == reverse(HOME)
    assert b'id="welcome-modal"' not in response.content


def test_setup_does_not_touch_another_users_repkin(client, user, other_user):
    client.force_login(other_user)
    client.get(reverse(HOME))

    client.force_login(user)
    client.post(reverse(SETUP), VALID)

    theirs = Repkin.objects.get(owner=other_user)
    assert theirs.name == ""
    assert theirs.color != "purple"
    assert theirs.setup_complete is False


def test_setup_modal_can_be_reused_to_change_color_later(logged_in_client, user):
    logged_in_client.post(reverse(SETUP), VALID)
    logged_in_client.post(reverse(SETUP), {**VALID, "color": "red"})

    repkin = Repkin.objects.get(owner=user)
    assert repkin.color == "red"
    assert repkin.name == "Biscuit"
    assert repkin.setup_complete is True


# When the form is invalid, the user stays on the home page vvvvvvvvvvvvvvvvvvvvvvv

def test_blank_name_reopens_modal_on_home_page_with_error(logged_in_client, user):
    response = logged_in_client.post(reverse(SETUP), {**VALID, "name": ""})

    assert response.status_code == 200
    assert "core/home.html" in [t.name for t in response.templates]
    assert response.context["open_setup"] is True
    assert "name" in response.context["setup_form"].errors
    assert b'class="field-error"' in response.content

    repkin = Repkin.objects.get(owner=user)
    assert repkin.setup_complete is False
    assert repkin.name == ""


def test_color_outside_the_list_is_rejected(logged_in_client):
    response = logged_in_client.post(reverse(SETUP), {**VALID, "color": "plaid"})
    assert response.status_code == 200
    assert "color" in response.context["setup_form"].errors


def test_failed_submit_does_not_show_unsaved_values(logged_in_client, user):
    logged_in_client.get(reverse(HOME))
    before = Repkin.objects.get(owner=user).color

    response = logged_in_client.post(reverse(SETUP), {**VALID, "name": ""})

    assert response.context["repkin"].color == before
    assert Repkin.objects.get(owner=user).color == before
