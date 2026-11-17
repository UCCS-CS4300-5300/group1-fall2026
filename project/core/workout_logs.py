"""Logging a whole workout: every exercise in it, as just performed.

The endpoint in views_workout.py is thin. The rule lives here: a workout is logged
all together or not at all, so a failure half way never leaves some exercises
counted toward RepKin's stats and others missing.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from .exercise_logging import log_exercise
from .exercises import SECTIONS, STAT_NAMES

# The exercise log keeps distance to two decimal places (presets keep three).
_TWO_PLACES = Decimal("0.01")


def exercise_data(item):
    """One validated workout item -> the flat dict log_exercise() expects.

    `item` is a WorkoutItemForm's cleaned_data, so weight and distance are already
    converted to the units we store (kilograms and miles). The weight is passed
    through so it is recorded with the log; it does not change the points.
    """
    distance = item.get("distance_miles")
    if distance is not None:
        distance = Decimal(distance).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    return {
        "exercise_type": item["exercise_type"],
        "sets": item.get("sets"),
        "reps": item.get("reps"),
        "duration_seconds": item.get("duration_seconds"),
        "distance_miles": distance,
        "weight_kg": item.get("weight_kg"),
    }


def log_workout(user, items):
    """Log every exercise in a validated workout, in the order it appears on the page.

    `items` is validate_payload()'s "items": {section: [cleaned exercise, ...]}.
    Returns the new ExerciseLog rows. All or nothing.
    """
    logs = []
    with transaction.atomic():
        for section in SECTIONS:
            for item in items.get(section, []):
                logs.append(log_exercise(user, exercise_data(item)))
    return logs


def stat_totals(logs):
    """How much strength, dexterity and endurance these logs added in all."""
    return {name: sum(getattr(log, name) for log in logs) for name in STAT_NAMES}
