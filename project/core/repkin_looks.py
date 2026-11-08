"""
The Repkin arm versions shown in the locker room, in order.

Clicking the Arms arrow moves to the next one, and after the last
one it goes back to the first.
"""

ARM_VERSIONS = [
    "gifs/Repkins/Green/Base/CS5300Sprite_Base_Green_Idle.gif",   # no arms
    "gifs/Repkins/Green/Arms/CS5300Sprite_Arms1_Green_Idle.gif",  # small arms
    "gifs/Repkins/Green/Arms/CS5300Sprite_Arms2_Green_Idle.gif",  # bigger arms
    "gifs/Repkins/Green/Arms/CS5300Sprite_Arms3_Green_Idle.gif",  # muscular arms
]


def parse_arm_level(value):
    """Turn the ?arms= value into a valid level. Anything invalid means 0 (no arms)."""
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 0
    if 0 <= level < len(ARM_VERSIONS):
        return level
    return 0


def next_arm_level(level):
    """The level after this one, wrapping back to 0 after the last."""
    return (level + 1) % len(ARM_VERSIONS)
