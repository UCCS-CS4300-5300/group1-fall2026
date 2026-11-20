import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models_workout import MAX_PRESETS_PER_USER, Workout
from .units import UNIT_SYSTEMS
from .workout_logs import log_workout, stat_totals
from .workout_presets import (
    NameTaken, PresetNotFound, PresetValidationError, TooManyPresets,
    catalog_payload, list_presets, save_preset, serialize_preset, validate_payload,
    with_default_name,
)

# A full workout is a few kilobytes. Anything far bigger is not a workout.
MAX_BODY_BYTES = 50_000


def error(code, message, status, **extra):
    return JsonResponse({"error": code, "message": message, **extra}, status=status)


# What can go wrong when a preset is saved, whether by "Save preset" or as part of
# logging a workout. They all get the same replies.
PRESET_PROBLEMS = (PresetValidationError, NameTaken, TooManyPresets, PresetNotFound)


def preset_problem(problem):
    """The JSON reply for one of PRESET_PROBLEMS."""
    if isinstance(problem, PresetValidationError):
        return JsonResponse(
            {"error": "validation", "message": "Please fix the problems below.", "errors": problem.errors},
            status=400,
        )
    if isinstance(problem, NameTaken):
        return error(
            "name_taken", "You already have a workout with that name.", 409,
            existing_id=problem.existing_id,
        )
    if isinstance(problem, TooManyPresets):
        return error(
            "too_many_presets",
            f"You can keep up to {MAX_PRESETS_PER_USER} workouts. Delete one to save another.",
            409,
        )
    return error("not_found", "That workout doesn't exist.", 404)


@login_required
@require_GET
def workout_logging(request):
    """The workout logging page: build a workout, save it as a preset, or load one."""
    return render(request, "core/workout_logging.html")


@login_required
@require_GET
def workout_catalog(request):
    """The sections and the exercises each one offers, for the picker."""
    return JsonResponse(catalog_payload())


@login_required
@require_GET
def preset_list(request):
    """The signed-in user's presets, newest first."""
    return JsonResponse({
        "presets": list_presets(request.user),
        "max_presets": MAX_PRESETS_PER_USER,
    })


@login_required
@require_GET
def preset_detail(request, pk):
    """One preset, with weights and distances in the unit system the page asks for."""
    unit_system = request.GET.get("unit_system")
    if unit_system not in UNIT_SYSTEMS:
        return error("invalid_unit_system", 'unit_system must be "imperial" or "si".', 400)
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    return JsonResponse(serialize_preset(workout, unit_system))


@login_required
@require_POST
def preset_save(request):
    """Create a preset, or update one when the body includes its id."""
    if len(request.body) > MAX_BODY_BYTES:
        return error("too_large", "That request is too large.", 413)
    try:
        payload = json.loads(request.body)
    except ValueError:
        return error("invalid_json", "The request body must be JSON.", 400)

    try:
        workout, created = save_preset(request.user, payload)
    except PRESET_PROBLEMS as problem:
        return preset_problem(problem)

    return JsonResponse(
        {"id": workout.pk, "name": workout.name, "created": created},
        status=201 if created else 200,
    )


@login_required
@require_POST
def preset_delete(request, pk):
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    workout.delete()
    return JsonResponse({"deleted": True})


@login_required
@require_POST
def workout_log(request):
    """Log every exercise in the workout as just performed.

    Takes the same body as saving a preset. Add `"save_preset": true` to also save the
    workout as a preset (updating the one named by `id`, if there is one): the page does
    this for any workout that isn't already saved. A blank name gets a dated one like
    "Workout Nov 16". Saving and logging happen together, so if either fails, neither
    does. Returns the new log ids, which the page hands to the home page so RepKin can
    comment on the workout.
    """
    if len(request.body) > MAX_BODY_BYTES:
        return error("too_large", "That request is too large.", 413)
    try:
        payload = json.loads(request.body)
    except ValueError:
        return error("invalid_json", "The request body must be JSON.", 400)

    wants_save = isinstance(payload, dict) and payload.get("save_preset") is True

    try:
        cleaned = validate_payload(payload, require_name=False)
        with transaction.atomic():
            saved = None
            if wants_save:
                saved = save_preset(
                    request.user, with_default_name(request.user, payload, timezone.localdate())
                )
            logs = log_workout(request.user, cleaned["items"])
    except PRESET_PROBLEMS as problem:
        return preset_problem(problem)

    preset = None
    if saved is not None:
        workout, created = saved
        preset = {"id": workout.pk, "name": workout.name, "created": created}
    return JsonResponse(
        {
            "success": True,
            "log_ids": [log.pk for log in logs],
            "count": len(logs),
            "stats": stat_totals(logs),
            "preset": preset,
        },
        status=201,
    )
