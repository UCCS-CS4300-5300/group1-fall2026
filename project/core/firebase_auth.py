import os

import firebase_admin
from firebase_admin import auth, credentials


# Check Firebase's signed proof that the person entered the correct password.
def verify_firebase_id_token(id_token):
    # Reuse Firebase's setup, or load the private key the first time.
    try:
        app = firebase_admin.get_app()
    except ValueError:
        credential = credentials.Certificate(os.environ["FIREBASE_CREDENTIALS_PATH"])
        app = firebase_admin.initialize_app(credential)
    # Return the account details Firebase confirmed.
    return auth.verify_id_token(id_token, app=app)