from unittest.mock import Mock

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


# Make a Django account that represents a signed-in Firebase user in these tests.
@pytest.fixture
def firebase_user(db):
    return User.objects.create_user("firebase_test-uid")


# Provide a complete set of example values for XP save requests.
@pytest.fixture
def xp_values():
    return {
        "total_xp": "1200",
        "arms_xp": "200",
        "legs_xp": "300",
        "core_xp": "250",
        "chest_xp": "150",
        "weekly_xp": "400",
    }


# Check that saving sends all six number values to this user's Firestore document.
@pytest.mark.django_db
def test_xp_stats_are_saved_to_signed_in_users_document(
    client, firebase_user, monkeypatch, xp_values
):
    firestore_client = Mock()
    user_ref = firestore_client.collection.return_value.document.return_value
    monkeypatch.setattr("core.views.get_firestore_client", lambda: firestore_client)
    client.force_login(firebase_user)

    response = client.post(reverse("core:xp_stats"), xp_values)

    assert response.status_code == 200
    assert response.json() == {
        "total_xp": 1200,
        "arms_xp": 200,
        "legs_xp": 300,
        "core_xp": 250,
        "chest_xp": 150,
        "weekly_xp": 400,
    }
    firestore_client.collection.assert_called_once_with("users")
    firestore_client.collection.return_value.document.assert_called_once_with("test-uid")
    user_ref.set.assert_called_once_with(
        {
            "total_xp": 1200,
            "arms_xp": 200,
            "legs_xp": 300,
            "core_xp": 250,
            "chest_xp": 150,
            "weekly_xp": 400,
        },
        merge=True,
    )


# Check that loading returns saved values and fills any missing fields with zero.
@pytest.mark.django_db
def test_xp_stats_can_be_loaded_with_zero_defaults(
    client, firebase_user, monkeypatch
):
    firestore_client = Mock()
    user_ref = firestore_client.collection.return_value.document.return_value
    user_ref.get.return_value.to_dict.return_value = {
        "total_xp": 1200,
        "arms_xp": 200,
        "weekly_xp": 400,
    }
    monkeypatch.setattr("core.views.get_firestore_client", lambda: firestore_client)
    client.force_login(firebase_user)

    response = client.get(reverse("core:xp_stats"))

    assert response.status_code == 200
    assert response.json() == {
        "total_xp": 1200,
        "arms_xp": 200,
        "legs_xp": 0,
        "core_xp": 0,
        "chest_xp": 0,
        "weekly_xp": 400,
    }


# Bad, missing, or negative values should be rejected without using Firestore.
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_xp", "-1"),
        ("arms_xp", "1.5"),
        ("legs_xp", "many"),
        ("core_xp", ""),
    ],
)
def test_xp_stats_reject_invalid_values_before_firestore(
    client, firebase_user, monkeypatch, xp_values, field, value
):
    xp_values[field] = value
    get_firestore_client = Mock()
    monkeypatch.setattr("core.views.get_firestore_client", get_firestore_client)
    client.force_login(firebase_user)

    response = client.post(reverse("core:xp_stats"), xp_values)

    assert response.status_code == 400
    get_firestore_client.assert_not_called()


# XP stats are private, so a visitor must sign in before loading them.
@pytest.mark.django_db
def test_xp_stats_require_a_signed_in_user(client):
    response = client.get(reverse("core:xp_stats"))

    assert response.status_code == 302


# A regular Django account cannot use the endpoint as a Firebase account.
@pytest.mark.django_db
def test_xp_stats_reject_non_firebase_django_user(client, db, monkeypatch, xp_values):
    user = User.objects.create_user("ordinary-user")
    get_firestore_client = Mock()
    monkeypatch.setattr("core.views.get_firestore_client", get_firestore_client)
    client.force_login(user)

    response = client.post(reverse("core:xp_stats"), xp_values)

    assert response.status_code == 403
    get_firestore_client.assert_not_called()
