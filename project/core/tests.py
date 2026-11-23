import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from core.models_repkin import Repkin
from .models import StarterItem
from unittest.mock import patch

PASSWORD = "pw12345!"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        "sam",
        email="sam@example.com",
        password=PASSWORD,
    )


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_starter_item_string_representation():
    item = StarterItem.objects.create(title="Example")
    assert str(item) == "Example"


@pytest.mark.django_db
def test_home_page_loads(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_home_page_renders_repkin_gif(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))
    assert ".gif" in response.content.decode()


@pytest.mark.django_db
def test_login_page_loads(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_firebase_token_creates_django_session(client, monkeypatch):
    monkeypatch.setattr(
        "core.views.verify_firebase_id_token",
        lambda token: {"uid": "firebase-uid-123", "email": "sam@example.com"},
    )

    response = client.post(
        reverse("core:firebase_session"),
        {"idToken": "signed-firebase-token"},
    )

    user = User.objects.get(username="firebase_firebase-uid-123")
    assert response.status_code == 200
    assert response.json() == {"redirectUrl": "/"}
    assert client.session["_auth_user_id"] == str(user.pk)
    assert user.email == "sam@example.com"
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_firebase_token_without_uid_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        "core.views.verify_firebase_id_token",
        lambda token: {"email": "sam@example.com"},
    )

    response = client.post(
        reverse("core:firebase_session"), {"idToken": "signed-firebase-token"}
    )

    assert response.status_code == 401
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_page_uses_firebase_email_form(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200
    assert b'id="firebase-login-form"' in response.content
    assert b'data-firebase-auth="login"' in response.content
    assert b'name="email"' in response.content
    assert b'name="username"' not in response.content


@pytest.mark.django_db
def test_django_password_login_is_disabled(client, user):
    response = client.post(
        reverse("login"), {"username": "sam", "password": PASSWORD}
    )

    assert response.status_code == 405
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_logout_clears_session(client, user):
    client.force_login(user)
    response = client.post(reverse("core:logout"))
    assert response.status_code == 302
    assert response["Location"] == reverse("login")
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_visit_home_redirects_while_logged_out(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next={reverse('core:home')}"


@pytest.mark.django_db
def test_logout_then_home_redirects(logged_in_client):
    logged_in_client.post(reverse("core:logout"))
    response = logged_in_client.get(reverse("core:home"))
    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/"


@pytest.mark.django_db
def test_logout_get_not_allowed(logged_in_client):
    response = logged_in_client.get(reverse("core:logout"))
    assert response.status_code == 405
    assert "_auth_user_id" in logged_in_client.session


@pytest.mark.django_db
def test_logout_message(logged_in_client):
    response = logged_in_client.post(reverse("core:logout"), follow=True)
    messages = [str(message) for message in response.context["messages"]]
    assert messages == ["You've been logged out."]


#
@pytest.mark.django_db
def test_main_menu_button_interaction(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))
    assert b'id="mainMenuButton"' in response.content


@pytest.mark.django_db
def test_home_does_not_show_the_practice_data_panel(logged_in_client):
    html = logged_in_client.get(reverse("core:home")).content.decode().lower()
    assert "practice" not in html           # no panel, form, script, or leftover handler

@pytest.fixture
def home_html(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))
    assert response.status_code == 200
    return response.content.decode()


@pytest.fixture
def menu_html(home_html):
    """Everything from the #mainMenu element onward."""
    assert 'id="mainMenu"' in home_html
    return home_html.split('id="mainMenu"', 1)[1]


def find_css_text(filename):
    path = Path(settings.BASE_DIR) / "static" / "css" / filename
    assert path.exists(), f"{path} not found"
    return path.read_text(encoding="utf-8")


@pytest.mark.django_db
def test_menu_has_panel_and_fields(menu_html):
    assert 'class="menu_panel"' in menu_html
    assert menu_html.count("menu_field") >= 10


@pytest.mark.django_db
def test_menu_logout_form_posts_to_logout(menu_html):
    assert f'action="{reverse("core:logout")}"' in menu_html
    assert "csrfmiddlewaretoken" in menu_html

#Markup Tests
@pytest.mark.django_db
def test_hud_shows_signed_in_username(home_html, user):
    assert "Signed in as" in home_html
    assert user.first_name in home_html


@pytest.mark.django_db
def test_hud_shows_repkin_mood_and_color(home_html):
    assert "mood" in home_html
    assert "color" in home_html
    
@pytest.mark.django_db
def test_menu_has_credits_button_and_overlay(home_html):
    assert 'id="creditsButton"' in home_html
    assert 'id="creditsOverlay"' in home_html
    assert 'id="creditsExitButton"' in home_html
    assert 'class="credits_overlay hidden"' in home_html

@pytest.mark.django_db
def test_menu_art_has_all_four_states(home_html):
    for attr in ("data-imp-on", "data-imp-off", "data-si-on", "data-si-off"):
        assert attr in home_html
    for el_id in ("musicBtn", "impBtn", "siBtn"):
        assert f'id="{el_id}"' in home_html

@pytest.mark.django_db
def test_home_has_locker_room_button(home_html):
    assert 'id="locker-room-btn"' in home_html
    assert 'href="/locker-room/"' in home_html
    
@pytest.mark.django_db
def test_locker_room_renders(logged_in_client):
    response = logged_in_client.get(reverse("core:locker_room"))
    assert response.status_code == 200
    assert b'<div class="stage">' in response.content
    assert b'class="user-base-gif' in response.content

@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["core:home", "core:locker_room"])
def test_menu_is_on_both_rooms(logged_in_client, url_name):
    html = logged_in_client.get(reverse(url_name)).content.decode()
    assert 'id="mainMenu"' in html
    assert 'id="mainMenuButton"' in html
    assert "js/main_menu.js" in html
    assert html.count('id="menuArt"') == 1
    
@pytest.mark.django_db
def test_welcome_popup_is_remembered_across_pages(logged_in_client, user):
    for name in ("core:home", "core:locker_room"):
        html = logged_in_client.get(reverse(name)).content.decode()
        assert f"repkinz.welcomeSeen.{user.pk}" in html
        assert "markWelcomeSeen()" in html
        
@pytest.mark.django_db
def test_home_has_no_customize_button(logged_in_client):
    html = logged_in_client.get(reverse("core:home")).content.decode()
    assert 'id="customize-btn"' not in html
    
@pytest.mark.django_db
def test_welcome_popup_is_home_only(logged_in_client):
    home = logged_in_client.get(reverse("core:home")).content.decode()
    locker = logged_in_client.get(reverse("core:locker_room")).content.decode()
    assert 'id="welcome-modal"' in home        # new user, setup not complete
    assert 'id="welcome-modal"' not in locker
    
@pytest.mark.django_db
def test_locker_room_requires_login(client):
    response = client.get(reverse("core:locker_room"))
    assert response.status_code == 302

@pytest.mark.django_db
def test_the_dumbbell_links_to_the_workout_logging_page(home_html):
    assert home_html.count('id="workout-logging-btn"') == 1
    assert 'href="/workouts/"' in home_html
    assert "practice" not in home_html.lower()


@pytest.mark.django_db
def test_the_old_single_exercise_modal_is_gone_from_home(home_html):
    assert 'id="log-exercise-btn"' not in home_html
    assert 'id="exercise-modal"' not in home_html
    assert 'id="exercise-form"' not in home_html


@pytest.mark.django_db
def test_update_repkin_name_saves(logged_in_client, user):
    r = logged_in_client.post(reverse("core:update_repkin_name"), {"name": "Chase"})
    assert r.status_code == 200
    assert r.json() == {"name": "Chase"}
    assert user.repkin.name == "Chase"


@pytest.mark.django_db
@pytest.mark.parametrize("bad", ["", "   ", "x" * 31])
def test_update_repkin_name_rejects_bad_input(logged_in_client, bad):
    r = logged_in_client.post(reverse("core:update_repkin_name"), {"name": bad})
    assert r.status_code == 400


@pytest.mark.django_db
def test_update_repkin_name_requires_login(client):
    r = client.post(reverse("core:update_repkin_name"), {"name": "Chase"})
    assert r.status_code == 302


@pytest.mark.django_db
def test_update_repkin_name_rejects_get(logged_in_client):
    assert logged_in_client.get(reverse("core:update_repkin_name")).status_code == 405
    
@pytest.mark.django_db
def test_updated_name(logged_in_client, user):
    r = logged_in_client.post(reverse("core:update_user_name"), {"name": "Bradley"})
    assert r.status_code == 200
    assert r.json() == {"name": "Bradley"}
    user.refresh_from_db()
    assert user.first_name == "Bradley"
    
@pytest.mark.django_db
def test_menu_shows_saved_repkin_name(logged_in_client):
    logged_in_client.post(reverse("core:update_repkin_name"), {"name": "Chase"})
    html = logged_in_client.get(reverse("core:home")).content.decode()
    assert 'id="cur-repkin-name"' in html
    assert 'value="Chase"' in html
    

@pytest.mark.django_db
def test_repkin_name_form_posts_to_the_route(home_html):
    assert f'action="{reverse("core:update_repkin_name")}"' in home_html
    assert 'data-display="cur-repkin-name"' in home_html
    
@pytest.mark.django_db
def test_menu_shows_saved_name(logged_in_client):
    logged_in_client.post(reverse("core:update_user_name"), {"name": "Bradley"})
    html = logged_in_client.get(reverse("core:home")).content.decode()
    assert 'id="cur-user-name"' in html
    assert 'value="Bradley"' in html
    

@pytest.mark.django_db
def test_user_name_form_posts_to_the_route(home_html):
    assert f'action="{reverse("core:update_user_name")}"' in home_html
    assert 'data-display="cur-user-name"' in home_html

@pytest.mark.django_db
def test_update_user_name_saves(logged_in_client, user):
    r = logged_in_client.post(reverse("core:update_user_name"), {"name": "Sam"})
    assert r.json() == {"name": "Sam"}
    user.refresh_from_db()
    assert user.first_name == "Sam"

@pytest.mark.django_db
def test_menu_shows_first_name_not_firebase_id(logged_in_client, user):
    user.first_name = "Sam"
    user.save()
    html = logged_in_client.get(reverse("core:home")).content.decode()
    assert 'id="cur-user-name"' in html
    assert 'value="Sam"' in html
    
@pytest.mark.django_db
def test_menu_has_height_weight_forms(home_html):
    for el_id in ("cur-height", "cur-weight"):
            assert f'id="{el_id}"' in home_html
    assert 'data-profile="height_cm"' in home_html
    assert 'data-profile="weight_kg"' in home_html
    assert "js/unit_conversion.js" in home_html and "js/profile.js" in home_html
    assert home_html.index("unit_conversion.js") < home_html.index("profile.js")
    
@pytest.mark.django_db
def test_summary_mirrors_name_boxes(home_html):
    assert 'data-mirror="cur-user-name"' in home_html
    assert 'data-mirror="cur-repkin-name"' in home_html
    
#Unit Tests (SI and Imperial)
def _fb_user(client, django_user_model):
    client.force_login(django_user_model.objects.create_user("firebase_abc123"))


@pytest.mark.django_db
@pytest.mark.parametrize("field,value", [
    ("height_cm", "50"), ("height_cm", "250"),     # limits are inclusive
    ("weight_kg", "10"), ("weight_kg", "650"),
])
def test_profile_accepts_boundary_values(client, django_user_model, field, value):
    _fb_user(client, django_user_model)
    with patch("core.views.get_firestore_client"):
        assert client.post(reverse("core:profile_data"), {field: value}).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("field,value", [
    ("height_cm", "49.9"), ("height_cm", "250.1"),
    ("weight_kg", "9.9"), ("weight_kg", "650.1"),
    ("height_cm", "inf"), ("weight_kg", "nan"), ("height_cm", ""),
])
def test_profile_rejects_out_of_range(client, django_user_model, field, value):
    _fb_user(client, django_user_model)
    with patch("core.views.get_firestore_client") as fake:
        r = client.post(reverse("core:profile_data"), {field: value})
    assert r.status_code == 400
    fake.return_value.collection.return_value.document.return_value.set.assert_not_called()


@pytest.mark.django_db
def test_profile_rounds_to_one_decimal(client, django_user_model):
    _fb_user(client, django_user_model)
    with patch("core.views.get_firestore_client") as fake:
        ref = fake.return_value.collection.return_value.document.return_value
        client.post(reverse("core:profile_data"), {"weight_kg": "74.8349"})
    ref.set.assert_called_once_with({"weight_kg": 74.8}, merge=True)