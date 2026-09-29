import pytest
from django.urls import reverse
from core.models import StarterItem
@pytest.mark.django_db
def test_starter_item_string_representation():
    item = StarterItem.objects.create(title="Example")
    assert str(item) == "Example"
@pytest.mark.django_db
def test_home_page_loads(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert b"Your project starts here." in response.content
@pytest.mark.django_db
def test_home_page_displays_only_active_items(client):
    StarterItem.objects.create(title="Visible item", is_active=True)
    StarterItem.objects.create(title="Hidden item", is_active=False)
    response = client.get(reverse("core:home"))
    assert b"Visible item" in response.content
    assert b"Hidden item" not in response.content
