from decimal import Decimal

import pytest

from core import units
from core.units import IMPERIAL, SI


def test_pounds_become_kilograms():
    assert units.weight_to_kg("100", IMPERIAL) == Decimal("45.359")
    assert units.weight_to_kg("45", IMPERIAL) == Decimal("20.412")


def test_kilograms_stay_kilograms():
    assert units.weight_to_kg("60", SI) == Decimal("60.000")
    assert units.weight_to_kg(Decimal("2.5"), SI) == Decimal("2.500")


def test_kilograms_are_shown_in_the_users_unit():
    assert units.kg_to_weight("20.412", IMPERIAL) == Decimal("45.0")
    assert units.kg_to_weight("20.412", SI) == Decimal("20.4")


def test_kilometres_become_miles_and_back():
    assert units.distance_to_miles("10", SI) == Decimal("6.214")
    assert units.distance_to_miles("5", IMPERIAL) == Decimal("5.000")
    assert units.miles_to_distance("3.107", SI) == Decimal("5.00")
    assert units.miles_to_distance("3.107", IMPERIAL) == Decimal("3.11")


@pytest.mark.parametrize("pounds", ["2.5", "5", "10", "25", "35", "45", "95", "135", "185", "225", "315", "405"])
def test_everyday_weights_survive_a_round_trip_in_pounds(pounds):
    stored = units.weight_to_kg(pounds, IMPERIAL)
    assert units.kg_to_weight(stored, IMPERIAL) == Decimal(pounds).quantize(Decimal("0.1"))


@pytest.mark.parametrize("kilos", ["1", "2.5", "5", "10", "20", "60", "100"])
def test_everyday_weights_survive_a_round_trip_in_kilograms(kilos):
    stored = units.weight_to_kg(kilos, SI)
    assert units.kg_to_weight(stored, SI) == Decimal(kilos).quantize(Decimal("0.1"))


@pytest.mark.parametrize("km", ["0.5", "1", "3", "5", "10", "21.1", "42.2", "100"])
def test_everyday_distances_survive_a_round_trip_in_kilometres(km):
    stored = units.distance_to_miles(km, SI)
    assert abs(units.miles_to_distance(stored, SI) - Decimal(km)) <= Decimal("0.01")


def test_rounding_goes_up_at_the_halfway_point():
    assert units.miles_for_exercise_log("1.005") == Decimal("1.01")
    assert units.miles_for_exercise_log("1.004") == Decimal("1.00")


def test_unknown_unit_systems_are_rejected_everywhere():
    for call in (
        lambda: units.check_system("martian"),
        lambda: units.weight_to_kg("1", "martian"),
        lambda: units.kg_to_weight("1", "martian"),
        lambda: units.distance_to_miles("1", "martian"),
        lambda: units.miles_to_distance("1", "martian"),
        lambda: units.unit_labels("martian"),
    ):
        with pytest.raises(ValueError):
            call()


def test_the_labels_for_each_system():
    assert units.unit_labels(IMPERIAL) == {"weight": "lb", "distance": "mi"}
    assert units.unit_labels(SI) == {"weight": "kg", "distance": "km"}


def test_the_browsers_saved_choice_maps_to_a_system():
    """main_menu.js saves "lbs" or "kgs" under the key repkinz.unit."""
    assert units.system_from_browser_choice("lbs") == IMPERIAL
    assert units.system_from_browser_choice("kgs") == SI


@pytest.mark.parametrize("odd", [None, "", "stone", "KGS"])
def test_anything_unexpected_from_the_browser_means_imperial_like_the_menu_default(odd):
    assert units.system_from_browser_choice(odd) == IMPERIAL
    assert units.system_from_browser_choice(odd, default=SI) == SI
