import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .models_workout import MAX_PRESETS_PER_USER, Workout
from .units import UNIT_SYSTEMS
from .workout_presets import (
    NameTaken, PresetNotFound, PresetValidationError, TooManyPresets,
    catalog_payload, list_presets, save_preset, serialize_preset,
)

# A full workout is a few kilobytes. Anything far bigger is not a workout.
MAX_BODY_BYTES = 50_000


def error(code, message, status, **extra):
    return JsonResponse({"error": code, "message": message, **extra}, status=status)


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
    except PresetValidationError as problem:
        return JsonResponse(
            {"error": "validation", "message": "Please fix the problems below.", "errors": problem.errors},
            status=400,
        )
    except NameTaken as problem:
        return error(
            "name_taken", "You already have a workout with that name.", 409,
            existing_id=problem.existing_id,
        )
    except TooManyPresets:
        return error(
            "too_many_presets",
            f"You can keep up to {MAX_PRESETS_PER_USER} workouts. Delete one to save another.",
            409,
        )
    except PresetNotFound:
        return error("not_found", "That workout doesn't exist.", 404)

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
