import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

PASSWORD = "pw12345!"
CREATE = "core:account_creation"

NEW_ACCOUNT = {
    "username": "newbie",
    "email": "newbie@example.com",
    "password1": "S3cure-pass!",
    "password2": "S3cure-pass!",
}


@pytest.fixture
def user(db):
    return User.objects.create_user("sam", email="sam@example.com", password=PASSWORD)


@pytest.fixture
def other_user(db):
    return User.objects.create_user("alex", email="alex@example.com", password=PASSWORD)


# Account creation page vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_account_creation_page_loads(client, db):
    response = client.get(reverse(CREATE))
    assert response.status_code == 200
    for field in (b'name="username"', b'name="email"',
                  b'name="password1"', b'name="password2"'):
        assert field in response.content
    assert b"Create account!" in response.content
    assert b'class="field-error"' not in response.content


def test_login_page_links_to_account_creation(client, db):
    response = client.get(reverse("login"))
    assert f'href="{reverse(CREATE)}"'.encode() in response.content


def test_valid_signup_creates_user_with_email(client, db):
    response = client.post(reverse(CREATE), NEW_ACCOUNT)
    assert response.status_code == 302
    assert response["Location"] == reverse("core:home")

    created = User.objects.get(username="newbie")
    assert created.email == "newbie@example.com"


def test_new_account_password_is_hashed(client, db):
    client.post(reverse(CREATE), NEW_ACCOUNT)
    created = User.objects.get(username="newbie")
    assert created.password != NEW_ACCOUNT["password1"]
    assert created.check_password(NEW_ACCOUNT["password1"])
    assert not created.check_password("wrong-password")


def test_new_account_is_logged_in_and_lands_on_home(client, db):
    response = client.post(reverse(CREATE), NEW_ACCOUNT, follow=True)
    created = User.objects.get(username="newbie")
    assert client.session["_auth_user_id"] == str(created.pk)
    assert response.status_code == 200
    assert response.context["user"] == created


def test_new_account_sees_welcome_modal_on_first_home_visit(client, db):
    response = client.post(reverse(CREATE), NEW_ACCOUNT, follow=True)
    assert b'id="welcome-modal"' in response.content


def test_new_account_can_log_out_and_back_in(client, db):
    client.post(reverse(CREATE), NEW_ACCOUNT)
    client.post(reverse("core:logout"))
    assert "_auth_user_id" not in client.session

    response = client.post(
        reverse("login"),
        {"username": "newbie", "password": NEW_ACCOUNT["password1"]},
    )
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_mismatched_passwords_are_rejected(client, db):
    response = client.post(reverse(CREATE), {**NEW_ACCOUNT, "password2": "different-1!"})
    assert response.status_code == 200
    assert "password2" in response.context["form"].errors
    assert b'class="field-error"' in response.content
    assert not User.objects.filter(username="newbie").exists()
    assert "_auth_user_id" not in client.session


def test_duplicate_username_is_rejected(client, user):
    response = client.post(reverse(CREATE), {**NEW_ACCOUNT, "username": "sam"})
    assert response.status_code == 200
    assert "username" in response.context["form"].errors
    assert User.objects.filter(username="sam").count() == 1
    assert "_auth_user_id" not in client.session


def test_invalid_email_is_rejected(client, db):
    response = client.post(reverse(CREATE), {**NEW_ACCOUNT, "email": "not-an-email"})
    assert response.status_code == 200
    assert "email" in response.context["form"].errors
    assert not User.objects.exists()


@pytest.mark.parametrize("field", ["username", "email", "password1", "password2"])
def test_every_field_is_required(client, db, field):
    response = client.post(reverse(CREATE), {**NEW_ACCOUNT, field: ""})
    assert response.status_code == 200
    assert field in response.context["form"].errors
    assert not User.objects.exists()


# Login: the edge cases vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_login_page_loads(client, db):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b'name="username"' in response.content
    assert b'name="password"' in response.content


def test_login_sends_user_to_next_page(client, user):
    response = client.post(
        reverse("login"),
        {"username": "sam", "password": PASSWORD, "next": reverse(CREATE)},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse(CREATE)


def test_login_ignores_next_pointing_to_another_site(client, user):
    response = client.post(
        reverse("login"),
        {"username": "sam", "password": PASSWORD, "next": "https://evil.example/"},
    )
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_blank_password_is_rejected(client, user):
    response = client.post(reverse("login"), {"username": "sam", "password": ""})
    assert response.status_code == 200
    assert "password" in response.context["form"].errors
    assert "_auth_user_id" not in client.session


def test_inactive_user_cannot_log_in(client, user):
    user.is_active = False
    user.save()
    response = client.post(reverse("login"), {"username": "sam", "password": PASSWORD})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_login_session_belongs_to_the_right_user(client, user, other_user):
    client.post(reverse("login"), {"username": "alex", "password": PASSWORD})
    response = client.get(reverse("core:home"))
    assert response.context["user"] == other_user
    assert response.context["user"] != user


# Accounts and passwords in the database vvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_password_is_stored_hashed(user):
    assert user.password != PASSWORD
    assert user.check_password(PASSWORD)
    assert not user.check_password("wrong-password")


def test_user_and_email_persist_in_database(user):
    fresh = User.objects.get(username="sam")
    assert fresh.email == "sam@example.com"
    assert fresh.check_password(PASSWORD)


def test_duplicate_username_is_blocked_by_database(user):
    with pytest.raises(IntegrityError):
        User.objects.create_user("sam", password="x")


# Logout: the edge cases vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_logout_get_request_does_not_log_user_out(client, user):
    client.force_login(user)
    response = client.get(reverse("core:logout"))
    assert response.status_code == 405
    assert "_auth_user_id" in client.session


def test_logout_while_already_logged_out_still_goes_to_login(client, db):
    response = client.post(reverse("core:logout"))
    assert response.status_code == 302
    assert response["Location"] == reverse("login")