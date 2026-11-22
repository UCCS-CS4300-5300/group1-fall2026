import pytest
from core.forms_exercise import ExerciseInputForm
from django.contrib.auth.models import User
from django.urls import reverse
from core.views_exercise import build_exercise_data

@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user(
        username="exercise_tester",
        password="test_password_123",
    )
    client.force_login(user)
    return client


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