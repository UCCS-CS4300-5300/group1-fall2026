"""Imperial and SI (metric) units.

The user's choice lives in the browser (main_menu.js saves "lbs" or "kgs" under
the key "repkinz.unit"), so the server never guesses: each request says which
system the numbers are in, and ALL conversion happens here, in one place.

What we store:
    weight    in kilograms   (3 decimal places)
    distance  in miles       (3 decimal places in presets, 2 in the exercise log)
What we show: weight to 1 decimal place, distance to 2.
"""

from decimal import ROUND_HALF_UP, Decimal

IMPERIAL = "imperial"
SI = "si"
UNIT_SYSTEMS = (IMPERIAL, SI)

KG_PER_LB = Decimal("0.45359237")
KM_PER_MILE = Decimal("1.609344")

WEIGHT_UNIT = {IMPERIAL: "lb", SI: "kg"}
DISTANCE_UNIT = {IMPERIAL: "mi", SI: "km"}

# The two values main_menu.js can save in the browser.
BROWSER_CHOICES = {"lbs": IMPERIAL, "kgs": SI}


def check_system(system):
    if system not in UNIT_SYSTEMS:
        raise ValueError(f"Unknown unit system: {system!r}")
    return system


def system_from_browser_choice(value, default=IMPERIAL):
    """Turn the browser's "lbs" / "kgs" into IMPERIAL / SI."""
    return BROWSER_CHOICES.get(value, default)


def unit_labels(system):
    check_system(system)
    return {"weight": WEIGHT_UNIT[system], "distance": DISTANCE_UNIT[system]}


def _round(value, places):
    exponent = Decimal(1).scaleb(-places)
    return Decimal(value).quantize(exponent, rounding=ROUND_HALF_UP)


def weight_to_kg(value, system):
    """What the user typed -> what we store."""
    check_system(system)
    value = Decimal(value)
    return _round(value * KG_PER_LB if system == IMPERIAL else value, 3)


def kg_to_weight(kg, system):
    """What we stored -> what the user sees."""
    check_system(system)
    kg = Decimal(kg)
    return _round(kg / KG_PER_LB if system == IMPERIAL else kg, 1)


def distance_to_miles(value, system):
    """What the user typed -> what we store."""
    check_system(system)
    value = Decimal(value)
    return _round(value if system == IMPERIAL else value / KM_PER_MILE, 3)


def miles_to_distance(miles, system):
    """What we stored -> what the user sees."""
    check_system(system)
    miles = Decimal(miles)
    return _round(miles if system == IMPERIAL else miles * KM_PER_MILE, 2)


def miles_for_exercise_log(miles):
    """The exercise log keeps distance to 2 decimal places."""
    return _round(miles, 2)
