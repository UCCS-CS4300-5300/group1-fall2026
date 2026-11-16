from decimal import Decimal
from django import forms
from .exercises import EXERCISES, REPS, DURATION, DISTANCE

class ExerciseInputForm(forms.Form):
    EXERCISE_CHOICES = [
        (name, name.replace("_", " ").title())
        for name in EXERCISES
    ]

    REPETITION_EXERCISES = {
        name
        for name, info in EXERCISES.items()
        if info["input_type"] == REPS
    }

    DURATION_EXERCISES = {
        name
        for name, info in EXERCISES.items()
        if info["input_type"] == DURATION
    }

    DISTANCE_EXERCISES = {
        name
        for name, info in EXERCISES.items()
        if info["input_type"] == DISTANCE
    }

    exercise_type = forms.ChoiceField(
        choices=EXERCISE_CHOICES
    )

    sets = forms.IntegerField(
        min_value=1,
        required=False
    )

    reps = forms.IntegerField(
        min_value=1,
        required=False
    )

    duration_seconds = forms.IntegerField(
        min_value=1,
        required=False
    )

    distance_miles = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=7,
        decimal_places=2,
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        exercise_type = cleaned_data.get("exercise_type")

        if exercise_type in self.REPETITION_EXERCISES:
            required_fields = {"sets", "reps"}

        elif exercise_type in self.DURATION_EXERCISES:
            required_fields = {"duration_seconds"}

        elif exercise_type in self.DISTANCE_EXERCISES:
            required_fields = {"distance_miles"}

        else:
            return cleaned_data

        # Verify required measurements are present.
        for field in required_fields:
            if cleaned_data.get(field) is None:
                if field not in self.errors:
                    self.add_error(
                        field,
                        f"{field.replace('_', ' ').capitalize()} is required."
                    )

        # Remove measurements unrelated to the exercise.
        measurement_fields = {
            "sets",
            "reps",
            "duration_seconds",
            "distance_miles",
        }

        for field in measurement_fields - required_fields:
            cleaned_data[field] = None

        return cleaned_data
