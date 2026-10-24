import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from .models import StarterItem

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


@pytest.mark.django_db
def test_main_menu_button_interaction(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))
    assert b'id="mainMenuButton"' in response.content


@pytest.mark.django_db
def test_home_contains_practice_data_form(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))
    assert b'id="practice-data-form"' in response.content
    assert f'action="{reverse("core:practice_data")}"'.encode() in response.content

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
def test_menu_shows_current_username(menu_html, user):
    assert f'value="{user.username}"' in menu_html
    assert "readonly" in menu_html


@pytest.mark.django_db
def test_menu_password_fields_are_masked(menu_html):
    assert menu_html.count('type="password"') >= 2


@pytest.mark.django_db
def test_menu_logout_form_posts_to_logout(menu_html):
    assert f'action="{reverse("core:logout")}"' in menu_html
    assert "csrfmiddlewaretoken" in menu_html

#Markup Tests
@pytest.mark.django_db
def test_hud_shows_signed_in_username(home_html, user):
    assert "Signed in as" in home_html
    assert user.username in home_html


@pytest.mark.django_db
def test_hud_shows_repkin_mood_and_color(home_html):
    assert "mood" in home_html
    assert "color" in home_html

    









