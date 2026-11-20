"""Map Repkin colors and limb levels to their available sprite assets."""

# Keep the supported levels and available color base sprites together.
LEVEL_COUNT = 4
COLORS_WITHOUT_LIMB_SPRITES = {"blue", "purple", "yellow"}
COLOR_BASE_SPRITES = {
    "green": "gifs/Repkins/Green/Base/CS5300Sprite_Base_Green_Idle.gif",
    "blue": "gifs/Repkins/Blue/Base/CS5300Sprite_Base.gif",
    "purple": "gifs/Repkins/Purple/Base/CS5300Sprite_Base.gif",
    "red": "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg0_Arms0.gif",
    "yellow": "gifs/Repkins/Yellow/Base/CS5300Sprite_Base.gif",
}

# Map each available color and limb-level combination to its sprite file.
SPRITES = {
    ("green", 1, 0): "gifs/Repkins/Green/Arms/CS5300Sprite_Arms1_Green_Idle.gif",
    ("green", 2, 0): "gifs/Repkins/Green/Arms/CS5300Sprite_Arms2_Green_Idle.gif",
    ("green", 3, 0): "gifs/Repkins/Green/Arms/CS5300Sprite_Arms3_Green_Idle.gif",
    ("green", 0, 1): "gifs/Repkins/Green/Legs/CS5300Sprite_Legs1_Green_Idle.gif",
    ("green", 0, 2): "gifs/Repkins/Green/Legs/CS5300Sprite_Legs2_Green_Idle.gif",
    ("green", 0, 3): "gifs/Repkins/Green/Legs/CS5300Sprite_Legs3_Green_Idle-.gif",
    ("green", 1, 1): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Base_Green_Idle_Leg1_Arms1.gif",
    ("green", 2, 1): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Legs_1_Arms_2_Green_Idle.gif",
    ("green", 3, 1): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Legs_1_Arms_3_Green_Idle.gif",
    ("green", 1, 2): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Legs_2_Arms_1_Green_Idle.gif",
    ("green", 2, 2): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Base_Green_Idle_Leg2_Arms2.gif",
    ("green", 3, 2): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Legs_2_Arms_3_Green_Idle.gif",
    ("green", 1, 3): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Legs_3_Arms_1_Green_Idle.gif",
    ("green", 2, 3): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Legs_3_Arms_2_Green_Idle.gif",
    ("green", 3, 3): "gifs/Repkins/Green/Arms and Legs/Idle/CS5300Sprite_Both_3_Green_Idle.gif",
    ("red", 1, 0): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg0_Arms1.gif",
    ("red", 2, 0): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg0_Arms2.gif",
    ("red", 3, 0): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg0_Arms3.gif",
    ("red", 0, 1): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg1_Arms0.gif",
    ("red", 1, 1): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg1_Arms1.gif",
    ("red", 2, 1): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg1_Arms2.gif",
    ("red", 3, 1): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg1_Arms3.gif",
    ("red", 0, 2): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg2_Arms0.gif",
    ("red", 1, 2): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg2_Arms1.gif",
    ("red", 2, 2): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg2_Arms2.gif",
    ("red", 3, 2): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg2_Arms3.gif",
    ("red", 0, 3): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg3_Arms0.gif",
    ("red", 1, 3): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg3_Arms1.gif",
    ("red", 2, 3): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg3_Arms2.gif",
    ("red", 3, 3): "gifs/Repkins/Red/Arms and Legs/CS5300Sprite_Base_Red_Idle_Leg3_Arms3.gif",
}


# Normalize saved values to one of the supported limb levels.
def parse_limb_level(value):
    """Return a valid saved limb level; invalid values mean no limbs."""
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 0
    if 0 <= level < LEVEL_COUNT:
        return level
    return 0


# Advance to the next level and wrap back to zero at the end.
def next_limb_level(level):
    """Return the next limb level, wrapping back to 0 after the last."""
    return (level + 1) % LEVEL_COUNT


# Select the mapped sprite or fall back to that color's base sprite.
def sprite_for(color, arms_level, legs_level):
    """Return an explicitly mapped sprite, or that color's base art until added."""
    color = color if color in COLOR_BASE_SPRITES else "green"
    arms_level = parse_limb_level(arms_level)
    legs_level = parse_limb_level(legs_level)
    return SPRITES.get((color, arms_level, legs_level), COLOR_BASE_SPRITES[color])


# Identify base sprites that need a vertical offset for alignment.
def sprite_needs_vertical_offset(color, legs_level):
    """Whether the current no-legs art needs alignment for its taller canvas."""
    if color in COLORS_WITHOUT_LIMB_SPRITES:
        return True
    return color == "red" and parse_limb_level(legs_level) == 0


# Build the sprite URL matrix used by the locker-room controls.
def sprite_urls_for(color):
    """Return the sprite URL matrix used by the locker-room controls."""
    return {
        str(arms): {
            str(legs): sprite_for(color, arms, legs)
            for legs in range(LEVEL_COUNT)
        }
        for arms in range(LEVEL_COUNT)
    }
