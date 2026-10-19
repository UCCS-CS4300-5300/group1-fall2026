import pytest
from core.forms_exercise import ExerciseInputForm
from django.contrib.auth.models import User
from django.urls import reverse
from html.parser import HTMLParser

@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user(
        username="exercise_tester",
        password="test_password_123",
    )
    client.force_login(user)
    return client

def test_home_contains_exercise_button(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b'id="log-exercise-btn"' in response.content

def test_home_contains_exercise_modal(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b'id="exercise-modal"' in response.content
    assert b"<dialog" in response.content

def test_exercise_button_targets_modal(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b'data-exercise-modal="exercise-modal"' in response.content

def test_exercise_modal_contains_cancel_button(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    content = response.content.decode()

    assert 'id="cancel-exercise-btn"' in content
    assert 'type="button"' in content
    assert "Cancel" in content

class ExerciseDropdownParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_modal = False
        self.in_select = False
        self.options = []
        self.select_found = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag == "dialog" and attributes.get("id") == "exercise-modal":
            self.in_modal = True

        elif tag == "select" and self.in_modal:
            if attributes.get("id") == "exercise-type":
                self.in_select = True
                self.select_found = True

        elif tag == "option" and self.in_select:
            self.options.append(attributes.get("value"))

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_select = False
        elif tag == "dialog":
            self.in_modal = False

def test_exercise_dropdown_contains_baseline_exercises(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    parser = ExerciseDropdownParser()
    parser.feed(response.content.decode())

    assert parser.select_found, "Exercise dropdown was not found"

    expected_exercises = [
        "push_ups",
        "sit_ups",
        "squats",
        "planks",
        "curls",
        "walking",
        "jogging",
        "running",
        "lunges",
        "butterfly_stretch",
        "shoulder_stretch",
    ]

    # Placeholder must be the first option.
    assert parser.options[0] == ""

    # All required baseline exercises must be available.
    assert set(expected_exercises).issubset(set(parser.options))

    # Exercise values must be unique.
    assert len(parser.options) == len(set(parser.options))

def test_exercise_modal_has_hidden_repetition_fields(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    content = response.content.decode()

    # Repetition inputs should be grouped together.
    assert 'id="repetition-fields"' in content

    # The group should initially be hidden.
    assert 'id="repetition-fields" hidden' in content

    # Both inputs must exist.
    assert 'name="sets"' in content
    assert 'name="reps"' in content

def test_repetition_exercises_have_input_type_metadata(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    content = response.content.decode()

    repetition_exercises = [
        "push_ups",
        "sit_ups",
        "squats",
        "curls",
        "lunges",
    ]

    for exercise in repetition_exercises:
        assert (
            f'value="{exercise}" data-input-type="reps"'
            in content
        )

def test_exercise_modal_has_hidden_duration_field(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    content = response.content.decode()

    # Duration input should exist and initially be hidden.
    assert 'id="duration-fields" hidden' in content

    # Duration is measured in seconds.
    assert 'name="duration_seconds"' in content

    # These exercises use duration-based measurements.
    duration_exercises = [
        "planks",
        "butterfly_stretch",
        "shoulder_stretch",
    ]

    for exercise in duration_exercises:
        assert (
            f'value="{exercise}" data-input-type="duration"'
            in content
        )

def test_exercise_modal_has_hidden_distance_field(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    content = response.content.decode()

    # Distance fields should initially be hidden.
    assert 'id="distance-fields" hidden' in content

    # Distance is measured in miles.
    assert 'name="distance_miles"' in content

    # These exercises use distance measurements.
    distance_exercises = [
        "walking",
        "jogging",
        "running",
    ]

    for exercise in distance_exercises:
        assert (
            f'value="{exercise}" data-input-type="distance"'
            in content
        )

@pytest.mark.parametrize(
    "exercise_type",
    [
        "push_ups",
        "sit_ups",
        "squats",
        "curls",
        "lunges",
    ],
)
def test_valid_repetition_exercise_is_accepted(exercise_type):
    form = ExerciseInputForm(
        data={
            "exercise_type": exercise_type,
            "sets": 3,
            "reps": 10,
        }
    )

    assert form.is_valid(), form.errors