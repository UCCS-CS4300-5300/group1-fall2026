import pytest
from django.core.exceptions import ValidationError
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


@pytest.mark.django_db
@pytest.mark.parametrize(("initial_state", "expected_state"), [(False, True), (True, False)])
def test_toggle_tired_saves_the_opposite_state(initial_state, expected_state):
    repkin = Repkin.objects.create(
        mood="happy",
        color="green",
        is_tired=initial_state,
    )

    assert repkin.toggle_tired() is expected_state
    repkin.refresh_from_db()
    assert repkin.is_tired is expected_state


@pytest.mark.django_db
def test_repkin_cannot_have_blank_mood():
    repkin = Repkin(
        mood="",
        color="blue",
    )

    with pytest.raises(ValidationError):
        repkin.full_clean()


@pytest.mark.django_db
def test_repkin_cannot_have_blank_color():
    repkin = Repkin(
        mood="happy",
        color="",
    )

    with pytest.raises(ValidationError):
        repkin.full_clean()