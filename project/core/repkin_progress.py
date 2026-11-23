"""
Stat bar and evolution unlock rules for the Repkin.

All the numbers live here, so the team can rebalance in one place.
"""
from django.db.models import Sum

from .exercises import STAT_NAMES

# Each stat bar has 3 segments, one per 100 points, so a full bar is 300.
POINTS_PER_SEGMENT = 100
SEGMENT_COUNT = 3
FULL_BAR_POINTS = POINTS_PER_SEGMENT * SEGMENT_COUNT

# Points needed for each limb level. Level 0 is always unlocked.
LEVEL_THRESHOLDS = (0, 100, 200, 300)

# Which stat unlocks which limb.
LIMB_STATS = {"arms": "strength", "legs": "endurance"}

STAT_BAR_IMAGE = "img/stat_bars/{stat}_{segment}.png"


def current_stats(repkin):
    """Real stats plus this week's progress, which is what the stat bar shows."""
    return {
        name: getattr(repkin, name) + getattr(repkin, f"progress_{name}")
        for name in STAT_NAMES
    }


def bar_segments(points):
    """How many bar segments are lit for this many points (0 to 3)."""
    if points <= 0:
        return 0
    return min(SEGMENT_COUNT, points // POINTS_PER_SEGMENT)


def stat_bar_images(repkin):
    """The overlay images to stack on the empty bar. Each stat fills on its own."""
    stats = current_stats(repkin)
    return [
        STAT_BAR_IMAGE.format(stat=name, segment=segment)
        for name in STAT_NAMES
        for segment in range(1, bar_segments(stats[name]) + 1)
    ]


def max_unlocked_level(points):
    """The highest limb level these points unlock."""
    level = 0
    for candidate, needed in enumerate(LEVEL_THRESHOLDS):
        if points >= needed:
            level = candidate
    return level


def unlocked_levels(repkin):
    """The highest unlocked arms and legs levels for this Repkin."""
    stats = current_stats(repkin)
    return {limb: max_unlocked_level(stats[stat]) for limb, stat in LIMB_STATS.items()}


def next_unlock_message(limb, unlocked):
    """A short hint telling the user what unlocks the next level."""
    if unlocked >= len(LEVEL_THRESHOLDS) - 1:
        return f"All {limb} levels are unlocked."
    needed = LEVEL_THRESHOLDS[unlocked + 1]
    return f"{limb.title()} level {unlocked + 1} unlocks at {needed} {LIMB_STATS[limb]}."


def lifetime_stats(user):
    """Everything this user has earned across their whole workout history."""
    totals = user.exercise_logs.aggregate(**{name: Sum(name) for name in STAT_NAMES})
    return {name: totals[name] or 0 for name in STAT_NAMES}
