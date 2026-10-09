"""A ruleset: the few numbers a mode other than the original's may move.

The engine's numbers are the original's and fixed (`game/engine/rules.py`); a
`Ruleset` gathers the ones another mode is allowed to change, and every bike
carries one. These tests exist so that a mode is a *value* handed to a race and
not an edit to the engine: each number here is read from the bike's ruleset and
not from the constant, and `CLASSIC` is the constants exactly -- so a race that
does not ask for anything else rides as the original does.
"""

import pytest

from game.engine import flight, items
from game.engine import rival as rivals
from game.engine.rules import CLASSIC, Ruleset, State
from game.engine.original import (
    CAP,
    CAP_S,
    INDEX_STEP,
    LAND_AHEAD,
    LAND_BEHIND,
    NITROS_START,
    THROTTLE,
)
from game.engine.speed import Speed, update_index
from tests.test_engine_run import _riding_at, _run

FAST = Ruleset(cap=95, cap_s=127, index_step=4, nitros=6, land_behind=2, land_ahead=3)


def test_classic_is_the_originals_numbers():
    """The default ruleset is the constants, one for one: if this drifts, a race
    that asked for nothing is no longer the original's."""
    assert (CLASSIC.cap, CLASSIC.cap_s, CLASSIC.index_step, CLASSIC.nitros,
            CLASSIC.land_behind, CLASSIC.land_ahead) == (
        CAP, CAP_S, INDEX_STEP, NITROS_START, LAND_BEHIND, LAND_AHEAD)
    assert Speed.of(CLASSIC) == Speed()


@pytest.mark.parametrize("bad", [
    dict(cap=0), dict(cap=120, cap_s=100), dict(cap_s=200), dict(index_step=0),
    dict(nitros=-1), dict(nitros=256), dict(land_behind=8), dict(land_ahead=-1),
])
def test_a_ruleset_the_engine_cannot_ride_is_refused(bad):
    """Refused where it is made, not found out as a strange race: a cap above
    the largest magnitude, an index that never moves, a landing window of a
    quarter turn or more."""
    with pytest.raises(ValueError):
        Ruleset(**bad)


def test_a_race_starts_both_bikes_from_its_ruleset():
    run = _run(rules=FAST, rival=True)
    assert run.bike.rules is FAST and run.rival.rules is FAST
    assert run.bike.speed.cap == 95 and run.bike.speed.nitros == 6


def test_the_index_walks_by_the_rulesets_step():
    speed = Speed.of(FAST)
    seen = []
    for _ in range(30):
        update_index(speed, State.RIDING, throttle=True, nitro_pressed=False)
        seen.append(speed.index)
    assert seen[:3] == [4, 8, 12] and seen[-1] == 95
    update_index(speed, State.RIDING, throttle=False, nitro_pressed=False)
    assert speed.index == 91


def test_an_s_raises_the_cap_to_the_rulesets():
    run = _riding_at(1000, rules=FAST)
    items.give(run.bike, items.S)
    assert run.bike.speed.cap == 127


def test_the_rival_far_ahead_rides_at_the_rulesets_cap():
    run = _run(rules=FAST, rival=True)
    run.rival.x = run.bike.x + (0x100 << 8)
    rivals.drive(run.rival, run.bike, run.camera, 0)
    assert run.rival.speed.cap == 95


def test_the_landing_window_is_the_rulesets():
    """Three steps ahead lands under both; four ahead only under the original's
    wider window. That a bike asks its own ruleset is `test_engine_flight`'s."""
    assert flight.lands(3, 0, FAST.land_behind, FAST.land_ahead)
    assert not flight.lands(4, 0, FAST.land_behind, FAST.land_ahead)
    assert flight.lands(4, 0)


def test_a_crash_puts_back_the_rulesets_cap():
    """Down, the rider loses the S: the cap goes back to the ruleset's own, not
    the original's."""
    run = _riding_at(1000, rules=FAST)
    bike = run.bike
    bike.speed.cap = FAST.cap_s
    bike.state, bike.down_timer = State.DOWN, 57
    run.step(THROTTLE)
    assert bike.speed.cap == 95
