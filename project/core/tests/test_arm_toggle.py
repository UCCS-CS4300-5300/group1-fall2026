import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.repkin_looks import ARM_VERSIONS, next_arm_level, parse_arm_level

LOCKER = "core:locker_room"


@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user("flexer", password="pw12345!")
    client.force_login(user)
    return client


def gif_url(level):
    return f"/static/{ARM_VERSIONS[level]}"


# The list of arm versions vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_there_are_four_arm_versions_in_order():
    assert len(ARM_VERSIONS) == 4
    assert "Base" in ARM_VERSIONS[0]
    assert "Arms1" in ARM_VERSIONS[1]
    assert "Arms2" in ARM_VERSIONS[2]
    assert "Arms3" in ARM_VERSIONS[3]


# Reading the ?arms= value vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

@pytest.mark.parametrize("value, expected", [("0", 0), ("1", 1), ("3", 3)])
def test_valid_arm_levels_are_kept(value, expected):
    assert parse_arm_level(value) == expected


@pytest.mark.parametrize("value", [None, "", "banana", "-1", "4", "1.5"])
def test_invalid_arm_levels_fall_back_to_no_arms(value):
    assert parse_arm_level(value) == 0


# Moving to the next version vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

@pytest.mark.parametrize("level, expected", [(0, 1), (1, 2), (2, 3)])
def test_next_arm_level_moves_forward(level, expected):
    assert next_arm_level(level) == expected


def test_next_arm_level_wraps_after_the_last_version():
    assert next_arm_level(3) == 0


# The locker room page vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_locker_room_starts_with_no_arms(logged_in_client):
    response = logged_in_client.get(reverse(LOCKER))

    assert response.status_code == 200
    assert response.context["arm_level"] == 0
    content = response.content.decode()
    assert gif_url(0) in content
    assert 'href="?arms=1"' in content


def test_locker_room_shows_the_chosen_arm_version(logged_in_client):
    response = logged_in_client.get(reverse(LOCKER), {"arms": "2"})

    content = response.content.decode()
    assert gif_url(2) in content
    assert gif_url(0) not in content
    assert 'href="?arms=3"' in content


def test_arrow_on_last_version_goes_back_to_no_arms(logged_in_client):
    response = logged_in_client.get(reverse(LOCKER), {"arms": "3"})

    content = response.content.decode()
    assert gif_url(3) in content
    assert 'href="?arms=0"' in content


def test_invalid_arms_value_shows_no_arms_instead_of_crashing(logged_in_client):
    response = logged_in_client.get(reverse(LOCKER), {"arms": "banana"})

    assert response.status_code == 200
    assert response.context["arm_level"] == 0
    assert gif_url(0) in response.content.decode()


def test_clicking_through_every_version_comes_back_to_the_start(logged_in_client):
    seen = []
    level = 0
    for _ in range(len(ARM_VERSIONS) + 1):
        response = logged_in_client.get(reverse(LOCKER), {"arms": str(level)})
        seen.append(response.context["arm_level"])
        level = response.context["next_arms"]

    assert seen == [0, 1, 2, 3, 0]


def test_locker_room_requires_login(client, db):
    response = client.get(reverse(LOCKER))
    assert response.status_code == 302
