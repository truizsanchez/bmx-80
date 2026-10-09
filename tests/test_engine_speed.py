"""The speed model, rule by rule: the index, the curve, the slope term, the magnitude.

Each test states one thing the original does. The numbers are the original's
behaviour and not a tuning, so a test that fails here means the engine stopped
being the original -- not that a number wants moving.

What is checked against the original itself -- its bytes and its recorded ticks --
is not in this repository; these are the rules that check has to agree with.
"""

import math

import pytest

from game.engine.rules import Auto, State
from game.engine.original import (
    CAP,
    CAP_S,
    CURVE_TOP,
    MAGNITUDE_MAX,
    NITRO_INDEX,
    NITRO_TICKS,
    SOFT_TERM,
)
from game.engine.speed import Speed, curve, magnitude, slope, update_index

RIDING = State.RIDING


def _ride(speed, ticks, throttle=False, nitro=False, state=RIDING):
    """`ticks` of the index rule, the same buttons every tick."""
    seen = []
    for _ in range(ticks):
        update_index(speed, state, throttle, nitro)
        seen.append(speed.index)
    return seen


# -- the curve ------------------------------------------------------------------


def test_the_curve_never_goes_down():
    """More index is never less speed: the throttle can only ever help."""
    values = [curve(i) for i in range(MAGNITUDE_MAX + 1)]
    assert values == sorted(values)


def test_the_curve_at_the_two_caps():
    """Top speed without an S is 98 and with one 112: the two numbers every
    measurement of the original's speed starts from."""
    assert curve(CAP) == 98
    assert curve(CAP_S) == 112


def test_the_curve_is_steep_at_the_bottom_and_flat_at_the_top():
    """Why a coast from low speed stops at once and one from the top rolls on:
    the first eight steps of the index are worth 48, the last eight before the
    cap are worth 4."""
    assert curve(7) - curve(0) == 48
    assert curve(CAP) - curve(CAP - 8) == 4


def test_from_the_top_of_the_curve_the_index_is_its_own_value():
    """Only a nitro gets there, and there the index is the magnitude."""
    for index in range(CURVE_TOP, MAGNITUDE_MAX + 1):
        assert curve(index) == index


# -- the throttle and the coast -------------------------------------------------


def test_the_throttle_climbs_two_a_tick_to_the_cap_and_stops():
    speed = Speed()
    seen = _ride(speed, 60, throttle=True)
    assert seen[:3] == [2, 4, 6]
    assert max(seen) == CAP and seen[-1] == CAP
    assert all(b - a in (0, 1, 2) for a, b in zip(seen, seen[1:]))


def test_an_s_moves_the_cap_and_nothing_else():
    speed = Speed(cap=CAP_S)
    assert _ride(speed, 80, throttle=True)[-1] == CAP_S


def test_off_the_throttle_the_index_falls_two_a_tick_and_stops_at_zero():
    """The bike never rolls back: nothing takes the index below zero."""
    speed = Speed(index=CAP)
    seen = _ride(speed, 60)
    assert seen[:2] == [CAP - 2, CAP - 4]
    assert seen[-1] == 0 and min(seen) == 0


@pytest.mark.parametrize("start", [1, 2, 30, CAP, CAP_S])
@pytest.mark.parametrize("direction", [0, 4, 7, 8, 16, 24, 28])
def test_a_coast_lasts_half_the_index_on_any_slope(start, direction):
    """The slope changes the magnitude and never the index, so how long a coast
    lasts is a fact about the index alone -- `ceil(index / 2)` ticks, uphill,
    downhill or up a wall."""
    speed = Speed(index=start)
    ticks = 0
    while speed.index:
        update_index(speed, RIDING, throttle=False, nitro_pressed=False)
        slope(speed, direction, soft=False, no_slope=False)
        magnitude(speed)
        ticks += 1
    assert ticks == math.ceil(start / 2)


# -- the nitro --------------------------------------------------------------------


def test_a_nitro_holds_the_top_then_comes_down_to_the_cap():
    """144 for sixteen ticks, then two down a tick -- on the throttle -- to the cap.

    From an even index the steps down miss an odd cap by one, and the next climb
    clamps it back: 80, 78, 79. That is the original's arithmetic, not a wobble.
    """
    speed = Speed(index=CAP)
    update_index(speed, RIDING, throttle=True, nitro_pressed=True)
    assert speed.index == NITRO_INDEX and speed.nitros == 3
    held = _ride(speed, NITRO_TICKS, throttle=True)
    assert set(held) == {NITRO_INDEX}
    falling = _ride(speed, 40, throttle=True)
    assert falling[:2] == [NITRO_INDEX - 2, NITRO_INDEX - 4]
    at = falling.index(80)
    assert falling[at:at + 3] == [80, 78, CAP]
    assert falling[-1] == CAP


def test_a_nitro_fires_on_a_press_and_only_with_one_in_hand():
    speed = Speed(index=40, nitros=1)
    update_index(speed, RIDING, throttle=True, nitro_pressed=True)
    assert speed.index == NITRO_INDEX and speed.nitros == 0
    for _ in range(NITRO_TICKS):
        update_index(speed, RIDING, throttle=True, nitro_pressed=False)
    update_index(speed, RIDING, throttle=True, nitro_pressed=True)
    assert speed.nitros == 0 and speed.index == NITRO_INDEX, \
        "a press with nothing in hand moved the index"


def test_a_press_while_a_nitro_runs_is_not_read():
    """The timer comes before the rule, so a second press spends nothing."""
    speed = Speed(index=CAP, nitros=4)
    update_index(speed, RIDING, throttle=True, nitro_pressed=True)
    update_index(speed, RIDING, throttle=True, nitro_pressed=True)
    assert speed.nitros == 3


def test_an_empty_press_spends_the_tick_on_nothing():
    """With no nitro in hand a press still wins the tick: the index neither
    climbs on the throttle nor falls off it."""
    for throttle in (True, False):
        speed = Speed(index=40, nitros=0)
        update_index(speed, RIDING, throttle=throttle, nitro_pressed=True)
        assert speed.index == 40


# -- what the state decides -------------------------------------------------------


@pytest.mark.parametrize("state, index", [
    (State.FINISHED, 32),
    (State.CRASHING, 8),
    (State.DOWN, 0),
])
def test_some_states_set_the_index_outright(state, index):
    speed = Speed(index=60)
    update_index(speed, state, throttle=True, nitro_pressed=True)
    assert speed.index == index and speed.nitros == 4


def test_in_the_air_the_index_is_the_flights_business():
    speed = Speed(index=60)
    update_index(speed, State.AIR, throttle=True, nitro_pressed=False)
    assert speed.index == 60


def test_past_the_line_the_throttle_is_held_for_you():
    """Even in the air, and with the rider's own thumbs off everything."""
    for state in (RIDING, State.AIR):
        speed = Speed(index=10)
        update_index(speed, state, throttle=False, nitro_pressed=False, auto=Auto.THROTTLE)
        assert speed.index == 12


def test_further_on_the_index_is_raised_to_the_cap_and_never_lowered_to_it():
    raised = Speed(index=10)
    update_index(raised, RIDING, False, False, auto=Auto.RIDING)
    assert raised.index == CAP
    above = Speed(index=120)
    update_index(above, RIDING, False, False, auto=Auto.RIDING)
    assert above.index == 120
    for state, auto in ((State.AIR, Auto.AIR), (RIDING, Auto.CELEBRATING)):
        left = Speed(index=10)
        update_index(left, state, False, False, auto=auto)
        assert left.index == 10


# -- the slope term ---------------------------------------------------------------


def _climb(speed, direction, ticks, soft=False, no_slope=False):
    terms = []
    for _ in range(ticks):
        slope(speed, direction, soft, no_slope)
        terms.append(speed.slope_term)
        magnitude(speed)
    return terms


def test_uphill_the_term_walks_down_and_rests_one_step_past_minus_32():
    """Two a tick. The original compares with -32 *before* it subtracts, so the
    walk takes one more step and rests at -34."""
    terms = _climb(Speed(), 4, 30)
    assert terms[:3] == [-2, -4, -6]
    assert terms[-1] == -34 and min(terms) == -34


def test_downhill_the_term_walks_up_to_32():
    terms = _climb(Speed(), 28, 30)
    assert terms[:2] == [2, 4]
    assert terms[-1] == 32 and max(terms) == 32


def test_steepness_does_not_enter():
    """The first step up and the last cost the same: only the side of the
    circle the direction is on counts."""
    assert _climb(Speed(), 1, 20) == _climb(Speed(), 7, 20)
    assert _climb(Speed(), 24, 20) == _climb(Speed(), 31, 20)


def test_level_ground_empties_the_accumulator():
    speed = Speed()
    _climb(speed, 4, 10)
    slope(speed, 0, soft=False, no_slope=False)
    assert speed.slope_acc == 0
    assert _climb(speed, 4, 1) == [-2]


@pytest.mark.parametrize("direction", range(8, 24))
def test_there_is_no_gravity_on_a_wall(direction):
    """Walls and ceilings leave the term alone -- which is why a bike off the
    throttle in a loop stays where it is instead of sliding down."""
    speed = Speed(slope_acc=-20)
    assert _climb(speed, direction, 5) == [0] * 5
    assert speed.slope_acc == -20


def test_the_r_turns_the_slope_off():
    """The R is for the hills: nothing lost climbing, and nothing gained descending."""
    assert _climb(Speed(), 4, 5, no_slope=True) == [0] * 5
    assert _climb(Speed(), 28, 5, no_slope=True) == [0] * 5


def test_sand_is_minus_56():
    """The original only draws sand on the level, and there it costs 56."""
    assert _climb(Speed(), 0, 3, soft=True) == [SOFT_TERM] * 3


def test_soft_ground_is_set_before_the_slope_step():
    """The order the original runs them in. No map of the original puts sand on a
    slope, so this is the rule's order and not a case a rider meets -- pinned
    because it is what decides the R and the sand below."""
    assert _climb(Speed(), 4, 2, soft=True) == [-2, -4]
    assert _climb(Speed(), 12, 2, soft=True) == [SOFT_TERM] * 2


def test_the_r_does_not_take_the_sand_away():
    """The R skips the slope step and nothing else: the sand is set before it, so
    sand costs the same with the R. Checked on the original by forcing the R on
    over a ride through sand -- the same magnitude on every tick."""
    assert _climb(Speed(), 0, 3, soft=True, no_slope=True) == [SOFT_TERM] * 3


# -- the magnitude ----------------------------------------------------------------


def test_the_magnitude_is_the_curve_plus_the_term_held_to_its_range():
    assert magnitude(Speed(index=CAP, slope_term=-20)) == 78
    assert magnitude(Speed(index=2, slope_term=-34)) == 0
    assert magnitude(Speed(index=NITRO_INDEX, slope_term=32)) == MAGNITUDE_MAX


def test_the_term_is_spent_by_the_magnitude_that_uses_it():
    """Set while riding, used by the next magnitude, then gone: a tick that sets
    nothing adds nothing."""
    speed = Speed(index=CAP, slope_term=-20)
    assert magnitude(speed) == 78
    assert speed.slope_term == 0
    assert magnitude(speed) == 98


def test_s_on_sand_is_half_of_top_speed():
    """The third measurement: with an S, on level sand, the magnitude is 56."""
    speed = Speed(index=CAP_S, cap=CAP_S)
    slope(speed, 0, soft=True, no_slope=False)
    assert magnitude(speed) == 56
