import json
import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.repkin_looks import ARM_VERSIONS

LOCKER = "core:locker_room"


@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user("flexer", password="pw12345!")
    client.force_login(user)
    return client


def gif_urls_on_page(content):
    match = re.search(
        r'<script id="arm-gif-urls" type="application/json">(.*?)</script>',
        content,
        re.S,
    )
    assert match, "The arm gif list was not found on the page"
    return json.loads(match.group(1))


def test_page_sends_every_arm_gif_in_order(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert gif_urls_on_page(content) == [f"/static/{path}" for path in ARM_VERSIONS]


def test_page_loads_the_arm_toggle_script(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert "core/arm_toggle.js" in content


def test_arrow_knows_the_current_arm_level(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER), {"arms": "2"}).content.decode()
    assert 'data-arm-level="2"' in content


def test_arrow_still_works_as_a_link_without_javascript(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER), {"arms": "3"}).content.decode()
    assert 'href="?arms=0"' in content


def test_invalid_arms_value_gives_level_zero_to_the_script(logged_in_client):
    content = logged_in_client.get(reverse(LOCKER), {"arms": "banana"}).content.decode()
    assert 'data-arm-level="0"' in content
