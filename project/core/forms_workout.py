from decimal import Decimal

from django import forms

from .exercises import (
    DISTANCE, DURATION, EXERCISES, REPS, SECTIONS, exercise_label,
)
from .units import distance_to_miles, weight_to_kg

# Sanity limits, so a typo can't store something absurd.
MAX_SETS = 100
MAX_REPS = 1000
MAX_DURATION_SECONDS = 24 * 60 * 60
MAX_DISTANCE_MILES = Decimal("500")
MAX_WEIGHT_KG = Decimal("1000")

_SOME_NUMBER = dict(min_value=Decimal("0.01"), max_digits=8, decimal_places=2, required=False)


class WorkoutItemForm(forms.Form):
    """Checks one exercise being added to one section of a workout.

    `distance` and `weight` arrive in the user's unit system (miles or km, lb
    or kg). cleaned_data holds them converted to the units we store.
    """

    exercise_type = forms.ChoiceField(choices=[(key, exercise_label(key)) for key in EXERCISES])
    sets = forms.IntegerField(min_value=1, max_value=MAX_SETS, required=False)
    reps = forms.IntegerField(min_value=1, max_value=MAX_REPS, required=False)
    duration_seconds = forms.IntegerField(min_value=1, max_value=MAX_DURATION_SECONDS, required=False)
    distance = forms.DecimalField(**_SOME_NUMBER)
    weight = forms.DecimalField(**_SOME_NUMBER)

    def __init__(self, data, *, section, unit_system):
        # A box holding only spaces is an empty box.
        data = {
            key: None if isinstance(value, str) and not value.strip() else value
            for key, value in data.items()
        }
        super().__init__(data)
        self.section = section
        self.unit_system = unit_system

    def clean(self):
        cleaned = super().clean()
        exercise_type = cleaned.get("exercise_type")
        if exercise_type is None:
            return cleaned
        entry = EXERCISES[exercise_type]

        if self.section not in entry["sections"]:
            self.add_error(
                "exercise_type",
                f"{exercise_label(exercise_type)} can't be added to "
                f"\"{SECTIONS[self.section]}\".",
            )
            return cleaned

        input_type = entry["input_type"]
        required = {
            REPS: ("sets", "reps"),
            DURATION: ("duration_seconds",),
            DISTANCE: ("distance",),
        }[input_type]
        for field in required:
            if cleaned.get(field) is None and field not in self.errors:
                self.add_error(field, f"{field.replace('_', ' ').capitalize()} is required.")

        # Measurements that don't belong to this exercise are dropped.
        for field in {"sets", "reps", "duration_seconds", "distance"} - set(required):
            cleaned[field] = None

        self._clean_weight(cleaned, entry, exercise_type)
        self._convert_distance(cleaned)
        return cleaned

    def _clean_weight(self, cleaned, entry, exercise_type):
        raw = self.data.get("weight")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            cleaned["weight_kg"] = None            # no weight: bodyweight work
            return
        if not entry["weighted"]:
            self.add_error("weight", f"{exercise_label(exercise_type)} doesn't use a weight.")
            return
        weight = cleaned.get("weight")
        if weight is None:
            return                                  # the field itself already reported why
        kilos = weight_to_kg(weight, self.unit_system)
        if kilos > MAX_WEIGHT_KG:
            self.add_error("weight", "That weight is too heavy to be right.")
            return
        cleaned["weight_kg"] = kilos

    def _convert_distance(self, cleaned):
        distance = cleaned.get("distance")
        cleaned["distance_miles"] = None
        if distance is None:
            return
        miles = distance_to_miles(distance, self.unit_system)
        if miles > MAX_DISTANCE_MILES:
            self.add_error("distance", "That distance is too far to be right.")
            return
        cleaned["distance_miles"] = miles
