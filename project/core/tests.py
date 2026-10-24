from core.models_repkin import Repkin
import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from .models import StarterItem
PASSWORD = "pw12345!"

@pytest.fixture
def user(db):
    return User.objects.create_user(
        "sam", email="sam@example.com", password=PASSWORD
    )

@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client

# TESTS BELOW THIS LINE ============================#
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
    content = response.content.decode()
    assert ".gif" in content

@pytest.mark.django_db
def test_logout_redirect_properly(logged_in_client):
    response = logged_in_client.get(reverse("login"))
    assert response.status_code == 200

@pytest.mark.django_db
def test_valid_login_redirects_home(client, user):
    response = client.post(
        reverse("login"), {"username": "sam", "password": PASSWORD}
    )
    assert response.status_code == 302
    assert response["Location"] == "/"
    assert client.session["_auth_user_id"] == str(user.pk)

@pytest.mark.django_db
def test_logout_clears_session(client, user):
    client.force_login(user)
    response = client.post(reverse("core:logout"))
    assert response.status_code == 302
    assert response["Location"] == reverse("login")
    assert "_auth_user_id" not in client.session

@pytest.mark.django_db
def test_incorrect_password_not_permitted_to_login(client):
    response = client.post(reverse("login"), {"username": "sam", "password": "wrong-password"})
    assert response.status_code == 200
    assert b"form-error" in response.content
    assert "_auth_user_id" not in client.session

@pytest.mark.django_db
def test_not_real_user_not_permitted_to_login(client, db):
    response = client.post(reverse("login"), {"username": "ghost", "password": f"{PASSWORD}"})
    assert response.status_code == 200
    assert b'role="alert"' in response.content
    assert "_auth_user_id" not in client.session

@pytest.mark.django_db
def test_no_username_not_permitted_to_login(client, db):
    response = client.post(reverse("login"), {"username": "", "password": PASSWORD})
    assert response.status_code == 200
    assert "username" in response.context["form"].errors
    assert "_auth_user_id" not in client.session

@pytest.mark.django_db
def test_no_username_not_permitted_to_login_produces_error_message_visual(client, db):
    response = client.post(reverse("login"), {"username": "", "password": PASSWORD})
    assert response.status_code == 200
    assert b'class="field-error"' in response.content
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
    messages = [str(m) for m in response.context["messages"]]
    assert messages == ["You've been logged out."]
    
@pytest.mark.django_db
def test_main_menu_button_interaction(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))
    content = response.content.decode()
    assert 'id="mainMenuButton"' in content

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

    








