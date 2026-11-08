import logging

from django.db import transaction

from .exercises import calculate_stats
from .models_exercise import ExerciseLog
from .models_repkin import Repkin

logger = logging.getLogger(__name__)

# Same defaults the home page uses when it creates a Repkin.
DEFAULT_REPKIN = {"mood": "content", "color": "green"}


def log_exercise(user, data):
    """
    Save one workout to the user's exercise history and send its stats on.

    `data` is the flat dict from the exercise form, for example:
    {"exercise_type": "push_ups", "sets": 3, "reps": 10,
     "duration_seconds": None, "distance_miles": None}

    All saving happens here, so moving exercise history to Firebase later
    only means changing this function.
    """
    exercise_type = data["exercise_type"]
    stats = calculate_stats(exercise_type, data)

    with transaction.atomic():
        log = ExerciseLog.objects.create(
            user=user,
            exercise_type=exercise_type,
            sets=data.get("sets"),
            reps=data.get("reps"),
            duration_seconds=data.get("duration_seconds"),
            distance_miles=data.get("distance_miles"),
            **stats,
        )
        send_stats_to_repkin(user, stats, log.logged_at)

    logger.info("Logged %s for %s: %s", exercise_type, user, stats)
    return log


def send_stats_to_repkin(user, stats, timestamp):
    """
    Add a workout's stats to the user's weekly Repkin progress.

    They go into the progress stats, not the real stats. Brandon's
    add_prog_to_stats() moves them into the real stats at the end of the week.
    """
    repkin, _ = Repkin.objects.get_or_create(owner=user, defaults=DEFAULT_REPKIN)
    repkin.update_progress(stats)
    repkin.save()
    logger.debug("Added %s to %s's Repkin progress at %s", stats, user, timestamp)
