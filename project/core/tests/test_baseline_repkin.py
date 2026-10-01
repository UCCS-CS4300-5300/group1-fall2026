import pytest

from core.models_repkin import Repkin


@pytest.mark.django_db
def test_repkin_can_store_mood():
    repkin = Repkin.objects.create(
        mood="happy",
        color="blue",
    )

    assert repkin.mood == "happy"


@pytest.mark.django_db
def test_repkin_can_store_selected_color():
    repkin = Repkin.objects.create(
        mood="happy",
        color="green",
    )

    assert repkin.color == "green"