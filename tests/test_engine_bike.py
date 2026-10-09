"""One tick of the bike on the ground: the window, the probes, following the ground,
taking off, and the states that stand still.

The ground here is built in the test, a few metatiles on an otherwise empty map,
because what is under test is the rule and not any course: which cells are read,
what a solid one under the wheels does to the direction, where the bike is put
back on the grid. Whether the rules reproduce the original tick for tick is
checked against recorded runs of it, where a cartridge exists.
"""

import pytest

from game.engine.bike import Bike
from game.engine.probes import probe, window
from game.engine.original import WINDOW
from game.engine.rules import Auto, State
from game.engine.original import CAP, DIRECTIONS, FAST, LEFT, MINIS_BEHIND, THROTTLE, TRAIL, UP
from game.engine.speed import Speed
from game.engine.terrain import SKY, Hit

EMPTY = 0xFF
ROCK = 0xEF
#: A level cell's floor probes, for every direction: the three the original uses
#: on the level. Tests that need another set say so.
LEVEL_PROBES = (27, 26, 21)


class Ground:
    """A map of metatiles, empty but for the cells a test puts down."""

    def __init__(self, cells=None, tiles=None, hits=None, probes=None, items=()):
        self.cells = cells or {}
        self._items = list(items)
        self._tiles = tiles or {}
        self.hits = hits or {}
        self._probes = probes or {}
        #: Whether the engine has asked for the sign over the finish.
        self.signed = False

    def metatile(self, row, col):
        return self.cells.get((row, col % 256), EMPTY)

    def tiles(self, metatile):
        return self._tiles.get(metatile, (0, 0, 0, 0))

    def collision(self, tile):
        return self.hits.get(tile, SKY)

    def probes(self, direction):
        return self._probes.get(direction, LEVEL_PROBES)

    def is_rock(self, tile):
        return tile == ROCK

    def items(self):
        return self._items

    def teleports(self):
        """One stretch the length of the course, on the grid's row."""
        return [(0, 0xFFFF, 232)]

    def put(self, row, col, metatile):
        self.cells[(row, col % 256)] = metatile

    def goal(self):
        """No sign of its own -- a course of this game's own draws its finish
        however it draws it -- but it writes down that it was asked, because
        whether the engine asks at all, and for which bike, is the rule."""
        self.signed = True

    def throw(self, step):
        """A thrown rider's path: up and back, then down and back."""
        return ((-128 if step >= 5 else 128 if step <= 3 else 0), -1)


def _floor(direction=0, soft=False, no_wheelie=False, tile=1):
    """A ground whose every tile of metatile 1 is solid, travelled at `direction`."""
    return Ground(tiles={1: (tile,) * 4},
                  hits={tile: Hit(True, soft, no_wheelie, direction)})


def _solid_from(ground, row):
    """Metatile 1 on every cell from `row` down: open above it, ground below."""
    ground.cells = {(r, c): 1 for r in range(row, 16) for c in range(256)}
    return ground


def _px(x, y):
    """A position in fixed point, from whole pixels."""
    return x << 8, y << 8


def _riding(ground, x=0x40, y=0x48, direction=0, index=CAP, **kw):
    fx, fy = _px(x, y)
    return Bike(ground, x=fx, y=fy, direction=direction, attitude=direction,
                state=State.RIDING, speed=Speed(index=index), **kw)


# -- the window and the probes -------------------------------------------------


def test_the_trail_keeps_the_last_iterations_and_nothing_while_standing_still():
    """Why this test: the mini-maniacs are the player a few iterations ago, so
    the trail is the whole of them -- and the one rule that is not obvious is
    that **a bike going nowhere puts nothing on it**. Without that the three of
    them pile up on a stopped bike, which the original does not do. It is also
    the one thing here that cannot be seen in a screenshot of a moving bike.
    """
    bike = Bike(Ground())
    bike.x, bike.y = _px(100, 80)
    assert bike.behind(0) is None, "nothing has happened yet"
    bike.vx = 0
    bike.remember()
    assert bike.trail == [], "standing still is not a place it has been"
    bike.vx = 1
    for step in range(TRAIL + 4):
        bike.x = (100 + step) << 8
        bike.attitude = step % DIRECTIONS
        bike.remember()
    assert len(bike.trail) == TRAIL, "the oldest fall off the end"
    assert bike.behind(0) == (100 + TRAIL + 3, 80, (TRAIL + 3) % DIRECTIONS)
    assert bike.behind(MINIS_BEHIND[0])[0] == 100 + TRAIL + 3 - MINIS_BEHIND[0]
    assert bike.behind(TRAIL) is None, "further back than it remembers"


def test_the_window_is_three_metatiles_from_the_row_above_and_the_own_column():
    """Rows from one above the bike's, columns from its own: a bike at metatile
    (row 4, col 4) sees rows 3-5, columns 4-6."""
    ground = Ground(cells={(3, 4): 1, (5, 6): 2},
                    tiles={1: (10, 11, 12, 13), 2: (20, 21, 22, 23), EMPTY: (0, 0, 0, 0)})
    cells = window(ground, 4 * 16, 4 * 16)
    assert cells[0:2] == [10, 11] and cells[WINDOW:WINDOW + 2] == [12, 13]
    assert cells[4 * WINDOW + 4:4 * WINDOW + 6] == [20, 21]
    assert cells[5 * WINDOW + 4:5 * WINDOW + 6] == [22, 23]


def test_a_probe_moves_down_in_the_lower_half_and_left_in_the_left_half():
    marks = {27: 1, 26: 2, 33: 3, 32: 4}
    ground = Ground(hits={n: Hit(True, False, False, n) for n in marks.values()})
    cells = [0] * 36
    for index, tile in marks.items():
        cells[index] = tile
    right_upper = probe(ground, cells, 0x00, 0x08, 0, 0, State.RIDING)
    left_upper = probe(ground, cells, 0x00, 0x00, 0, 0, State.RIDING)
    right_lower = probe(ground, cells, 0x08, 0x08, 0, 0, State.RIDING)
    assert right_upper.first.direction == 1       # cell 27
    assert left_upper.first.direction == 2        # 27 - 1
    assert right_lower.first.direction == 3       # 27 + 6


def test_the_cell_beside_the_third_probe_is_read_too():
    """The original steps on from the third probe's cell and reads the next one."""
    cells = [0] * 36
    cells[22] = 7
    ground = Ground(hits={7: Hit(True, False, False, 5)})
    assert probe(ground, cells, 0, 0x08, 0, 0, State.RIDING).beside_third.solid


def test_riding_up_at_45_the_first_probe_is_cell_22():
    cells = [0] * 36
    cells[22] = 7
    ground = Ground(hits={7: Hit(True, False, False, 4)}, probes={4: (0, 1, 2)})
    assert probe(ground, cells, 0, 0x08, 4, 4, State.RIDING).first.solid
    assert not probe(ground, cells, 0, 0x08, 4, 4, State.AIR).first.solid


# -- following the ground ------------------------------------------------------


@pytest.mark.parametrize("direction", [0, 4, 8, 16, 28])
def test_the_tile_under_the_wheels_sets_the_direction_and_the_attitude(direction):
    ground = _floor(direction)
    ground.cells = {(r, c): 1 for r in range(16) for c in range(256)}
    bike = _riding(ground, direction=0)
    bike.step(THROTTLE, 0)
    assert bike.direction == bike.attitude == direction
    assert bike.state is State.RIDING


def _following(direction, x, y):
    ground = _floor(direction)
    ground.cells = {(r, c): 1 for r in range(16) for c in range(256)}
    bike = _riding(ground, x=x, y=y, direction=direction)
    bike.x += 0x37
    bike.y += 0x21
    return bike


def test_on_the_level_the_bike_is_put_on_the_grid_and_does_not_rise_or_sink():
    bike = _following(0, 0x40, 0x4D)
    bike.step(THROTTLE, 0)
    assert bike.px[1] == 0x48 and bike.y & 0xFF == 0x21
    assert bike.vy == 0 and bike.vx > 0


def test_up_a_right_hand_wall_x_is_put_on_the_grid_and_does_not_drift():
    bike = _following(8, 0x4D, 0x40)
    bike.step(THROTTLE, 0)
    assert bike.px[0] == 0x48 and bike.vx == 0 and bike.vy < 0


def test_on_a_ceiling_y_goes_up_to_the_next_line_of_the_grid():
    bike = _following(16, 0x40, 0x4D)
    bike.step(THROTTLE, 0)
    assert bike.px[1] == 0x50 and bike.vy == 0 and bike.vx < 0


def test_a_slope_is_not_put_on_the_grid():
    bike = _following(4, 0x40, 0x4D)
    y, x = bike.y, bike.x
    bike.step(THROTTLE, 0)
    assert (bike.y, bike.x) == (y + bike.vy, x + bike.vx)


def test_climbing_a_wall_a_level_tile_is_not_taken_up():
    """Going up a wall, a tile that would lay the bike back on the level is not
    followed -- the bike leaves the wall instead of turning a right angle."""
    ground = _floor(0)
    ground.cells = {(r, c): 1 for r in range(16) for c in range(256)}
    bike = _riding(ground, direction=12)
    bike.step(THROTTLE, 0)
    assert bike.direction == 12


# -- taking off ---------------------------------------------------------------


def test_with_nothing_under_the_wheels_the_bike_takes_off():
    bike = _riding(Ground())
    bike.step(THROTTLE, 0)
    assert bike.state is State.AIR


def test_on_the_level_the_second_probe_is_enough_to_stay_down():
    """Cell 26, the second on the level: touching it, there is no take-off."""
    # At (0x48, 0x40) the second probe, cell 26, is the top-left tile of the
    # metatile one row down and one column on.
    ground = Ground(tiles={1: (9, 0, 0, 0)}, hits={9: Hit(True, False, False, 0)},
                    cells={(5, 5): 1})
    bike = _riding(ground, x=0x48, y=0x40)
    bike.step(THROTTLE, 0)
    assert bike.state is State.RIDING


@pytest.mark.parametrize("index, held, auto, jump", [
    (CAP, 0, Auto.NONE, 0),
    (CAP, UP, Auto.NONE, 1),
    (FAST, 0, Auto.NONE, 2),
    (FAST, UP, Auto.NONE, 3),
    (CAP, UP, Auto.RIDING, 4),
])
def test_a_take_off_has_a_class_from_the_speed_and_up(index, held, auto, jump):
    """Fast (an index a nitro or an S reaches) and Up are the two things a jump
    is: they pick its class, and the class is how long it hangs."""
    speed = Speed(index=index, cap=index, nitro_timer=5)
    bike = Bike(Ground(), x=0x4000, y=0x4000, state=State.RIDING, speed=speed, auto=auto)
    bike.step(THROTTLE | held, 0)
    assert bike.state is State.AIR
    assert bike.jump_class == jump and bike.hang == 2 * jump
    assert bike.speed.nitro_timer == 0


# -- rocks, walls and the standing states -------------------------------------


def _on_a_rock(player):
    ground = _floor(0)
    ground.cells = {(r, c): 1 for r in range(16) for c in range(256)}
    ground._tiles[1] = (ROCK,) * 4
    ground.hits[ROCK] = Hit(True, False, False, 0)
    return _riding(ground, player=player)


def test_the_rider_crashes_on_a_rock_and_the_computer_hops_it():
    rider, computer = _on_a_rock(True), _on_a_rock(False)
    rider.step(THROTTLE, 0)
    computer.step(THROTTLE, 0)
    assert rider.state is State.CRASHING
    assert computer.state is State.RIDING and computer.direction == 4


CRASHES = (State.FALLING, State.CRASHING, State.DOWN)


def test_stopped_on_a_wall_or_a_ceiling_is_a_crash():
    for direction, crashed in ((8, False), (9, True), (16, True), (23, True), (24, False)):
        bike = Bike(Ground(), direction=direction, state=State.STOPPED)
        bike.step(0, 0)
        assert (bike.state in CRASHES) is crashed, direction


def test_at_index_zero_the_bike_stops_and_the_throttle_starts_it():
    ground = _floor(0)
    ground.cells = {(r, c): 1 for r in range(16) for c in range(256)}
    bike = _riding(ground, index=2)
    bike.step(0, 0)
    assert bike.state is State.STOPPED
    bike.step(THROTTLE, 0)
    assert bike.state is State.RIDING


def test_in_the_countdown_the_bike_shivers_a_pixel_and_goes_nowhere():
    bike = Bike(Ground(), x=0x2000, y=0xE800, state=State.COUNTDOWN)
    ys = []
    for _ in range(4):
        bike.step(THROTTLE, 0)
        ys.append(bike.px[1])
    assert ys == [0xE9, 0xE8, 0xE9, 0xE8]
    assert bike.x == 0x2000


def test_on_the_level_left_starts_a_wheelie_unless_the_tile_forbids_it():
    """In the upper half of its metatile, as a bike riding the level is: the
    third probe then reads the air, and the wheelie's ground check lets it be."""
    for no_wheelie, state in ((False, State.WHEELIE), (True, State.RIDING)):
        bike = _riding(_solid_from(_floor(0, no_wheelie=no_wheelie), 5), y=0x40)
        bike.step(THROTTLE, 0)
        bike.step(THROTTLE | LEFT, 0)
        assert bike.state is state, no_wheelie


def test_a_wheelie_that_starts_with_the_third_probe_on_solid_ends_on_the_spot():
    """Its ground check runs on the tick it starts: the lower half of a metatile
    puts the third probe in the ground, and the bike is riding again at once."""
    bike = _riding(_solid_from(_floor(0), 5), y=0x48)
    bike.step(THROTTLE, 0)
    bike.step(THROTTLE | LEFT, 0)
    assert bike.state is State.RIDING


def test_sand_is_read_only_on_the_level():
    for direction, term in ((0, -56), (4, -4)):
        ground = _floor(direction, soft=True)
        ground.cells = {(r, c): 1 for r in range(16) for c in range(256)}
        bike = _riding(ground, direction=direction)
        bike.step(THROTTLE, 0)
        bike.step(THROTTLE, 0)
        assert bike.speed.slope_term == term, direction


# -- a wheelie ----------------------------------------------------------------------


def _wheeling(attitude=0, direction=0, **kw):
    """A wheelie on ground travelled at `direction`. Nose up, the attitude probes
    look up and ahead, as the original's do -- into the air, here."""
    ground = _solid_from(_floor(direction), 5)
    ground._probes = {d: (3, 2, 21) for d in range(1, 9)}
    fx, fy = _px(0x40, 0x40)
    return Bike(ground, x=fx, y=fy, direction=direction, attitude=attitude,
                state=State.WHEELIE, speed=Speed(index=CAP), **kw)


def test_held_the_nose_comes_up_a_step_every_other_tick():
    bike = _wheeling()
    attitudes = []
    for tick in range(6):
        bike.step(THROTTLE | LEFT, 0, tick)
        attitudes.append(bike.attitude)
    assert attitudes == [1, 1, 2, 2, 3, 3]
    assert bike.state is State.WHEELIE


def test_the_nose_only_comes_up_on_the_level():
    bike = _wheeling(direction=4, attitude=4)
    bike.step(THROTTLE | LEFT, 0, 0)
    assert bike.attitude == 4


def test_at_ninety_degrees_the_wheelie_is_over():
    """Nose at 8 is a tumble -- and on level ground, down on the same tick."""
    bike = _wheeling(attitude=7)
    bike.step(THROTTLE | LEFT, 0, 0)
    assert bike.state in CRASHES


def test_let_go_the_nose_comes_down_a_step_a_tick_and_it_rides_again():
    bike = _wheeling(attitude=3)
    attitudes = []
    for tick in range(3):
        bike.step(THROTTLE, 0, tick)
        attitudes.append((bike.attitude, bike.state))
    assert attitudes == [(2, State.WHEELIE), (1, State.WHEELIE), (0, State.RIDING)]
