import pytest
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

from core.models_repkin import Repkin
from core.repkin_looks import (
    COLOR_BASE_SPRITES,
    LEVEL_COUNT,
    next_limb_level,
    parse_limb_level,
    sprite_for,
)

LOCKER = "core:locker_room"


@pytest.fixture
def logged_in_client(client, db):
    user = User.objects.create_user("flexer", password="pw12345!")
    # Start each test with an owned Repkin at its default sprite levels.
    # Full strength and endurance unlock every arm and leg level, so these
    # tests check saving and drawing sprites, not the unlock rules
    # (those are covered in test_stat_bar_evolutions.py).
    Repkin.objects.create(
        owner=user, mood="content", color="green", strength=300, endurance=300
    )
    client.force_login(user)
    return client

# Check that limb-level input is normalized and cycles correctly.
@pytest.mark.parametrize("value, expected", [("0", 0), ("1", 1), ("3", 3)])
def test_valid_limb_levels_are_kept(value, expected):
    assert parse_limb_level(value) == expected


@pytest.mark.parametrize("value", [None, "", "banana", "-1", "4", "1.5"])
def test_invalid_limb_levels_fall_back_to_no_limbs(value):
    assert parse_limb_level(value) == 0


@pytest.mark.parametrize("level, expected", [(0, 1), (1, 2), (2, 3), (3, 0)])
def test_next_limb_level_moves_forward_and_wraps(level, expected):
    assert next_limb_level(level) == expected

# Check all supported green arm and leg combinations.
def test_green_sprite_matrix_has_every_limb_combination():
    sprites = [
        sprite_for("green", arms, legs)
        for arms in range(LEVEL_COUNT)
        for legs in range(LEVEL_COUNT)
    ]
    assert len(set(sprites)) == LEVEL_COUNT * LEVEL_COUNT
    assert all(finders.find(path) for path in sprites)

@pytest.mark.parametrize(
    ("arms", "legs", "filename"),
    [
        (1, 1, "CS5300Sprite_Base_Green_Idle_Leg1_Arms1.gif"),
        (2, 2, "CS5300Sprite_Base_Green_Idle_Leg2_Arms2.gif"),
    ],
)
def test_green_same_stage_arms_and_legs_use_idle_sprite(arms, legs, filename):
    assert sprite_for("green", arms, legs) == (
        "gifs/Repkins/Green/Arms and Legs/Idle/" + filename
    )

# Check that every supplied purple regular sprite is selected from the mapping.
def test_purple_sprite_matrix_uses_all_supplied_idle_assets():
    sprites = {
        sprite_for("purple", arms, legs)
        for arms in range(LEVEL_COUNT)
        for legs in range(LEVEL_COUNT)
    }
    assert len(sprites) == LEVEL_COUNT * LEVEL_COUNT
    assert all(finders.find(path) for path in sprites)


def test_blue_sprite_matrix_uses_all_supplied_idle_assets():
    sprites = {
        sprite_for("blue", arms, legs)
        for arms in range(LEVEL_COUNT)
        for legs in range(LEVEL_COUNT)
    }

    assert len(sprites) == LEVEL_COUNT * LEVEL_COUNT
    assert all(finders.find(path) for path in sprites)


# Check that every supplied red sprite is selected from the mapping.
def test_red_sprite_matrix_uses_all_supplied_idle_assets():
    sprites = {
        sprite_for("red", arms, legs)
        for arms in range(LEVEL_COUNT)
        for legs in range(LEVEL_COUNT)
    }
    assert len(sprites) == LEVEL_COUNT * LEVEL_COUNT
    assert all(finders.find(path) for path in sprites)

# Check colors without limb art keep their own base sprite.
@pytest.mark.parametrize("color", ["yellow"])
def test_colors_without_limb_art_use_their_own_base_sprite(color):
    assert sprite_for(color, 2, 1) == COLOR_BASE_SPRITES[color]

# Check that valid sprite levels are stored on the owned Repkin.
def test_sprite_levels_are_saved(logged_in_client):
    response = logged_in_client.post(
        reverse("core:update_repkin_sprite"),
        {"arms_level": "2", "legs_level": "3"},
    )

    assert response.status_code == 200
    assert response.json() == {"arms_level": 2, "legs_level": 3}
    repkin = Repkin.objects.get(owner__username="flexer")
    assert repkin.arms_level == 2
    assert repkin.legs_level == 3

# Check invalid limb levels are rejected without changing saved values.
@pytest.mark.parametrize(
    "values",
    [
        {"arms_level": "x", "legs_level": "0"},
        {"arms_level": "0", "legs_level": "4"},
        {"arms_level": "-1", "legs_level": "0"},
    ],
)
def test_invalid_sprite_levels_are_rejected(logged_in_client, values):
    response = logged_in_client.post(reverse("core:update_repkin_sprite"), values)

    assert response.status_code == 400
    repkin = Repkin.objects.get(owner__username="flexer")
    assert repkin.arms_level == 0
    assert repkin.legs_level == 0


@pytest.mark.parametrize(
    ("color", "arms", "legs", "expected_fragment"),
    [
        ("green", 0, 0, "Green_Tired_Leg0_Arms0.gif"),
        ("green", 2, 3, "Green_Tired_Leg3_Arms2.gif"),
        ("blue", 0, 0, "Blue_Tired_Leg0_Arms0.gif"),
        ("blue", 2, 3, "Blue_Tired_Leg3_Arms2.gif"),
        ("red", 0, 0, "Red_Tired_Leg0_Arms0.gif"),
        ("red", 3, 2, "Red_Tired_Leg2_Arms3.gif"),
    ],
)
def test_tired_sprite_for_supported_colors(logged_in_client, color, arms, legs, expected_fragment):
    from core.repkin_looks import sprite_for

    sprite_path = sprite_for(color, arms, legs, is_tired=True)
    assert expected_fragment in sprite_path
    assert finders.find(sprite_path)


def test_purple_tired_sprite_matrix_uses_all_supplied_assets():
    sprites = {
        sprite_for("purple", arms, legs, is_tired=True)
        for arms in range(LEVEL_COUNT)
        for legs in range(LEVEL_COUNT)
    }

    assert len(sprites) == LEVEL_COUNT * LEVEL_COUNT
    assert all(finders.find(path) for path in sprites)


def test_blue_tired_sprite_matrix_uses_all_supplied_assets():
    sprites = {
        sprite_for("blue", arms, legs, is_tired=True)
        for arms in range(LEVEL_COUNT)
        for legs in range(LEVEL_COUNT)
    }

    assert len(sprites) == LEVEL_COUNT * LEVEL_COUNT
    assert all(finders.find(path) for path in sprites)


@pytest.mark.parametrize("color", ["green", "purple", "blue", "red"])
def test_tired_state_is_saved_and_rendered_on_both_pages(logged_in_client, color):
    repkin = Repkin.objects.get(owner__username="flexer")
    repkin.is_tired = True
    repkin.save(update_fields=["is_tired"])
    assert Repkin.objects.get(pk=repkin.pk).is_tired is True

    repkin.color = color
    repkin.save(update_fields=["color"])
    tired_path = sprite_for(color, 0, 0, is_tired=True)
    for url_name in ("core:home", LOCKER):
        page = logged_in_client.get(reverse(url_name))
        assert page.context["repkin_sprite"] == tired_path

# Check saved sprite selections render on both main pages.
def test_saved_sprite_is_rendered_on_both_pages(logged_in_client):
    logged_in_client.post(
        reverse("core:update_repkin_sprite"),
        {"arms_level": "1", "legs_level": "2"},
    )
    sprite_path = sprite_for("green", 1, 2)

    for url_name in ("core:home", LOCKER):
        response = logged_in_client.get(reverse(url_name))
        assert response.context["repkin_sprite"] == sprite_path
        assert static(sprite_path).encode() in response.content

# Check the selected color and saved limb levels render together.
def test_saved_color_and_sprite_are_rendered_together(logged_in_client):
    repkin = Repkin.objects.get(owner__username="flexer")
    repkin.color = "purple"
    repkin.arms_level = 1
    repkin.legs_level = 2
    repkin.save()

    for url_name in ("core:home", LOCKER):
        response = logged_in_client.get(reverse(url_name))
        assert response.context["repkin"].color == "purple"
        assert response.context["repkin_sprite"] == sprite_for("purple", 1, 2)

# Check base-fallback sprites receive the vertical alignment class.
@pytest.mark.parametrize(
    ("color", "legs_level", "aligned"),
    [
        ("blue", 0, True),
        ("blue", 1, False),
        ("green", 0, True),
        ("green", 1, False),
        ("purple", 0, True),
        ("purple", 1, False),
        ("red", 0, True),
        ("yellow", 1, True),
    ],
)
@pytest.mark.parametrize("url_name", ["core:home", LOCKER])
def test_sprite_vertical_alignment(logged_in_client, color, legs_level, aligned, url_name):
    repkin = Repkin.objects.get(owner__username="flexer")
    repkin.color = color
    repkin.legs_level = legs_level
    repkin.save()

    response = logged_in_client.get(reverse(url_name))

    assert (b"non-green-no-legs" in response.content) is aligned


def test_locker_room_requires_login(client, db):
    response = client.get(reverse(LOCKER))
    assert response.status_code == 302
