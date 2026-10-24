from django.conf import settings
from django.db import models

from .exercises import EXERCISES


class ExerciseLog(models.Model):
    """One completed workout entry in a user's exercise history."""

    EXERCISE_CHOICES = [
        (key, key.replace("_", " ").title()) for key in EXERCISES
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exercise_logs",
    )
    exercise_type = models.CharField(max_length=40, choices=EXERCISE_CHOICES)

    # Only the fields that apply to the exercise are filled in.
    sets = models.PositiveIntegerField(null=True, blank=True)
    reps = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    distance_miles = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )

    # The stats this workout earned, kept as a record.
    strength = models.PositiveIntegerField(default=0)
    dexterity = models.PositiveIntegerField(default=0)
    endurance = models.PositiveIntegerField(default=0)

    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at"]

    def __str__(self):
        return f"{self.user} - {self.get_exercise_type_display()} ({self.logged_at:%Y-%m-%d %H:%M})"