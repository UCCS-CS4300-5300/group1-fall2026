"""The catalog of exercises RepKin knows about.

Every exercise is one entry in EXERCISES. To add an exercise, add one line
there; the exercise forms, the database choices, the workout builder, and the
tests all read from this list, so nothing else needs editing. Keep the keys of
existing exercises exactly as they are, because saved history refers to them.

Each entry says:
    input_type       what the user measures: reps (sets x reps), duration, or distance
    split            how its effort becomes strength / dexterity / endurance (adds up to 100)
    sections         which parts of a workout it can be added to
    group            the heading it appears under in the picker
    weighted         True if the user may also record the weight they used
    label            (optional) how its name is shown, when title-casing the key is not right
    points_per_mile  (optional, distance exercises) overrides POINTS_PER_MILE
"""

REPS = "reps"
DURATION = "duration"
DISTANCE = "distance"

STAT_NAMES = ("strength", "dexterity", "endurance")

# ---- The four parts of a workout, in the order they appear on the page ------
WARMUP_STRETCH = "warmup_stretch"
WARMUP_SETS = "warmup_sets"
WORKING_SETS = "working_sets"
COOLDOWN_STRETCH = "cooldown_stretch"

SECTIONS = {
    WARMUP_STRETCH: "Warm up and stretches",
    WARMUP_SETS: "Warm-up sets/exercises",
    WORKING_SETS: "Working sets/exercises",
    COOLDOWN_STRETCH: "Cooldown and stretches",
}
MAX_PER_SECTION = 5

# ---- Headings used to organise the picker ------------------------------------
GROUPS = (
    "Legs", "Chest", "Back", "Shoulders", "Arms", "Core",
    "Full body", "Cardio", "Mobility", "Stretches",
)

_WS, _WU, _WK, _CD = WARMUP_STRETCH, WARMUP_SETS, WORKING_SETS, COOLDOWN_STRETCH


def _exercise(input_type, split, sections, group, weighted=False, label=None,
              points_per_mile=None):
    entry = {
        "input_type": input_type,
        "split": split,
        "sections": tuple(sections),
        "group": group,
        "weighted": weighted,
    }
    if label is not None:
        entry["label"] = label
    if points_per_mile is not None:
        entry["points_per_mile"] = points_per_mile
    return entry


EXERCISES = {
    # ---- The original exercises. Do not rename these keys. -----------------------
    "push_ups":          _exercise(REPS,     {"strength": 80, "endurance": 20}, (_WU, _WK), "Chest"),
    "sit_ups":           _exercise(REPS,     {"strength": 60, "endurance": 40}, (_WU, _WK), "Core"),
    "squats":            _exercise(REPS,     {"strength": 70, "endurance": 30}, (_WU, _WK), "Legs", weighted=True),
    "curls":             _exercise(REPS,     {"strength": 100},                 (_WU, _WK), "Arms", weighted=True),
    "lunges":            _exercise(REPS,     {"strength": 50, "dexterity": 30, "endurance": 20}, (_WU, _WK), "Legs", weighted=True),
    "planks":            _exercise(DURATION, {"strength": 40, "endurance": 60}, (_WU, _WK), "Core"),
    "butterfly_stretch": _exercise(DURATION, {"dexterity": 100},                (_WS, _CD), "Stretches"),
    "shoulder_stretch":  _exercise(DURATION, {"dexterity": 100},                (_WS, _CD), "Stretches"),
    "walking":           _exercise(DISTANCE, {"endurance": 100},                (_WS, _WK, _CD), "Cardio"),
    "jogging":           _exercise(DISTANCE, {"dexterity": 20, "endurance": 80}, (_WS, _WK), "Cardio"),
    "running":           _exercise(DISTANCE, {"dexterity": 30, "endurance": 70}, (_WK,), "Cardio"),

    # ---- Warm-up and mobility -------------------------------------------------------
    "jumping_jacks":     _exercise(REPS,     {"endurance": 70, "dexterity": 30}, (_WS, _WU), "Cardio"),
    "high_knees":        _exercise(DURATION, {"endurance": 70, "dexterity": 30}, (_WS, _WU), "Cardio"),
    "butt_kicks":        _exercise(DURATION, {"endurance": 70, "dexterity": 30}, (_WS,), "Cardio"),
    "jump_rope":         _exercise(DURATION, {"endurance": 80, "dexterity": 20}, (_WS, _WK), "Cardio"),
    "arm_circles":       _exercise(REPS,     {"dexterity": 80, "endurance": 20}, (_WS,), "Mobility"),
    "leg_swings":        _exercise(REPS,     {"dexterity": 80, "endurance": 20}, (_WS,), "Mobility"),
    "hip_circles":       _exercise(REPS,     {"dexterity": 80, "endurance": 20}, (_WS,), "Mobility"),
    "torso_twists":      _exercise(REPS,     {"dexterity": 70, "strength": 10, "endurance": 20}, (_WS,), "Mobility"),
    "ankle_circles":     _exercise(REPS,     {"dexterity": 100},                (_WS,), "Mobility"),
    "neck_rolls":        _exercise(REPS,     {"dexterity": 100},                (_WS,), "Mobility"),
    "cat_cow":           _exercise(REPS,     {"dexterity": 100},                (_WS, _CD), "Mobility", label="Cat-Cow"),
    "inchworm":          _exercise(REPS,     {"strength": 40, "dexterity": 60}, (_WS, _WU), "Mobility"),
    "worlds_greatest_stretch": _exercise(REPS, {"dexterity": 80, "strength": 20}, (_WS,), "Mobility", label="World's Greatest Stretch"),

    # ---- Stretches (held for a number of seconds) --------------------------------------
    "hamstring_stretch":   _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "quad_stretch":        _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "calf_stretch":        _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "hip_flexor_stretch":  _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "chest_stretch":       _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "triceps_stretch":     _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "lat_stretch":         _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "neck_stretch":        _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "figure_four_stretch": _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "spinal_twist":        _exercise(DURATION, {"dexterity": 100}, (_WS, _CD), "Stretches"),
    "seated_forward_fold": _exercise(DURATION, {"dexterity": 100}, (_CD,), "Stretches"),
    "childs_pose":         _exercise(DURATION, {"dexterity": 100}, (_CD,), "Stretches", label="Child's Pose"),
    "pigeon_pose":         _exercise(DURATION, {"dexterity": 100}, (_CD,), "Stretches"),
    "cobra_stretch":       _exercise(DURATION, {"dexterity": 100}, (_CD,), "Stretches"),

    # ---- Legs --------------------------------------------------------------------------------
    "back_squat":            _exercise(REPS, {"strength": 80, "endurance": 20}, (_WU, _WK), "Legs", weighted=True),
    "front_squat":           _exercise(REPS, {"strength": 75, "endurance": 25}, (_WU, _WK), "Legs", weighted=True),
    "goblet_squat":          _exercise(REPS, {"strength": 70, "endurance": 30}, (_WU, _WK), "Legs", weighted=True),
    "romanian_deadlift":     _exercise(REPS, {"strength": 80, "endurance": 20}, (_WU, _WK), "Legs", weighted=True),
    "leg_press":             _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Legs", weighted=True),
    "bulgarian_split_squat": _exercise(REPS, {"strength": 60, "dexterity": 25, "endurance": 15}, (_WU, _WK), "Legs", weighted=True),
    "hip_thrust":            _exercise(REPS, {"strength": 90, "endurance": 10}, (_WU, _WK), "Legs", weighted=True),
    "calf_raises":           _exercise(REPS, {"strength": 70, "endurance": 30}, (_WU, _WK), "Legs", weighted=True),
    "leg_curl":              _exercise(REPS, {"strength": 100}, (_WU, _WK), "Legs", weighted=True),
    "leg_extension":         _exercise(REPS, {"strength": 100}, (_WU, _WK), "Legs", weighted=True),
    "step_ups":              _exercise(REPS, {"strength": 50, "dexterity": 20, "endurance": 30}, (_WU, _WK), "Legs", weighted=True),
    "glute_bridge":          _exercise(REPS, {"strength": 70, "endurance": 30}, (_WU, _WK), "Legs"),
    "jump_squats":           _exercise(REPS, {"strength": 50, "dexterity": 20, "endurance": 30}, (_WU, _WK), "Legs"),
    "wall_sit":              _exercise(DURATION, {"strength": 60, "endurance": 40}, (_WU, _WK), "Legs"),

    # ---- Chest and push --------------------------------------------------------------------------
    "bench_press":          _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Chest", weighted=True),
    "incline_bench_press":  _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Chest", weighted=True),
    "dumbbell_bench_press": _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Chest", weighted=True),
    "chest_fly":            _exercise(REPS, {"strength": 100}, (_WU, _WK), "Chest", weighted=True),
    "diamond_push_ups":     _exercise(REPS, {"strength": 80, "endurance": 20}, (_WU, _WK), "Chest"),
    "overhead_press":       _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Shoulders", weighted=True),
    "lateral_raises":       _exercise(REPS, {"strength": 90, "dexterity": 10}, (_WU, _WK), "Shoulders", weighted=True),
    "front_raises":         _exercise(REPS, {"strength": 100}, (_WU, _WK), "Shoulders", weighted=True),
    "pike_push_ups":        _exercise(REPS, {"strength": 80, "dexterity": 10, "endurance": 10}, (_WU, _WK), "Shoulders"),
    "dips":                 _exercise(REPS, {"strength": 85, "endurance": 15}, (_WK,), "Arms", weighted=True),
    "tricep_extension":     _exercise(REPS, {"strength": 100}, (_WU, _WK), "Arms", weighted=True),
    "tricep_pushdown":      _exercise(REPS, {"strength": 100}, (_WU, _WK), "Arms", weighted=True),

    # ---- Back and pull ---------------------------------------------------------------------------------
    "deadlift":          _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Back", weighted=True),
    "pull_ups":          _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Back", weighted=True),
    "chin_ups":          _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Back", weighted=True),
    "lat_pulldown":      _exercise(REPS, {"strength": 90, "endurance": 10}, (_WU, _WK), "Back", weighted=True),
    "barbell_row":       _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Back", weighted=True),
    "dumbbell_row":      _exercise(REPS, {"strength": 85, "endurance": 15}, (_WU, _WK), "Back", weighted=True),
    "seated_cable_row":  _exercise(REPS, {"strength": 90, "endurance": 10}, (_WU, _WK), "Back", weighted=True),
    "back_extensions":   _exercise(REPS, {"strength": 90, "endurance": 10}, (_WU, _WK), "Back", weighted=True),
    "face_pulls":        _exercise(REPS, {"strength": 100}, (_WU, _WK), "Shoulders", weighted=True),
    "reverse_fly":       _exercise(REPS, {"strength": 100}, (_WU, _WK), "Shoulders", weighted=True),
    "shrugs":            _exercise(REPS, {"strength": 100}, (_WU, _WK), "Shoulders", weighted=True),
    "hammer_curls":      _exercise(REPS, {"strength": 100}, (_WU, _WK), "Arms", weighted=True),

    # ---- Core ---------------------------------------------------------------------------------------------------
    "crunches":          _exercise(REPS, {"strength": 60, "endurance": 40}, (_WU, _WK), "Core"),
    "bicycle_crunches":  _exercise(REPS, {"strength": 50, "endurance": 50}, (_WU, _WK), "Core"),
    "leg_raises":        _exercise(REPS, {"strength": 70, "endurance": 30}, (_WU, _WK), "Core"),
    "russian_twists":    _exercise(REPS, {"strength": 50, "dexterity": 20, "endurance": 30}, (_WU, _WK), "Core", weighted=True),
    "dead_bug":          _exercise(REPS, {"strength": 50, "dexterity": 50}, (_WU, _WK), "Core"),
    "bird_dog":          _exercise(REPS, {"strength": 40, "dexterity": 60}, (_WU, _WK), "Core"),
    "side_plank":        _exercise(DURATION, {"strength": 40, "endurance": 60}, (_WU, _WK), "Core"),
    "hollow_hold":       _exercise(DURATION, {"strength": 60, "endurance": 40}, (_WU, _WK), "Core"),
    "mountain_climbers": _exercise(DURATION, {"strength": 30, "dexterity": 10, "endurance": 60}, (_WU, _WK), "Core"),

    # ---- Full body and conditioning -------------------------------------------------------------------------------------
    "burpees":           _exercise(REPS, {"strength": 40, "endurance": 60}, (_WU, _WK), "Full body"),
    "kettlebell_swings": _exercise(REPS, {"strength": 60, "endurance": 40}, (_WU, _WK), "Full body", weighted=True),
    "thrusters":         _exercise(REPS, {"strength": 60, "endurance": 40}, (_WK,), "Full body", weighted=True),
    "box_jumps":         _exercise(REPS, {"strength": 50, "dexterity": 20, "endurance": 30}, (_WU, _WK), "Full body"),

    # ---- More cardio ---------------------------------------------------------------------------------------------------------
    # Cycling covers more ground per unit of effort than running, so a mile is worth less.
    "cycling":           _exercise(DISTANCE, {"dexterity": 10, "endurance": 90}, (_WS, _WK, _CD), "Cardio", points_per_mile=15),
    "elliptical":        _exercise(DURATION, {"endurance": 100}, (_WS, _WK, _CD), "Cardio"),
    "stair_climbing":    _exercise(DURATION, {"strength": 20, "endurance": 80}, (_WK,), "Cardio"),
    "rowing_machine":    _exercise(DURATION, {"strength": 30, "endurance": 70}, (_WK,), "Cardio"),
}

# How much effort each unit is worth, so different exercise types are comparable.
POINTS_PER_REP = 1      # 3 sets x 10 reps = 30 points
SECONDS_PER_POINT = 2   # 60 second plank = 30 points
POINTS_PER_MILE = 40    # 1 mile = 40 points (an exercise may override this)

# NOTE: the weight a user lifts is recorded, but it does not change the points.


def exercise_label(exercise_type):
    """How an exercise's name is shown to people."""
    entry = EXERCISES[exercise_type]
    return entry.get("label") or exercise_type.replace("_", " ").title()


def exercises_for_section(section):
    """The exercise keys that may be added to a section, in catalog order."""
    return [key for key, entry in EXERCISES.items() if section in entry["sections"]]


def effort_points(exercise_type, data):
    """Total effort for one workout, before splitting into stats."""
    entry = EXERCISES[exercise_type]
    input_type = entry["input_type"]

    if input_type == REPS:
        return data["sets"] * data["reps"] * POINTS_PER_REP
    if input_type == DURATION:
        return data["duration_seconds"] / SECONDS_PER_POINT
    per_mile = entry.get("points_per_mile", POINTS_PER_MILE)
    return float(data["distance_miles"]) * per_mile


def calculate_stats(exercise_type, data):
    """
    Split a workout's effort into strength, dexterity, and endurance.

    Example: 3 x 10 push ups -> {"strength": 24, "dexterity": 0, "endurance": 6}
    """
    points = effort_points(exercise_type, data)
    split = EXERCISES[exercise_type]["split"]
    return {
        stat: round(points * split.get(stat, 0) / 100)
        for stat in STAT_NAMES
    }
