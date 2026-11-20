"""The workout logging page (core/templates/core/workout_logging.html)."""

import re
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.template.loader import get_template
from django.urls import reverse

from core.exercises import SECTIONS

PAGE_URL = "/workouts/"
SCRIPT = Path(__file__).resolve().parents[2] / "static" / "js" / "workout_builder.js"


@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user(username="lifter", password="test_password_123")
    client.force_login(user)
    return client


@pytest.fixture
def page(logged_in_client):
    response = logged_in_client.get(reverse("core:workout_logging"))
    assert response.status_code == 200
    return response.content.decode()


def test_page_lives_at_workouts():
    assert reverse("core:workout_logging") == PAGE_URL


@pytest.mark.django_db
def test_page_requires_login(client):
    response = client.get(PAGE_URL)
    assert response.status_code == 302


@pytest.mark.django_db
def test_page_only_allows_get(logged_in_client):
    assert logged_in_client.post(PAGE_URL).status_code == 405


def test_page_uses_its_own_template(logged_in_client):
    response = logged_in_client.get(PAGE_URL)
    assert "core/workout_logging.html" in [t.name for t in response.templates]


def test_page_has_the_two_top_buttons(page):
    assert "Create new workout" in page
    assert "Load workout preset" in page


def test_page_points_the_script_at_the_real_endpoints(page):
    assert 'data-catalog-url="/workouts/catalog/"' in page
    assert 'data-presets-url="/workouts/presets/"' in page
    assert 'data-save-url="/workouts/presets/save/"' in page
    assert 'data-detail-url="/workouts/presets/0/"' in page
    assert 'data-delete-url="/workouts/presets/0/delete/"' in page
    assert 'data-log-url="/workouts/log/"' in page
    assert 'data-home-url="/"' in page


def test_page_carries_a_csrf_token_for_the_script(page):
    match = re.search(r'data-csrf-token="([^"]+)"', page)
    assert match and len(match.group(1)) >= 32


def test_page_loads_its_script_and_styles(page):
    assert "js/workout_builder.js" in page
    assert "css/workout_logging.css" in page


def test_page_links_back_to_the_workout_room(page):
    assert 'class="wl-back"' in page
    assert 'href="/"' in page


def test_page_has_save_and_log_buttons_and_both_are_switched_on(page):
    for button_id in ("wl-save", "wl-log"):
        button = re.search(rf'<button[^>]*id="{button_id}"[^>]*>', page).group(0)
        assert "disabled" not in button


def test_every_element_the_script_looks_up_exists_in_the_template(page):
    """The script finds its page parts by id. A renamed id would break it silently."""
    wanted = set(re.findall(r'\$\("([\w-]+)"\)', SCRIPT.read_text(encoding="utf-8")))
    assert "wl-create" in wanted and "wl-picker-form" in wanted    # the search found something
    missing = sorted(name for name in wanted if f'id="{name}"' not in page)
    assert missing == []


def test_the_page_does_not_include_the_old_modal(page):
    assert 'id="exercise-modal"' not in page


def test_the_four_section_names_come_from_the_catalog_not_the_template():
    # The headings are drawn by the script from the catalog endpoint, so the template
    # must not hard-code a second copy that could drift.
    source = get_template("core/workout_logging.html").template.source
    for title in SECTIONS.values():
        assert title not in source


def test_page_has_the_shared_banner_home_button_and_hamburger(page):
    assert "img/workout_logging_banner.png" in page
    assert 'id="mainMenuButton"' in page
    assert 'id="mainMenu"' in page
    assert "js/main_menu.js" in page
    # The old text link and the big centred logo are gone.
    assert "Workout room</a>" not in page
    assert 'class="wl-logo"' not in page


def test_page_plays_the_same_track_as_the_home_page(page, client):
    from django.urls import reverse
    track = "audio/ES_Casanova_Instrumental.mp3"
    assert f'id="bg-music" src="/static/{track}"' in page
    assert track in client.get(reverse("core:home")).content.decode()
