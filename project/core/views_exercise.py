
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .forms_exercise import ExerciseInputForm

def build_exercise_data(cleaned_data):
    return {
        "exercise_type": cleaned_data["exercise_type"],
        "sets": cleaned_data.get("sets"),
        "reps": cleaned_data.get("reps"),
        "duration_seconds": cleaned_data.get("duration_seconds"),
        "distance_miles": cleaned_data.get("distance_miles"),
    }


@login_required
@require_POST
def submit_exercise(request):
    form = ExerciseInputForm(request.POST)

    if not form.is_valid():
        return JsonResponse(
            {
                "success": False,
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )


    # Prepare validated exercise data for the logging backend.
    data = build_exercise_data(form.cleaned_data)

    # TODO: Call log_exercise(request.user, data) once available.

    # Temporary response until backend integration is ready.
    return JsonResponse(
        {
            "success": False,
            "error": "Exercise logging is not implemented yet.",
        },
        status=501,
    )
