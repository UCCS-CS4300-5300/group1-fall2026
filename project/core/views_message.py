import math
import time

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .repkin_voice import KINDS, generate_message

# The least time (in seconds) that must pass between two messages of the same
# kind for the same person. Idle chatter is rate-limited so a browser timer (or
# a bug) can't hammer the model. A workout comment is a direct reaction to
# something the user just did, so it has no cooldown. A greeting has none
# either: it is limited by the one-greeting-per-login rule below instead.
COOLDOWN_SECONDS = {"greeting": 0, "workout": 0, "idle": 60}

# The most exercise ids one workout request may name.
MAX_LOG_IDS = 20

# Where we remember things about this person's messages (in their session).
# GREETING_PENDING_KEY is switched on at login (see firebase_session) and
# switched off by the first greeting request, so each login gets exactly one
# greeting. Logging out wipes the session, so the next login starts fresh.
GREETING_PENDING_KEY = "repkin_greeting_pending"
LAST_MESSAGE_KEY = "repkin_last_message"
LAST_SERVED_KEY = "repkin_last_served"


def current_time():
    """Wrapped in a function so tests can control the clock."""
    return time.time()


def parse_log_ids(raw_values):
    """Turn ['3', '4'] into [3, 4]. Raise ValueError if anything is not a
    plain whole number, or if there are too many."""
    if len(raw_values) > MAX_LOG_IDS:
        raise ValueError("too many log ids")
    ids = []
    for raw in raw_values:
        # isascii() keeps this to plain 0-9. Digits from other scripts (like the
        # Arabic-Indic '٣') pass isdigit(), and int() would turn them into 3.
        # The length limit keeps numbers small enough for the database.
        if not (raw.isascii() and raw.isdigit() and len(raw) <= 18):
            raise ValueError(f"not a valid log id: {raw!r}")
        ids.append(int(raw))
    return ids


def seconds_until_allowed(session, kind, now):
    last_served = session.get(LAST_SERVED_KEY, {}).get(kind)
    if last_served is None:
        return 0
    remaining = COOLDOWN_SECONDS[kind] - (now - last_served)
    return max(0, math.ceil(remaining))


@login_required
@require_POST
def repkin_message(request):
    kind = request.POST.get("kind", "")
    if kind not in KINDS:
        return JsonResponse({"error": "Unknown message kind."}, status=400)

    # Only a workout message looks at exercise ids; other kinds ignore them.
    log_ids = None
    if kind == "workout":
        try:
            log_ids = parse_log_ids(request.POST.getlist("log_ids"))
        except ValueError:
            return JsonResponse(
                {"error": "log_ids must be whole numbers (20 at most)."}, status=400
            )

    if kind == "greeting":
        # Take the "this login is owed a greeting" mark, if there is one. Taking
        # it BEFORE asking the model means a second tab or a refresh can't also
        # get a greeting for the same login.
        if not request.session.pop(GREETING_PENDING_KEY, False):
            return JsonResponse(
                {
                    "message": None,
                    "kind": kind,
                    "fallback": False,
                    "reason": "already_greeted",
                }
            )

    wait = seconds_until_allowed(request.session, kind, current_time())
    if wait:
        response = JsonResponse(
            {"error": "RepKin just spoke. Try again soon.", "retry_after": wait},
            status=429,
        )
        response["Retry-After"] = str(wait)
        return response

    # The previous message comes from OUR record of this session, never from
    # the browser, so nobody can slip their own text into the prompt.
    message = generate_message(
        request.user,
        kind,
        just_logged_ids=log_ids,
        last_message=request.session.get(LAST_MESSAGE_KEY, ""),
    )

    # Fallback lines count too, so a stopped Ollama isn't asked again and again.
    served = dict(request.session.get(LAST_SERVED_KEY, {}))
    served[kind] = current_time()
    request.session[LAST_SERVED_KEY] = served
    request.session[LAST_MESSAGE_KEY] = message.text

    return JsonResponse(
        {"message": message.text, "kind": kind, "fallback": message.used_fallback}
    )
