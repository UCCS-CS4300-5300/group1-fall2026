import json
import re

import pytest
from django.contrib.auth.models import User
from django.templatetags.static import static
from django.urls import reverse

from core.models_repkin import Repkin
from core.repkin_looks import LEVEL_COUNT, sprite_urls_for

LOCKER = "core:locker_room"


@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user("flexer", password="pw12345!")
    # Full strength and endurance unlock every arm and leg level, so these
    # tests check the page controls, not the unlock rules.
    Repkin.objects.create(
        owner=user, mood="content", color="green", strength=300, endurance=300
    )
    client.force_login(user)
    return client


# Read the sprite URL matrix embedded in the locker-room page.
def gif_urls_on_page(content):
    match = re.search(
        r'<script id="sprite-gif-urls" type="application/json">(.*?)</script>',
        content,
        re.S,
    )
    assert match, "The arm gif list was not found on the page"
    return json.loads(match.group(1))


# Check that the browser receives every sprite combination.
def test_page_sends_every_arm_and_leg_combination(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    expected = {
        arms: {legs: static(path) for legs, path in versions.items()}
        for arms, versions in sprite_urls_for("green").items()
    }
    assert gif_urls_on_page(content) == expected
    assert all(len(versions) == LEVEL_COUNT for versions in expected.values())


# Check that the locker room loads the sprite-control script.
def test_page_loads_the_arm_toggle_script(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert "core/arm_toggle.js" in content


def test_page_loads_the_functional_settings_menu(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert 'data-profile="height_cm"' in content
    assert 'data-profile="weight_kg"' in content
    assert 'id="siBtn"' in content
    assert 'id="impBtn"' in content
    assert "js/profile.js" in content


# Check that both controls receive the saved limb levels.
def test_controls_know_the_saved_arm_and_leg_levels(logged_in_client):
    logged_in_client.post(
        reverse("core:update_repkin_sprite"),
        {"arms_level": "2", "legs_level": "3"},
    )
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert 'data-arm-level="2"' in content
    assert 'data-leg-level="3"' in content


# Check that both controls and their save endpoint are rendered.
def test_limb_controls_and_save_url_are_present(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert 'id="arms-arrow-btn"' in content
    assert 'id="legs-arrow-btn"' in content
    assert 'id="sprite-gif-urls"' in content
    assert 'action="/repkin/sprite/"' in content


# Check that each control links to its next level.
def test_limb_control_links_have_next_levels(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert 'href="?arms=1"' in content
    assert 'href="?legs=1"' in content
