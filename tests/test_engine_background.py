"""The screen's background: the course as it scrolled in, which is not always the map.

On a ground built in the test. What is under test is when a change to the map
reaches the screen -- the original's rule, read in its code and watched in the
emulator: a column is read when it scrolls in, a crate taken is written through,
and nothing else is.
"""

from game.engine.background import Background
from game.engine.original import SLOTS, TILE
from game.engine.original import N
from game.engine.rules import State
from game.engine.original import THROTTLE
from game.engine.run import Run
from game.engine.original import COUNTDOWN, LAP_LINE
from tests.test_engine_bike import Ground, _floor, _solid_from

#: A metatile a test writes into the map, with a tile of its own to be seen by.
SIGN = 7
TILES = {1: (1,) * 4, SIGN: (SIGN,) * 4, N: (N,) * 4}
#: Where the sign goes: behind a bike at the lap line, and in the view.
SIGN_ROW, SIGN_COL = 13, LAP_LINE // 16 - 2


class _Signed(Ground):
    """A ground whose sign over the finish is a metatile, as both courses' is."""

    def goal(self):
        super().goal()
        self.put(SIGN_ROW, SIGN_COL, SIGN)


def _ground(cls=Ground):
    ground = _solid_from(_floor(0), 15)
    return cls(cells=ground.cells, tiles=TILES, hits=ground.hits)


def test_a_change_to_the_map_in_view_is_not_on_the_screen():
    """Why this test: the original fills its background a column at a time as the
    view scrolls, and reads the map for a column only then. A column already
    on the screen keeps what it had until the view has gone a whole background
    on -- and the same place, come round to again, is read afresh."""
    ground = _ground()
    screen = Background(ground)
    screen.scroll(0)
    ground.put(14, 2, SIGN)
    assert screen.tile(28, 4) != SIGN
    screen.scroll(SLOTS * TILE)
    screen.scroll(0)
    assert screen.tile(28, 4) == SIGN, "come back round, it was not read again"


def test_the_sign_goes_up_behind_the_player_and_is_seen_next_time_round():
    """Why this test: the lap line is just past the sign over the finish, so the
    sign is written into the map with its cell on the screen. Drawn from the map
    it pops up behind the player on the first lap; the original shows it only
    as the player arrives on the second. Both courses write their sign into the
    map, so this is the engine's to get right and not the course's."""
    run = Run(_ground(_Signed), limit=30000)
    for _ in range(COUNTDOWN):
        run.step(THROTTLE)
    run.bike.x = (LAP_LINE - 4) << 8
    run.camera.x = (LAP_LINE - 100) << 8
    for _ in range(3):
        run.step(THROTTLE)
    assert run.ground.signed and run.ground.metatile(SIGN_ROW, SIGN_COL) == SIGN
    row, col = SIGN_ROW * 2, SIGN_COL * 2
    assert run.background.tile(row, col) != SIGN, "the sign went up in view"
    lap = 256 * 16
    run.background.scroll(SIGN_COL * 16 + lap - 60)
    assert run.background.tile(row, col + lap // TILE) == SIGN, "not there next lap"


def test_a_crate_taken_leaves_the_screen_at_once():
    """Why this test: the one change the original writes through to the screen is
    a crate taken -- it blanks its tiles in video memory as it empties the cell.
    Without it the crate would stay drawn where the bike has just taken it."""
    ground = _ground()
    ground._items = [(N, 14, 4)]
    ground.put(14, 4, N)
    run = Run(ground)
    run.countdown = 0
    run.bike.state = State.RIDING
    run.bike.x = 0x40 << 8
    assert run.background.tile(28, 8) == N
    run.step(THROTTLE)
    assert run.ground.metatile(14, 4) == 0xFF
    assert run.background.tile(28, 8) != N, "the crate is still on the screen"
