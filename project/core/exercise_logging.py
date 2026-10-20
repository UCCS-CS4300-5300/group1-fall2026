import logging

from django.db import transaction

from .exercises import calculate_stats
from .models_exercise import ExerciseLog

logger = logging.getLogger(__name__)


def log_exercise(user, data):

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

    logger.debug("Stats ready for %s's Repkin at %s: %s", user, timestamp, stats)