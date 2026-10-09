import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from firebase_admin import auth as firebase_auth

from .firebase_auth import get_firestore_client, verify_firebase_id_token
from .models import StarterItem

logger = logging.getLogger(__name__)


# Show the page where someone enters their email and password.
@require_GET
def login_page(request):
    return render(request, "core/login.html")


# After Firebase checks the password, let Django remember the signed-in person too.
@require_POST
def firebase_session(request):
    # The browser must send Firebase's proof that sign-in succeeded.
    id_token = request.POST.get("idToken")
    if not id_token:
        return JsonResponse({"error": "A Firebase ID token is required."}, status=400)

    # Ask Firebase to check that proof before trusting the sign-in.
    try:
        decoded_token = verify_firebase_id_token(id_token)
    except firebase_auth.InvalidIdTokenError:
        return JsonResponse({"error": "The sign-in token is invalid or expired."}, status=401)

    # Firebase gives every account a unique number; use it to find this person.
    firebase_uid = decoded_token.get("uid")
    if not firebase_uid:
        return JsonResponse({"error": "The sign-in token has no user ID."}, status=401)

    User = get_user_model()
    username = f"firebase_{firebase_uid}"
    email = decoded_token.get("email", "") or ""
    user, created = User.objects.get_or_create(username=username, defaults={"email": email})
    if not created and user.has_usable_password():
        return JsonResponse({"error": "This Firebase account cannot be linked."}, status=409)

    # Firebase manages this password, so Django must not accept another one.
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    # Remember the successful login so Django can open protected pages.
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"redirectUrl": "/"})

@login_required
def home(request):
    items = StarterItem.objects.filter(is_active=True).order_by("title")
    return render(request, "core/home.html", {"items": items})


# Save or load one practice count from the signed-in Firebase user's document.
@login_required
@require_http_methods(["GET", "POST"])
def practice_data(request):
    username = request.user.get_username()
    uid_prefix = "firebase_"
    if not username.startswith(uid_prefix) or not username.removeprefix(uid_prefix):
        return JsonResponse({"error": "A Firebase account is required."}, status=403)

    firebase_uid = username.removeprefix(uid_prefix)
    if request.method == "POST":
        value = request.POST.get("practice_pushups")
        try:
            pushups = int(value)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Enter a whole-number practice count."}, status=400)
        if pushups < 0 or pushups > 10000:
            return JsonResponse({"error": "The practice count must be between 0 and 10000."}, status=400)

    try:
        user_ref = get_firestore_client().collection("users").document(firebase_uid)
        if request.method == "GET":
            user_data = user_ref.get().to_dict() or {}
            return JsonResponse({"practicePushups": user_data.get("practice_pushups")})

        user_ref.set({"practice_pushups": pushups}, merge=True)
        return JsonResponse({"practicePushups": pushups})
    except Exception:
        logger.exception("Unable to access practice data for Firebase UID %s", firebase_uid)
        return JsonResponse({"error": "Practice data storage is unavailable."}, status=503)


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You've been logged out.")
    return redirect("login")