from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

from core.exercise_logging import log_exercise
from core.exercises import STAT_NAMES
from core.models_repkin import Repkin
from core.repkin_looks import LEVEL_COUNT, sprite_for
from core.repkin_progress import (
    LEVEL_THRESHOLDS,
    SEGMENT_COUNT,
    STAT_BAR_IMAGE,
    bar_segments,
    current_stats,
    lifetime_stats,
    max_unlocked_level,
    next_unlock_message,
    stat_bar_images,
    unlocked_levels,
)

LOCKER = "core:locker_room"
SAVE_SPRITE = "core:update_repkin_sprite"


def flat(exercise_type, sets=None, reps=None, duration_seconds=None, distance_miles=None):
    return {
        "exercise_type": exercise_type,
        "sets": sets,
        "reps": reps,
        "duration_seconds": duration_seconds,
        "distance_miles": distance_miles,
    }


@pytest.fixture
def user(db):
    return User.objects.create_user("lifter", password="pw12345!")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("runner", password="pw12345!")


@pytest.fixture
def repkin(user):
    return Repkin.objects.create(
        owner=user, mood="content", color="green",
        strength=0, dexterity=0, endurance=0,
    )


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


def give_points(repkin, strength=0, dexterity=0, endurance=0):
    repkin.set_stats({"strength": strength, "dexterity": dexterity, "endurance": endurance})
    repkin.save()


# The rules vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_there_is_one_threshold_per_limb_level():
    assert len(LEVEL_THRESHOLDS) == LEVEL_COUNT
    assert LEVEL_THRESHOLDS[0] == 0


@pytest.mark.parametrize(
    "points, segments",
    [(-5, 0), (0, 0), (99, 0), (100, 1), (199, 1), (200, 2), (299, 2), (300, 3), (1000, 3)],
)
def test_bar_segments_fill_every_100_points_and_stop_at_full(points, segments):
    assert bar_segments(points) == segments


@pytest.mark.parametrize(
    "points, level",
    [(0, 0), (99, 0), (100, 1), (199, 1), (200, 2), (300, 3), (5000, 3)],
)
def test_limb_levels_unlock_at_each_threshold(points, level):
    assert max_unlocked_level(points) == level


def test_every_stat_bar_image_exists():
    assert finders.find("img/stat_bars/stat_bars_base.png")
    for name in STAT_NAMES:
        for segment in range(1, SEGMENT_COUNT + 1):
            assert finders.find(STAT_BAR_IMAGE.format(stat=name, segment=segment))


@pytest.mark.parametrize(
    "limb, unlocked, message",
    [
        ("arms", 0, "Arms level 1 unlocks at 100 strength."),
        ("legs", 2, "Legs level 3 unlocks at 300 endurance."),
        ("arms", 3, "All arms levels are unlocked."),
    ],
)
def test_unlock_messages_tell_the_user_what_is_next(limb, unlocked, message):
    assert next_unlock_message(limb, unlocked) == message


# The stat bar vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_bar_shows_real_stats_plus_this_weeks_progress(repkin):
    give_points(repkin, strength=60, dexterity=10, endurance=0)
    repkin.set_progress({"strength": 50, "dexterity": 0, "endurance": 30})
    repkin.save()

    assert current_stats(repkin) == {"strength": 110, "dexterity": 10, "endurance": 30}


def test_new_repkin_with_no_points_has_an_empty_bar(repkin):
    assert stat_bar_images(repkin) == []


def test_each_stat_fills_its_own_bar(repkin):
    give_points(repkin, strength=250, dexterity=0, endurance=100)

    assert stat_bar_images(repkin) == [
        "img/stat_bars/strength_1.png",
        "img/stat_bars/strength_2.png",
        "img/stat_bars/endurance_1.png",
    ]


def test_locker_room_draws_the_lit_segments(logged_in_client, repkin):
    give_points(repkin, dexterity=300)
    content = logged_in_client.get(reverse(LOCKER)).content.decode()

    assert static("img/stat_bars/stat_bars_base.png") in content
    for segment in (1, 2, 3):
        assert static(f"img/stat_bars/dexterity_{segment}.png") in content
    assert static("img/stat_bars/strength_1.png") not in content


def test_a_logged_workout_lights_up_the_bar(logged_in_client, user, repkin):
    # 10 sets of 10 curls = 100 points, all strength.
    log_exercise(user, flat("curls", sets=10, reps=10))

    content = logged_in_client.get(reverse(LOCKER)).content.decode()
    assert static("img/stat_bars/strength_1.png") in content
    assert static("img/stat_bars/endurance_1.png") not in content


# Locked evolutions vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_strength_unlocks_arms_and_endurance_unlocks_legs(repkin):
    give_points(repkin, strength=0, dexterity=300, endurance=150)
    assert unlocked_levels(repkin) == {"arms": 0, "legs": 1}


def test_saving_a_locked_arm_level_is_refused(logged_in_client, repkin):
    give_points(repkin, strength=50)

    response = logged_in_client.post(reverse(SAVE_SPRITE), {"arms_level": "1", "legs_level": "0"})

    assert response.status_code == 403
    assert response.json() == {"error": "That evolution is still locked."}
    repkin.refresh_from_db()
    assert repkin.arms_level == 0


def test_saving_an_unlocked_arm_level_works(logged_in_client, repkin):
    give_points(repkin, strength=100)

    response = logged_in_client.post(reverse(SAVE_SPRITE), {"arms_level": "1", "legs_level": "0"})

    assert response.status_code == 200
    repkin.refresh_from_db()
    assert repkin.arms_level == 1


def test_legs_stay_locked_even_with_full_strength(logged_in_client, repkin):
    give_points(repkin, strength=300, endurance=0)

    response = logged_in_client.post(reverse(SAVE_SPRITE), {"arms_level": "3", "legs_level": "1"})

    assert response.status_code == 403
    repkin.refresh_from_db()
    assert (repkin.arms_level, repkin.legs_level) == (0, 0)


@pytest.mark.parametrize("url_name", ["core:home", LOCKER])
def test_saved_level_above_what_is_unlocked_is_shown_lowered(logged_in_client, repkin, url_name):
    give_points(repkin, strength=120)
    repkin.arms_level = 3
    repkin.save()

    response = logged_in_client.get(reverse(url_name))
    assert response.context["repkin_sprite"] == sprite_for("green", 1, 0)


def test_locker_room_tells_the_arrows_what_is_unlocked(logged_in_client, repkin):
    give_points(repkin, strength=200, endurance=0)
    content = logged_in_client.get(reverse(LOCKER)).content.decode()

    assert 'data-max-arm-level="2"' in content
    assert 'data-max-leg-level="0"' in content
    assert "Legs level 1 unlocks at 100 endurance." in content


# Lifetime stats vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

def test_lifetime_stats_are_zero_with_no_workouts(user):
    assert lifetime_stats(user) == {"strength": 0, "dexterity": 0, "endurance": 0}


def test_lifetime_stats_add_up_the_whole_workout_history(user, repkin):
    log_exercise(user, flat("push_ups", sets=3, reps=10))
    log_exercise(user, flat("running", distance_miles=Decimal("1.00")))

    assert lifetime_stats(user) == {"strength": 24, "dexterity": 12, "endurance": 34}


def test_lifetime_stats_only_count_that_users_workouts(user, other_user, repkin):
    log_exercise(user, flat("curls", sets=2, reps=10))
    log_exercise(other_user, flat("walking", distance_miles=Decimal("2.00")))

    assert lifetime_stats(user) == {"strength": 20, "dexterity": 0, "endurance": 0}


def test_lifetime_stats_survive_the_weekly_progress_reset(user, repkin):
    log_exercise(user, flat("curls", sets=2, reps=10))
    repkin.refresh_from_db()
    repkin.add_prog_to_stats()
    repkin.save()

    assert repkin.progress_stats == {"strength": 0, "dexterity": 0, "endurance": 0}
    assert lifetime_stats(user)["strength"] == 20
