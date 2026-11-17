"""Saving, loading, and describing workout presets.

The endpoints in views_workout.py are thin. The rules live here.
"""

import re

from django.db import IntegrityError, transaction
from django.db.models import Count

from .exercises import (
    EXERCISES, GROUPS, MAX_PER_SECTION, SECTIONS, exercise_label, exercises_for_section,
)
from .forms_workout import WorkoutItemForm
from .models_workout import MAX_NAME_LENGTH, MAX_PRESETS_PER_USER, Workout, WorkoutExercise
from .units import UNIT_SYSTEMS, check_system, kg_to_weight, miles_to_distance, unit_labels


class PresetValidationError(Exception):
    """The request wasn't a valid preset. `errors` says what to fix, and where."""

    def __init__(self, errors):
        super().__init__("invalid preset")
        self.errors = errors


class NameTaken(Exception):
    def __init__(self, existing_id):
        super().__init__("name taken")
        self.existing_id = existing_id


class TooManyPresets(Exception):
    pass


class PresetNotFound(Exception):
    pass


def _error(where, message, **where_details):
    return {"where": where, "message": message, **where_details}


def clean_name(raw):
    """One tidy line: whitespace collapsed, 1 to 40 characters."""
    if not isinstance(raw, str):
        return None
    name = re.sub(r"\s+", " ", raw).strip()
    return name or None


def validate_payload(payload, *, require_name=True):
    """Check a whole preset. Returns the cleaned pieces, or raises PresetValidationError.

    Logging a workout uses the same rules but has no name to check
    (`require_name=False`): the name is ignored and comes back as None.

    Expected shape:
        {"id": 12,                      (only when updating)
         "name": "Leg Day",
         "unit_system": "imperial",
         "sections": {"working_sets": [{"exercise_type": "back_squat",
                                        "sets": 3, "reps": 8, "weight": 135}, ...], ...}}
    """
    if not isinstance(payload, dict):
        raise PresetValidationError([_error("preset", "Send the workout as a JSON object.")])

    errors = []

    name = None
    if require_name:
        name = clean_name(payload.get("name"))
        if name is None:
            errors.append(_error("name", "Give your workout a name."))
        elif len(name) > MAX_NAME_LENGTH:
            errors.append(_error("name", f"The name can be at most {MAX_NAME_LENGTH} characters."))

    unit_system = payload.get("unit_system")
    if unit_system not in UNIT_SYSTEMS:
        errors.append(_error("preset", "unit_system must be \"imperial\" or \"si\"."))
        unit_system = None

    preset_id = payload.get("id")
    if preset_id is not None and (isinstance(preset_id, bool) or not isinstance(preset_id, int)):
        errors.append(_error("preset", "id must be a whole number."))
        preset_id = None

    sections = payload.get("sections")
    items = {key: [] for key in SECTIONS}
    if not isinstance(sections, dict):
        errors.append(_error("preset", "sections must be an object."))
        sections = {}

    for key in sections:
        if key not in SECTIONS:
            errors.append(_error("section", f"\"{key}\" is not one of the workout's sections.", section=key))

    for key in SECTIONS:
        raw_items = sections.get(key, [])
        if not isinstance(raw_items, list):
            errors.append(_error("section", "A section must be a list.", section=key))
            continue
        if len(raw_items) > MAX_PER_SECTION:
            errors.append(_error(
                "section", f"\"{SECTIONS[key]}\" can hold at most {MAX_PER_SECTION} exercises.",
                section=key,
            ))
            continue
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                errors.append(_error("item", "Each exercise must be an object.", section=key, index=index))
                continue
            if unit_system is None:
                continue                 # can't convert measurements without a unit system
            form = WorkoutItemForm(raw_item, section=key, unit_system=unit_system)
            if form.is_valid():
                items[key].append(form.cleaned_data)
            else:
                for field, field_errors in form.errors.items():
                    for message in field_errors:
                        errors.append(_error("item", message, section=key, index=index, field=field))

    if not errors and not any(items.values()):
        errors.append(_error("preset", "Add at least one exercise."))

    if errors:
        raise PresetValidationError(errors)
    return {"id": preset_id, "name": name, "unit_system": unit_system, "items": items}


def _create_items(workout, items):
    rows = []
    for section, section_items in items.items():
        for position, item in enumerate(section_items, start=1):
            rows.append(WorkoutExercise(
                workout=workout,
                section=section,
                position=position,
                exercise_type=item["exercise_type"],
                sets=item["sets"],
                reps=item["reps"],
                duration_seconds=item["duration_seconds"],
                distance_miles=item["distance_miles"],
                weight_kg=item["weight_kg"],
            ))
    WorkoutExercise.objects.bulk_create(rows)


def _find_clash(user, name, exclude_pk=None):
    """Another of this user's presets with the same name (ignoring capitals), if any."""
    clashes = Workout.objects.filter(user=user, name__iexact=name)
    if exclude_pk is not None:
        clashes = clashes.exclude(pk=exclude_pk)
    return clashes.first()


def save_preset(user, payload):
    """Create or update a preset for `user`. Returns (workout, created)."""
    cleaned = validate_payload(payload)
    name = cleaned["name"]

    try:
        with transaction.atomic():
            if cleaned["id"] is not None:
                workout = Workout.objects.filter(pk=cleaned["id"], user=user).first()
                if workout is None:
                    raise PresetNotFound()
                clash = _find_clash(user, name, exclude_pk=workout.pk)
                if clash:
                    raise NameTaken(clash.pk)
                workout.name = name
                workout.save()
                workout.exercises.all().delete()
                created = False
            else:
                clash = _find_clash(user, name)
                if clash:
                    raise NameTaken(clash.pk)
                if Workout.objects.filter(user=user).count() >= MAX_PRESETS_PER_USER:
                    raise TooManyPresets()
                workout = Workout.objects.create(user=user, name=name)
                created = True
            _create_items(workout, cleaned["items"])
    except IntegrityError:
        # Two saves with the same name landed at the same moment.
        clash = _find_clash(user, name)
        raise NameTaken(clash.pk if clash else None)
    return workout, created


def serialize_preset(workout, unit_system):
    """A preset as plain data, with weights and distances in the user's units."""
    check_system(unit_system)
    sections = {key: [] for key in SECTIONS}
    rows = sorted(workout.exercises.all(), key=lambda row: (list(SECTIONS).index(row.section), row.position))
    for row in rows:
        entry = EXERCISES[row.exercise_type]
        item = {
            "exercise_type": row.exercise_type,
            "label": exercise_label(row.exercise_type),
            "input_type": entry["input_type"],
        }
        if row.sets is not None:
            item["sets"] = row.sets
        if row.reps is not None:
            item["reps"] = row.reps
        if row.duration_seconds is not None:
            item["duration_seconds"] = row.duration_seconds
        if row.distance_miles is not None:
            item["distance"] = float(miles_to_distance(row.distance_miles, unit_system))
        if row.weight_kg is not None:
            item["weight"] = float(kg_to_weight(row.weight_kg, unit_system))
        sections[row.section].append(item)
    return {
        "id": workout.pk,
        "name": workout.name,
        "unit_system": unit_system,
        "units": unit_labels(unit_system),
        "sections": sections,
    }


def list_presets(user):
    # order_by is spelled out because Django ignores a model's default ordering
    # once a query adds a count.
    presets = (
        Workout.objects.filter(user=user)
        .annotate(exercise_count=Count("exercises"))
        .order_by("-updated_at", "-id")
    )
    return [
        {
            "id": preset.pk,
            "name": preset.name,
            "exercise_count": preset.exercise_count,
            "updated_at": preset.updated_at.isoformat(),
        }
        for preset in presets
    ]


def catalog_payload():
    """Everything the builder's picker needs: sections, and what each one offers."""
    def sort_key(key):
        return (GROUPS.index(EXERCISES[key]["group"]), exercise_label(key).lower())

    sections = []
    for key, title in SECTIONS.items():
        sections.append({
            "key": key,
            "title": title,
            "max_items": MAX_PER_SECTION,
            "exercises": [
                {
                    "key": exercise,
                    "label": exercise_label(exercise),
                    "group": EXERCISES[exercise]["group"],
                    "input_type": EXERCISES[exercise]["input_type"],
                    "weighted": EXERCISES[exercise]["weighted"],
                }
                for exercise in sorted(exercises_for_section(key), key=sort_key)
            ],
        })
    return {
        "sections": sections,
        "limits": {"max_per_section": MAX_PER_SECTION, "max_name_length": MAX_NAME_LENGTH,
                   "max_presets": MAX_PRESETS_PER_USER},
    }
