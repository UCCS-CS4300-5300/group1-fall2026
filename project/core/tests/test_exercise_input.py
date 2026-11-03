import pytest
from core.forms_exercise import ExerciseInputForm
from django.contrib.auth.models import User
from django.urls import reverse
from html.parser import HTMLParser
from core.views_exercise import build_exercise_data

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
def test_repetition_exercises_require_sets_and_reps(exercise_type):
    form = ExerciseInputForm(
        data={"exercise_type": exercise_type}
    )

    assert not form.is_valid()
    assert "sets" in form.errors
    assert "reps" in form.errors


@pytest.mark.parametrize(
    "sets,reps",
    [
        (0, 10),
        (3, 0),
        (-1, 10),
        (3, -5),
        (2.5, 10),
        (3, 4.5),
    ],
)
def test_invalid_repetition_values_are_rejected(sets, reps):
    form = ExerciseInputForm(
        data={
            "exercise_type": "push_ups",
            "sets": sets,
            "reps": reps,
        }
    )

    assert not form.is_valid()


@pytest.mark.parametrize(
    "exercise_type",
    [
        "planks",
        "butterfly_stretch",
        "shoulder_stretch",
    ],
)
def test_valid_duration_exercise_is_accepted(exercise_type):
    form = ExerciseInputForm(
        data={
            "exercise_type": exercise_type,
            "duration_seconds": 60,
        }
    )

    assert form.is_valid(), form.errors


@pytest.mark.parametrize(
    "exercise_type",
    [
        "walking",
        "jogging",
        "running",
    ],
)
def test_valid_distance_exercise_is_accepted(exercise_type):
    form = ExerciseInputForm(
        data={
            "exercise_type": exercise_type,
            "distance_miles": "1.50",
        }
    )

    assert form.is_valid(), form.errors


@pytest.mark.parametrize(
    "duration",
    [None, "", 0, -1, 2.5, "abc"],
)
def test_invalid_duration_is_rejected(duration):
    form = ExerciseInputForm(
        data={
            "exercise_type": "planks",
            "duration_seconds": duration,
        }
    )

    assert not form.is_valid()


@pytest.mark.parametrize(
    "distance",
    [None, "", "0", "-1", "abc", "1.234"],
)
def test_invalid_distance_is_rejected(distance):
    form = ExerciseInputForm(
        data={
            "exercise_type": "running",
            "distance_miles": distance,
        }
    )

    assert not form.is_valid()


@pytest.mark.parametrize(
    "exercise_type,measurements,irrelevant_fields",
    [
        (
            "push_ups",
            {"sets": 3, "reps": 10, "distance_miles": "2.5"},
            ["distance_miles", "duration_seconds"],
        ),
        (
            "planks",
            {"duration_seconds": 60, "sets": 3, "reps": 10},
            ["sets", "reps", "distance_miles"],
        ),
        (
            "running",
            {"distance_miles": "2.5", "sets": 3, "reps": 10},
            ["sets", "reps", "duration_seconds"],
        ),
    ],
)


def test_irrelevant_measurements_are_excluded(
    exercise_type, measurements, irrelevant_fields
):
    form = ExerciseInputForm(
        data={
            "exercise_type": exercise_type,
            **measurements,
        }
    )

    assert form.is_valid(), form.errors

    for field in irrelevant_fields:
        assert form.cleaned_data.get(field) is None


class ExerciseFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_modal = False
        self.in_form = False
        self.form_found = False
        self.form_method = None
        self.field_names = set()
        self.submit_found = False
        self.cancel_found = False
        self.csrf_found = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag == "dialog" and attributes.get("id") == "exercise-modal":
            self.in_modal = True

        elif tag == "form" and self.in_modal:
            self.in_form = True
            self.form_found = True
            self.form_method = attributes.get("method", "").lower()

        elif self.in_form:
            if tag in ("input", "select"):
                name = attributes.get("name")
                if name:
                    self.field_names.add(name)

                if name == "csrfmiddlewaretoken":
                    self.csrf_found = True

            if tag == "button":
                if attributes.get("type") == "submit":
                    self.submit_found = True

                if attributes.get("id") == "cancel-exercise-btn":
                    self.cancel_found = (
                        attributes.get("type") == "button"
                    )

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False
        elif tag == "dialog":
            self.in_modal = False


def test_exercise_modal_contains_submission_form(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    parser = ExerciseFormParser()
    parser.feed(response.content.decode())

    assert parser.form_found
    assert parser.form_method == "post"
    assert parser.csrf_found
    assert parser.submit_found
    assert parser.cancel_found

    expected_fields = {
        "exercise_type",
        "sets",
        "reps",
        "duration_seconds",
        "distance_miles",
    }

    assert expected_fields.issubset(parser.field_names)


def test_submit_exercise_url_exists():
    url = reverse("core:submit_exercise")

    assert url == "/exercises/submit/"


def test_submit_exercise_requires_login(client):
    url = reverse("core:submit_exercise")

    response = client.post(
        url,
        data={
            "exercise_type": "push_ups",
            "sets": 3,
            "reps": 10,
        },
    )

    assert response.status_code == 302
    assert response.url.startswith("/login/")


def test_submit_exercise_rejects_get_requests(logged_in_client):
    url = reverse("core:submit_exercise")

    response = logged_in_client.get(url)

    assert response.status_code == 405


def test_submit_exercise_rejects_invalid_data(logged_in_client):
    response = logged_in_client.post(
        reverse("core:submit_exercise"),
        data={
            "exercise_type": "push_ups",
            "sets": 0,
            "reps": 10,
        },
    )

    assert response.status_code == 400

    response_data = response.json()

    assert response_data["success"] is False
    assert "sets" in response_data["errors"]

def test_exercise_form_targets_submission_endpoint(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200

    content = response.content.decode()
    expected_url = reverse("core:submit_exercise")

    assert 'id="exercise-form"' in content
    assert f'action="{expected_url}"' in content


def test_exercise_modal_contains_feedback_area(logged_in_client):
    response = logged_in_client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b'id="exercise-feedback"' in response.content


def test_validated_exercise_builds_flat_data():
    form = ExerciseInputForm(
        data={
            "exercise_type": "push_ups",
            "sets": 3,
            "reps": 10,
        }
    )

    assert form.is_valid(), form.errors

    data = build_exercise_data(form.cleaned_data)

    assert data == {
        "exercise_type": "push_ups",
        "sets": 3,
        "reps": 10,
        "duration_seconds": None,
        "distance_miles": None,
    }