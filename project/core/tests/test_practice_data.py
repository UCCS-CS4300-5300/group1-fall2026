from unittest.mock import Mock

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


# Create a test account whose username contains a Firebase UID.
@pytest.fixture
def firebase_user(db):
    return User.objects.create_user("firebase_test-uid")


# Saving stores the sample count under the signed-in user's Firebase UID.
@pytest.mark.django_db
def test_practice_value_is_saved_to_signed_in_users_document(client, firebase_user, monkeypatch):
    firestore_client = Mock()
    user_ref = firestore_client.collection.return_value.document.return_value
    monkeypatch.setattr("core.views.get_firestore_client", lambda: firestore_client)
    client.force_login(firebase_user)

    response = client.post(
        reverse("core:practice_data"),
        {"practice_pushups": "7"},
    )

    assert response.status_code == 200
    assert response.json() == {"practicePushups": 7}
    firestore_client.collection.assert_called_once_with("users")
    firestore_client.collection.return_value.document.assert_called_once_with("test-uid")
    user_ref.set.assert_called_once_with({"practice_pushups": 7}, merge=True)


# Loading returns the saved sample count for the signed-in user.
@pytest.mark.django_db
def test_practice_value_can_be_retrieved(client, firebase_user, monkeypatch):
    firestore_client = Mock()
    user_ref = firestore_client.collection.return_value.document.return_value
    user_ref.get.return_value.to_dict.return_value = {"practice_pushups": 7}
    monkeypatch.setattr("core.views.get_firestore_client", lambda: firestore_client)
    client.force_login(firebase_user)

    response = client.get(reverse("core:practice_data"))

    assert response.status_code == 200
    assert response.json() == {"practicePushups": 7}
    firestore_client.collection.return_value.document.assert_called_once_with("test-uid")


# A user without saved data gets an empty result without creating a document.
@pytest.mark.django_db
def test_missing_practice_value_returns_null_without_creating_data(client, firebase_user, monkeypatch):
    firestore_client = Mock()
    user_ref = firestore_client.collection.return_value.document.return_value
    user_ref.get.return_value.to_dict.return_value = None
    monkeypatch.setattr("core.views.get_firestore_client", lambda: firestore_client)
    client.force_login(firebase_user)

    response = client.get(reverse("core:practice_data"))

    assert response.status_code == 200
    assert response.json() == {"practicePushups": None}
    user_ref.set.assert_not_called()


# Anonymous visitors are redirected to sign in before accessing practice data.
@pytest.mark.django_db
def test_practice_data_requires_a_signed_in_user(client):
    response = client.get(reverse("core:practice_data"))

    assert response.status_code == 302


# Reject malformed or out-of-range counts before contacting Firestore.
@pytest.mark.django_db
@pytest.mark.parametrize("value", ["-1", "1.5", "many", "10001", ""])
def test_practice_data_rejects_invalid_counts(client, firebase_user, monkeypatch, value):
    get_firestore_client = Mock()
    monkeypatch.setattr("core.views.get_firestore_client", get_firestore_client)
    client.force_login(firebase_user)

    response = client.post(
        reverse("core:practice_data"),
        {"practice_pushups": value},
    )

    assert response.status_code == 400
    get_firestore_client.assert_not_called()


# Non-Firebase Django accounts cannot read or write practice data.
@pytest.mark.django_db
def test_practice_data_rejects_non_firebase_django_user(client, db, monkeypatch):
    user = User.objects.create_user("ordinary-user")
    get_firestore_client = Mock()
    monkeypatch.setattr("core.views.get_firestore_client", get_firestore_client)
    client.force_login(user)

    response = client.post(
        reverse("core:practice_data"),
        {"practice_pushups": "7"},
    )

    assert response.status_code == 403
    get_firestore_client.assert_not_called()