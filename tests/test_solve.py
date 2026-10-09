"""The search over the pad (`tools/solve.py`), on grounds built here.

What it answers -- whether a course can be finished under a ruleset, and how
fast -- is only worth anything if the race it searches is the race the game
runs. So what is under test is that: a branch copied by hand steps exactly as
a deep copy does, the crates one branch takes are not taken in another, and the
pad a search returns rides, replayed from the start, to the finish it claimed.
How good the search is at a course is a question about content and is not
asked here.
"""

import copy

from game.engine.rules import CLASSIC, Ruleset
from game.engine.original import LEFT, NITRO, THROTTLE, UP
from game.engine.original import TAKEOVER_LINE
from tests.test_engine_bike import _floor, _solid_from
from tools import solve


def _flat():
    # The original's grid is at y 232: a ground from metatile row 15 is under it.
    return _solid_from(_floor(0), 15)


def test_a_branch_copied_by_hand_steps_as_a_deep_copy_does():
    """Why this test: `clone` copies a race field by field because deepcopy is
    most of the search's time -- and a field it forgets is shared between two
    branches, which then ride each other's race. Stepped side by side, every
    field the bike has must agree."""
    run = solve.start(_flat())
    pad = [THROTTLE] * 30 + [THROTTLE | NITRO] * 3 + [THROTTLE | UP | LEFT] * 20 + [0] * 10
    for held in pad[:20]:
        run.step(held)
    mine, theirs = solve.clone(run), copy.deepcopy(run)
    for held in pad[20:]:
        mine.step(held)
        theirs.step(held)
        for field in type(mine.bike).__slots__:
            if field in ("ground", "rules"):
                continue
            assert getattr(mine.bike, field) == getattr(theirs.bike, field), field
    # ...and the original was not moved by either.
    assert run.iterations == 20 + solve.COUNTDOWN


def test_a_crate_taken_in_one_branch_is_there_in_another():
    ground = solve.Overlay(_flat())
    one, other = ground.clone(), ground.clone()
    one.put(15, 3, 7)
    assert one.metatile(15, 3) == 7 and one.metatile(15, 3 + 256) == 7
    assert other.metatile(15, 3) == ground.metatile(15, 3) == 1


def test_a_search_on_level_ground_finishes_and_its_pad_rides_there():
    result = solve.solve(_flat(), width=2, block=8)
    assert result.finished
    frames = [frame for _, frame in solve.replay(_flat(), result.pad)]
    assert frames[-1].x >= TAKEOVER_LINE
    assert len(result.pad) >= result.iterations


def test_a_faster_ruleset_finishes_level_ground_sooner():
    """The point of the tool: the same ground, two rulesets, two times."""
    classic = solve.solve(_flat(), CLASSIC, width=2)
    faster = solve.solve(_flat(), Ruleset(cap=111, index_step=4), width=2)
    assert classic.finished and faster.finished
    assert faster.elapsed < classic.elapsed
