import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

from core.models_repkin import Repkin
from core.views import DEFAULT_REPKIN

PASSWORD = "pw12345!"


@pytest.fixture
def user(db):
    return User.objects.create_user("sam", password=PASSWORD)


@pytest.fixture
def other_user(db):
    return User.objects.create_user("alex", password=PASSWORD)


def test_first_visit_creates_repkin_for_user(client, user):
    assert not Repkin.objects.filter(owner=user).exists()

    client.force_login(user)
    client.get(reverse("core:home"))

    repkin = Repkin.objects.get(owner=user)
    assert repkin.mood == DEFAULT_REPKIN["mood"]
    assert repkin.color == DEFAULT_REPKIN["color"]


def test_second_visit_does_not_create_duplicate(client, user):
    client.force_login(user)
    client.get(reverse("core:home"))
    client.get(reverse("core:home"))

    assert Repkin.objects.filter(owner=user).count() == 1


def test_each_user_sees_their_own_repkin(client, user, other_user):
    Repkin.objects.create(owner=user, mood="happy", color="purple")
    Repkin.objects.create(owner=other_user, mood="sad", color="red")

    client.force_login(user)
    response = client.get(reverse("core:home"))
    assert response.context["repkin"].owner == user
    assert response.context["repkin"].color == "purple"

    client.force_login(other_user)
    response = client.get(reverse("core:home"))
    assert response.context["repkin"].owner == other_user
    assert response.context["repkin"].color == "red"


def test_changing_one_repkin_does_not_change_another(client, user, other_user):
    client.force_login(user)
    client.get(reverse("core:home"))
    client.force_login(other_user)
    client.get(reverse("core:home"))

    Repkin.objects.filter(owner=user).update(color="purple")

    assert Repkin.objects.get(owner=user).color == "purple"
    assert Repkin.objects.get(owner=other_user).color == DEFAULT_REPKIN["color"]


def test_user_cannot_have_two_repkins(user):
    Repkin.objects.create(owner=user, mood="happy", color="blue")

    with pytest.raises(IntegrityError):
        Repkin.objects.create(owner=user, mood="sad", color="red")


def test_deleting_user_deletes_their_repkin(user):
    Repkin.objects.create(owner=user, mood="happy", color="blue")

    user.delete()

    assert Repkin.objects.count() == 0


def test_logged_out_visit_redirects_and_creates_nothing(client, db):
    response = client.get(reverse("core:home"))

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next={reverse('core:home')}"
    assert Repkin.objects.count() == 0