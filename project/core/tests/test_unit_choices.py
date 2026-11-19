"""The main menu, the workout page and the server must agree on the saved unit values.

main_menu.js saves the person's choice in the browser under "repkinz.unit". The workout
page (workout_builder.js) reads it, and core/units.py documents what it means. If someone
renames the values in one place, the others quietly misread them: for example, metric users
would get pounds and miles. These tests fail instead.
"""

import re
from pathlib import Path

from core import units

STATIC = Path(__file__).resolve().parents[2] / "static" / "js"


def read(name):
    return (STATIC / name).read_text(encoding="utf-8")


def builder_metric_values():
    match = re.search(r"const METRIC_CHOICES = \[([^\]]*)\]", read("workout_builder.js"))
    assert match, "workout_builder.js should define METRIC_CHOICES"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_the_workout_page_and_the_server_agree_which_saved_values_mean_metric():
    server = {value for value, system in units.BROWSER_CHOICES.items() if system == units.SI}
    assert builder_metric_values() == server


def test_the_workout_page_reads_the_key_the_main_menu_writes():
    assert '"repkinz.unit"' in read("main_menu.js")
    assert '"repkinz.unit"' in read("workout_builder.js")


def test_every_value_the_main_menu_saves_is_understood_by_the_workout_page_and_server():
    saved = set(re.findall(r'setUnit\("(\w+)"\)', read("main_menu.js")))
    assert saved, 'main_menu.js no longer calls setUnit("...") with plain strings: update this test'
    for value in saved:
        assert value in units.BROWSER_CHOICES, f'the menu saves "{value}", which units.py does not know'
    # and the two systems are both reachable from the menu
    assert {units.BROWSER_CHOICES[value] for value in saved} == {units.IMPERIAL, units.SI}


def test_the_workout_page_treats_the_menus_metric_value_as_metric():
    metric_saved = {
        value for value in re.findall(r'setUnit\("(\w+)"\)', read("main_menu.js"))
        if units.BROWSER_CHOICES.get(value) == units.SI
    }
    assert metric_saved and metric_saved <= builder_metric_values()


def test_values_saved_by_older_menus_still_work():
    assert units.system_from_browser_choice("lbs") == units.IMPERIAL
    assert units.system_from_browser_choice("kgs") == units.SI
    assert {"kgs"} <= builder_metric_values()
