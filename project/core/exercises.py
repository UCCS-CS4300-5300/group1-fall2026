REPS = "reps"
DURATION = "duration"
DISTANCE = "distance"

STAT_NAMES = ("strength", "dexterity", "endurance")

EXERCISES = {
    "push_ups":          {"input_type": REPS,     "split": {"strength": 80, "endurance": 20}},
    "sit_ups":           {"input_type": REPS,     "split": {"strength": 60, "endurance": 40}},
    "squats":            {"input_type": REPS,     "split": {"strength": 70, "endurance": 30}},
    "curls":             {"input_type": REPS,     "split": {"strength": 100}},
    "lunges":            {"input_type": REPS,     "split": {"strength": 50, "dexterity": 30, "endurance": 20}},
    "planks":            {"input_type": DURATION, "split": {"strength": 40, "endurance": 60}},
    "butterfly_stretch": {"input_type": DURATION, "split": {"dexterity": 100}},
    "shoulder_stretch":  {"input_type": DURATION, "split": {"dexterity": 100}},
    "walking":           {"input_type": DISTANCE, "split": {"endurance": 100}},
    "jogging":           {"input_type": DISTANCE, "split": {"dexterity": 20, "endurance": 80}},
    "running":           {"input_type": DISTANCE, "split": {"dexterity": 30, "endurance": 70}},
}

# How much effort each unit is worth, so different exercise types are comparable.
POINTS_PER_REP = 1      # 3 sets x 10 reps = 30 points
SECONDS_PER_POINT = 2   # 60 second plank = 30 points
POINTS_PER_MILE = 40    # 1 mile = 40 points


def effort_points(exercise_type, data):
    """Total effort for one workout, before splitting into stats."""
    input_type = EXERCISES[exercise_type]["input_type"]

    if input_type == REPS:
        return data["sets"] * data["reps"] * POINTS_PER_REP
    if input_type == DURATION:
        return data["duration_seconds"] / SECONDS_PER_POINT
    return float(data["distance_miles"]) * POINTS_PER_MILE


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