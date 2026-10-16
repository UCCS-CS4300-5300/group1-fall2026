import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.models import StarterItem

PASSWORD = "integration-pw-123"


@pytest.fixture
def user(db):
    return User.objects.create_user("juan", password=PASSWORD)


def item_titles(response):
    return [item.title for item in response.context["items"]]


@pytest.mark.django_db
def test_full_user_journey_login_and_logout(client, monkeypatch):
    monkeypatch.setattr(
        "core.views.verify_firebase_id_token",
        lambda token: {"uid": "integration-uid", "email": "juan@example.com"},
    )

    # 1. Logged out: home sends you to login
    response = client.get(reverse("core:home"))
    assert response.status_code == 302

    # 2. Firebase verifies the token and Django establishes the session.
    response = client.post(
        reverse("core:firebase_session"),
        {"idToken": "signed-firebase-token"},
    )
    assert response.status_code == 200

    response = client.get(reverse("core:home"))
    assert response.request["PATH_INFO"] == reverse("core:home")
    assert b"Log out" in response.content

    # 3. Log out, should land back on the login page
    response = client.post(reverse("core:logout"), follow=True)
    assert response.request["PATH_INFO"] == reverse("login")
    assert "_auth_user_id" not in client.session

    # 4. Home is locked again
    response = client.get(reverse("core:home"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_home_gets_only_active_items_in_alphabetical_order(client, user):
    StarterItem.objects.create(title="Zebra task")
    StarterItem.objects.create(title="Alpha task")
    StarterItem.objects.create(title="Hidden task", is_active=False)
    client.force_login(user)

    response = client.get(reverse("core:home"))
    assert item_titles(response) == ["Alpha task", "Zebra task"]


@pytest.mark.django_db
def test_deactivating_item_removes_it_from_home(client, user):
    item = StarterItem.objects.create(title="Temporary task")
    client.force_login(user)
    assert item_titles(client.get(reverse("core:home"))) == ["Temporary task"]

    item.is_active = False
    item.save()
    assert item_titles(client.get(reverse("core:home"))) == []


@pytest.mark.django_db
def test_home_page_uses_home_template(client, user):
    client.force_login(user)
    response = client.get(reverse("core:home"))
    assert "core/home.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_login_page_uses_login_template(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "core/login.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_regular_user_cannot_open_admin(client, user):
    client.force_login(user)
    response = client.get(reverse("admin:index"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_superuser_can_open_admin(client, db):
    boss = User.objects.create_superuser("boss", password=PASSWORD)
    client.force_login(boss)
    response = client.get(reverse("admin:index"))
    assert response.status_code == 200