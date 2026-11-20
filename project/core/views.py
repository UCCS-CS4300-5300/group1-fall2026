import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from firebase_admin import auth as firebase_auth

from .firebase_auth import get_firestore_client, verify_firebase_id_token
from .forms import RepkinSetupForm
from .models import StarterItem
from .models_repkin import Repkin

from .repkin_looks import (
    LEVEL_COUNT,
    next_limb_level,
    parse_limb_level,
    sprite_for,
    sprite_needs_vertical_offset,
    sprite_urls_for,
)
from .views_message import GREETING_PENDING_KEY
from .exercises import EXERCISES


logger = logging.getLogger(__name__)

DEFAULT_REPKIN = {"mood": "content", "color": "green"}

XP_STAT_FIELDS = (
    "total_xp",
    "arms_xp",
    "legs_xp",
    "core_xp",
    "chest_xp",
    "weekly_xp",
)


@require_GET
def login_page(request):
    return render(request, "core/login.html")


@require_GET
def account_creation(request):
    return render(request, "core/account_creation.html")


def get_repkin(user):
    repkin, _ = Repkin.objects.get_or_create(owner=user, defaults=DEFAULT_REPKIN)
    return repkin


@require_POST
def firebase_session(request):
    id_token = request.POST.get("idToken")
    if not id_token:
        return JsonResponse({"error": "A Firebase ID token is required."}, status=400)

    try:
        decoded_token = verify_firebase_id_token(id_token)
    except firebase_auth.InvalidIdTokenError:
        return JsonResponse({"error": "The sign-in token is invalid or expired."}, status=401)

    firebase_uid = decoded_token.get("uid")
    if not firebase_uid:
        return JsonResponse({"error": "The sign-in token has no user ID."}, status=401)

    User = get_user_model()
    username = f"firebase_{firebase_uid}"
    email = decoded_token.get("email", "") or ""
    user, created = User.objects.get_or_create(username=username, defaults={"email": email})
    if not created and user.has_usable_password():
        return JsonResponse({"error": "This Firebase account cannot be linked."}, status=409)

    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session[GREETING_PENDING_KEY] = True
    return JsonResponse({"redirectUrl": "/"})


@login_required
def home(request):
    repkin = get_repkin(request.user)
    return render_home(request, repkin, RepkinSetupForm(instance=repkin))


@login_required
def repkin_setup(request):
    if request.method != "POST":
        return redirect("core:home")
    repkin = get_repkin(request.user)
    form = RepkinSetupForm(request.POST, instance=repkin)
    if form.is_valid():
        repkin = form.save(commit=False)
        repkin.setup_complete = True
        repkin.save()
        return redirect("core:home")
    repkin.refresh_from_db()
    return render_home(request, repkin, form, open_setup=True)


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


@login_required
@require_http_methods(["GET", "POST"])
def xp_stats(request):
    username = request.user.get_username()
    uid_prefix = "firebase_"
    if not username.startswith(uid_prefix) or not username.removeprefix(uid_prefix):
        return JsonResponse({"error": "A Firebase account is required."}, status=403)

    firebase_uid = username.removeprefix(uid_prefix)
    if request.method == "POST":
        try:
            stats = {field: int(request.POST[field]) for field in XP_STAT_FIELDS}
        except (KeyError, TypeError, ValueError):
            return JsonResponse({"error": "All XP stats must be whole numbers."}, status=400)
        if any(value < 0 for value in stats.values()):
            return JsonResponse({"error": "XP stats cannot be negative."}, status=400)

    try:
        user_ref = get_firestore_client().collection("users").document(firebase_uid)
        if request.method == "GET":
            return JsonResponse(
                {
                    field: (user_ref.get().to_dict() or {}).get(field, 0)
                    for field in XP_STAT_FIELDS
                }
            )

        user_ref.set(stats, merge=True)
        return JsonResponse(stats)
    except Exception:
        logger.exception("Unable to access XP stats for Firebase UID %s", firebase_uid)
        return JsonResponse({"error": "XP stats storage is unavailable."}, status=503)


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You've been logged out.")
    return redirect("login")


def render_home(request, repkin, setup_form, open_setup=False):
    items = StarterItem.objects.filter(is_active=True).order_by("title")
    # Resolve the saved limb levels and matching sprite for the home page.
    arms_level = parse_limb_level(repkin.arms_level)
    legs_level = parse_limb_level(repkin.legs_level)

    context = {
        "items": items,
        "repkin": repkin,
        "repkin_sprite": sprite_for(repkin.color, arms_level, legs_level),
        "sprite_needs_vertical_offset": sprite_needs_vertical_offset(
            repkin.color, legs_level
        ),
        "setup_form": setup_form,
        "open_setup": open_setup,
        "show_welcome": True,

        "exercises": [
            {
                "name": name,
                "label": name.replace("_", " ").title(),
                "input_type": info["input_type"],
            }
            for name, info in EXERCISES.items()
],

    }

    return render(request, "core/home.html", context)

#Second Page Request#
@login_required
def locker_room(request):
    repkin = get_repkin(request.user)
    # Prepare the saved sprite and available options for the locker room.
    arms_level = parse_limb_level(repkin.arms_level)
    legs_level = parse_limb_level(repkin.legs_level)
    context = {
        "repkin": repkin,
        "setup_form": RepkinSetupForm(instance=repkin),
        "arms_level": arms_level,
        "legs_level": legs_level,
        "repkin_sprite": sprite_for(repkin.color, arms_level, legs_level),
        "sprite_needs_vertical_offset": sprite_needs_vertical_offset(
            repkin.color, legs_level
        ),
        "next_arms": next_limb_level(arms_level),
        "next_legs": next_limb_level(legs_level),
        "sprite_gif_urls": {
            arms: {legs: static(path) for legs, path in versions.items()}
            for arms, versions in sprite_urls_for(repkin.color).items()
        },
        "sprite_update_url": reverse("core:update_repkin_sprite"),
    }
    return render(request, "core/locker_room.html", context)


# Validate and save the selected limb levels for the signed-in Repkin.
@login_required
@require_POST
def update_repkin_sprite(request):
    try:
        arms_level = int(request.POST.get("arms_level", ""))
        legs_level = int(request.POST.get("legs_level", ""))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Choose valid arm and leg versions."}, status=400)

    if not (0 <= arms_level < LEVEL_COUNT and 0 <= legs_level < LEVEL_COUNT):
        return JsonResponse({"error": "Choose valid arm and leg versions."}, status=400)

    repkin = get_repkin(request.user)
    repkin.arms_level = arms_level
    repkin.legs_level = legs_level
    repkin.save(update_fields=["arms_level", "legs_level"])
    return JsonResponse({"arms_level": arms_level, "legs_level": legs_level})


#Information to be pulled and displayed in the main menu on both pages(Repkin Name and Username)#
@login_required
def _clean_name(request):
    name = request.POST.get("name", "").strip()
    return name if 1 <= len(name) <= 30 else None

@login_required
@require_POST
def update_repkin_name(request):
    name = _clean_name(request)
    if name is None:
        return JsonResponse({"error": "Enter 1-30 characters."}, status=400)
    repkin = get_repkin(request.user)
    repkin.name = name
    repkin.save(update_fields=["name"])    
    return JsonResponse({"name": name})


def _firebase_uid(request):
    username = request.user.get_username()
    prefix = "firebase_"
    if username.startswith(prefix) and username.removeprefix(prefix):
        return username.removeprefix(prefix)
    return None

@login_required
@require_POST
def update_user_name(request):
    name = _clean_name(request)
    if name is None:
        return JsonResponse({"error": "Enter 1-30 characters."}, status=400)
    request.user.first_name = name
    request.user.save(update_fields=["first_name"])
    return JsonResponse({"name": name})

PROFILE_LIMITS = {"height_cm": (50, 250), "weight_kg": (10, 650)}
#PII Handling
@login_required
@require_http_methods(["GET", "POST"])
def profile_data(request):
    uid = _firebase_uid(request)
    if uid is None:
        return JsonResponse({"error": "A Firebase account is required."}, status=403)
    update = {}
    if request.method == "POST":
        for field, (low, high) in PROFILE_LIMITS.items():
            raw = request.POST.get(field)
            if raw is None:
                continue
            try:
                value = float(raw)
            except ValueError:
                return JsonResponse({"error": "Enter a number."}, status=400)
            if not low <= value <= high:
                return JsonResponse({"error": f"Enter {low}-{high}."}, status=400)
            update[field] = round(value, 1)
        if not update:
            return JsonResponse({"error": "Nothing to save."}, status=400)
    try:
        ref = get_firestore_client().collection("users").document(uid)
        if request.method == "POST":
            ref.set(update, merge=True)
            return JsonResponse(update)
        data = ref.get().to_dict() or {}
        return JsonResponse({k: data.get(k) for k in PROFILE_LIMITS})
    except Exception:
        logger.exception("Profile storage failed for Firebase UID %s", uid)
        return JsonResponse({"error": "Profile storage is unavailable."}, status=503)
    
