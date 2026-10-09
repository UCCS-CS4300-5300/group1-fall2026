import os

import firebase_admin
from firebase_admin import auth, credentials, firestore


# Reuse the Firebase Admin app, or initialize it from the configured credentials.
def get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        credential = credentials.Certificate(os.environ["FIREBASE_CREDENTIALS_PATH"])
        return firebase_admin.initialize_app(credential)


# Create a Firestore client connected to the shared Firebase Admin app.
def get_firestore_client():
    return firestore.client(app=get_firebase_app())


# Check Firebase's signed proof that the person entered the correct password.
def verify_firebase_id_token(id_token):
    # Return the account details Firebase confirmed.
    return auth.verify_id_token(id_token, app=get_firebase_app())