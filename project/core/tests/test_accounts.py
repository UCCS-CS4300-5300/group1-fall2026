import pytest
from django.contrib.auth.models import User
from django.urls import reverse

CREATE = "core:account_creation"


@pytest.mark.django_db
def test_account_creation_page_uses_firebase_registration(client):
    response = client.get(reverse(CREATE))

    assert response.status_code == 200
    for field in (b'name="email"', b'name="password"', b'name="passwordConfirm"'):
        assert field in response.content
    assert b'data-firebase-auth="signup"' in response.content
    assert b"Create account!" in response.content
    assert b'name="username"' not in response.content


@pytest.mark.django_db
def test_login_page_links_to_firebase_account_creation(client):
    response = client.get(reverse("login"))
    assert f'href="{reverse(CREATE)}"'.encode() in response.content


@pytest.mark.django_db
def test_django_cannot_create_a_password_account(client):
    response = client.post(
        reverse(CREATE),
        {
            "email": "newbie@example.com",
            "password": "S3cure-pass!",
            "passwordConfirm": "S3cure-pass!",
        },
    )

    assert response.status_code == 405
    assert not User.objects.filter(email="newbie@example.com").exists()


@pytest.mark.django_db
def test_firebase_account_creation_page_links_back_to_login(client):
    response = client.get(reverse(CREATE))
    assert f'href="{reverse("login")}"'.encode() in response.content
