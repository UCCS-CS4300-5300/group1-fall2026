import pytest
from django.contrib.auth.models import User
from django.urls import reverse
import pytest
from django.urls import reverse
from .models import StarterItem

PASSWORD = "pw12345!"

@pytest.fixture
def user(db):
    return User.objects.create_user(
        "sam", email="sam@example.com", password=PASSWORD
    )

@pytest.fixture
def logged_in_client(client):
    user = User.objects.create_user("sam", password="pw12345!")
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
    assert b"Your project starts here." in response.content


@pytest.mark.django_db
def test_home_page_displays_only_active_items(logged_in_client):
    StarterItem.objects.create(title="Visible item", is_active=True)
    StarterItem.objects.create(title="Hidden item", is_active=False)
    response = logged_in_client.get(reverse("core:home"))
    assert b"Visible item" in response.content
    assert b"Hidden item" not in response.content
    
@pytest.mark.django_db
def logout_redirect_properly(logged_in_client):
    response = logged_in_client.get(reverse("core:login"))
    assert response.status_code == 302

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

def test_not_real_user_not_permitted_to_login(client, db):
    response = client.post(reverse("login"), {"username": "ghost", "password": f"{PASSWORD}"})
    assert response.status_code == 200
    assert b'role="alert"' in response.content
    assert "_auth_user_id" not in client.session
    
def test_no_username_not_permitted_to_login(client, db):
    response = client.post(reverse("login"), {"username": "", "password": PASSWORD})
    assert response.status_code == 200
    assert "username" in response.context["form"].errors
    assert "_auth_user_id" not in client.session
    
def test_no_username_not_permitted_to_login_produces_error_message_visual(client, db):
    response = client.post(reverse("login"), {"username": "", "password": PASSWORD})
    assert response.status_code == 200
    assert b'class="field-error"' in response.content
    assert "_auth_user_id" not in client.session
    
def test_visit_home_redirects_while_logged_out(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next={reverse('core:home')}"
    
