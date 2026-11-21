import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.models_repkin import Repkin


@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user("tired-toggle-user", password="pw12345!")
    Repkin.objects.create(owner=user, mood="content", color="green")
    client.force_login(user)
    return client


@pytest.mark.parametrize(
    ("return_to", "expected_url"),
    [
        ("home", "core:home"),
        ("locker_room", "core:locker_room"),
    ],
)
def test_tired_button_toggles_saved_state_and_returns_to_page(
    logged_in_client, return_to, expected_url
):
    url = reverse("core:toggle_repkin_tired")

    response = logged_in_client.post(url, {"return_to": return_to})

    assert response.status_code == 302
    assert response["Location"] == reverse(expected_url)
    repkin = Repkin.objects.get(owner__username="tired-toggle-user")
    assert repkin.is_tired is True

    logged_in_client.post(url, {"return_to": return_to})
    repkin.refresh_from_db()
    assert repkin.is_tired is False


def test_tired_button_is_rendered_on_both_pages_and_reflects_state(logged_in_client):
    for page_name, return_to in (
        ("core:home", "home"),
        ("core:locker_room", "locker_room"),
    ):
        response = logged_in_client.get(reverse(page_name))
        content = response.content.decode()
        assert f'name="return_to" value="{return_to}"' in content
        assert "Set tired" in content

    logged_in_client.post(
        reverse("core:toggle_repkin_tired"),
        {"return_to": "home"},
    )
    for page_name in ("core:home", "core:locker_room"):
        content = logged_in_client.get(reverse(page_name)).content.decode()
        assert "Set not tired" in content
