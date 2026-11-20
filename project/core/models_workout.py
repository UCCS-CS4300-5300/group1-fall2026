from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from .exercises import MAX_PER_SECTION, SECTIONS
from .models_exercise import ExerciseLog

MAX_NAME_LENGTH = 40
MAX_PRESETS_PER_USER = 50


class Workout(models.Model):
    """A workout preset: a named plan a user builds once and can load again."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workouts",
    )
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            # "Leg Day" and "leg day" are the same name, for the same person.
            models.UniqueConstraint(
                Lower("name"), "user", name="unique_workout_name_per_user"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"


class WorkoutExercise(models.Model):
    """One exercise inside a preset, in one of its four sections."""

    SECTION_CHOICES = list(SECTIONS.items())

    workout = models.ForeignKey(
        Workout,
        on_delete=models.CASCADE,
        related_name="exercises",
    )
    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    position = models.PositiveSmallIntegerField()   # 1 = first in its section
    exercise_type = models.CharField(max_length=40, choices=ExerciseLog.EXERCISE_CHOICES)

    # Only the measurements that apply to the exercise are filled in.
    sets = models.PositiveIntegerField(null=True, blank=True)
    reps = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    distance_miles = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workout", "section", "position"],
                name="unique_position_within_section",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1, position__lte=MAX_PER_SECTION),
                name="position_within_section_limit",
            ),
        ]

    def __str__(self):
        return f"{self.workout.name}: {self.get_exercise_type_display()} ({self.section} #{self.position})"
