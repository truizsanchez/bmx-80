"""The air: a jump's fall, the rider turning the bike, the landing, and a crash.

There is no gravity in the original, and these say so from the other side: a
flight is a straight line whose direction turns a step at a time, at a pace the
jump's class sets, and whether it ends riding or crashed is the attitude against
the surface. Whether the rules reproduce the original tick for tick is checked
against recorded runs of it, where a cartridge exists.
"""

import pytest

from game.engine import bike as bike_module
from game.engine import flight
from game.engine.bike import Bike
from game.engine.probes import Probes
from game.engine.rules import Ruleset, State
from game.engine.original import LEFT, NITRO, NITRO_INDEX, RIGHT, THROTTLE
from game.engine.speed import Speed
from game.engine.terrain import SKY, Hit

from tests.test_engine_bike import Ground


# -- the rules --------------------------------------------------------------------


def test_the_slow_jump_falls_fastest_and_turns_every_tick():
    assert flight.jump(0) == flight.Jump(drop=8, period=0, step=2)
    assert all(flight.jump(c) == flight.Jump(drop=4, period=1, step=1) for c in (1, 2, 3))
    assert flight.jump(4) == flight.Jump(drop=2, period=3, step=1)


def test_a_falling_index_is_lifted_off_the_floor_first():
    assert flight.fall(60, 0) == 52
    assert flight.fall(20, 0) == 26
    assert flight.fall(20, 1) == 30


def test_heading_right_the_flight_turns_down_and_stops_short_of_straight_down():
    """From 4 in steps of two: 2, 0, 30, 28, 26, and there it stays."""
    seen, direction = [], 4
    for _ in range(8):
        direction = flight.turn(direction, 2)
        seen.append(direction)
    assert seen == [2, 0, 30, 28, 26, 26, 26, 26]
    assert flight.turn(27, 1) == 26 and flight.turn(26, 1) == 26 and flight.turn(25, 1) == 25


def test_heading_left_the_flight_turns_down_to_straight_down():
    assert [flight.turn(d, 2) for d in (9, 16, 23, 24)] == [11, 18, 24, 24]


def test_the_rider_turns_the_bike_a_step_a_tick_and_right_wins():
    assert flight.rotate(0, RIGHT) == 31
    assert flight.rotate(31, LEFT) == 0
    assert flight.rotate(5, RIGHT | LEFT) == 4
    assert flight.rotate(5, 0) == 5


@pytest.mark.parametrize("surface", range(32))
def test_the_landing_window_is_five_behind_to_seven_ahead(surface):
    """The same window whatever the surface: the nose 56 degrees below it to 79
    above it lands, one step more either way crashes."""
    landing = [(surface + d) % 32 for d in range(-5, 8)]
    assert all(flight.lands(a, surface) for a in landing)
    assert not flight.lands((surface - 6) % 32, surface)
    assert not flight.lands((surface + 8) % 32, surface)


# -- a bike in the air ------------------------------------------------------------


def _air(**kw):
    kw.setdefault("state", State.AIR)
    kw.setdefault("speed", Speed(index=60))
    return Bike(Ground(), x=0x4000, y=0x4000, **kw)


def test_a_hanging_jump_keeps_its_speed_and_direction():
    bike = _air(direction=4, hang=3)
    bike.step(THROTTLE, 0, tick=0)
    assert (bike.direction, bike.speed.index, bike.hang) == (4, 60, 2)


def test_after_the_hang_the_jump_falls_and_turns_on_its_period():
    fast = _air(direction=4, jump_class=2)
    fast.step(THROTTLE, 0, tick=1)
    assert fast.speed.index == 56 and fast.direction == 4, "an odd tick does not turn"
    fast.step(THROTTLE, 0, tick=2)
    assert fast.direction == 3


def test_a_nitro_in_the_air_re_aims_the_flight_along_the_nose():
    """Allowed on the tick after a take-off without the J -- and with it, nose up."""
    bike = _air(direction=2, attitude=5, air_nitro_window=1)
    bike.step(THROTTLE, NITRO, tick=0)
    assert bike.direction == 5 and bike.speed.index == NITRO_INDEX
    assert bike.hang == 7 and bike.speed.nitros == 3
    late = _air(direction=2, attitude=5)
    late.step(THROTTLE, NITRO, tick=0)
    assert late.speed.nitros == 4, "no window and no J"
    jet = _air(direction=2, attitude=5, jet=True)
    jet.step(THROTTLE, NITRO, tick=0)
    assert jet.speed.nitros == 3
    nose_down = _air(direction=2, attitude=20, jet=True)
    nose_down.step(THROTTLE, NITRO, tick=0)
    assert nose_down.speed.nitros == 4


# -- landing and crashing ---------------------------------------------------------


def _touching(**hits):
    """Probes where the named cells are solid with the given direction."""
    probes = {name: SKY for name in Probes._fields if name != "at_tile"}
    for name, direction in hits.items():
        probes[name] = Hit(True, False, False, direction)
    return Probes(**probes, at_tile=0)


@pytest.fixture
def landing(monkeypatch):
    """A bike in the air for one tick, touching what the test says: the probes
    the landing reads are the ones taken this tick, so they are frozen."""
    def land(attitude, probes, **kw):
        monkeypatch.setattr(bike_module, "probe", lambda *args: probes)
        kw.setdefault("direction", 26)
        bike = _air(attitude=attitude, **kw)
        bike.step(0, 0, tick=1)
        return bike
    return land


def test_a_bike_inside_the_window_lands_on_the_surface(landing):
    bike = landing(2, _touching(third=4))
    assert bike.state is State.RIDING and bike.direction == bike.attitude == 4


def test_the_attitude_probes_are_asked_before_the_third(landing):
    bike = landing(0, _touching(third=4, attitude_first=0))
    assert bike.direction == 0


def test_outside_the_window_the_landing_is_a_crash(landing):
    bike = landing(16, _touching(third=0, below=0, below_left=0))
    assert bike.state is State.DOWN and bike.down_timer == 57


def test_the_window_is_the_bikes_rulesets(landing):
    """Four steps ahead is inside the original's window and outside a narrower
    ruleset's: the bike asks its own, not the constant."""
    assert landing(4, _touching(third=0, below=0, below_left=0)).state is State.RIDING
    narrow = Ruleset(land_behind=2, land_ahead=3)
    crashed = landing(4, _touching(third=0, below=0, below_left=0), rules=narrow)
    assert crashed.state is State.DOWN


def test_the_computers_fast_bike_lands_whatever_its_nose(landing):
    bike = landing(16, _touching(third=0), checks_landing=False)
    assert bike.state is State.RIDING


def test_head_first_into_ground_above_is_a_crash(landing):
    bike = landing(0, _touching(above=0, third=0))
    assert bike.state is not State.RIDING


@pytest.mark.parametrize("under, state, direction", [
    ({}, State.FALLING, 24),                                   # nothing: straight down
    ({"below_left": 0, "below": 0}, State.DOWN, 26),           # level: down on the ground
    ({"below_left": 4}, State.CRASHING, 36),                   # a climb: a tumble, +32
    ({"below_left": 28}, State.CRASHING, 28),                  # a descent: a tumble
    ({"below_left": 0, "below": 12}, State.CRASHING, 12),
])
def test_a_crash_is_chosen_by_what_is_under_the_bike(landing, under, state, direction):
    bike = landing(16, _touching(third=0, **under))
    assert bike.state is state
    if state is not State.DOWN:
        assert bike.direction == direction


# -- the crash states -----------------------------------------------------------

def _crashed(state, **kw):
    kw.setdefault("speed", Speed(index=0))
    kw.setdefault("x", 0x4000)
    kw.setdefault("y", 0x4000)
    return Bike(Ground(), state=state, **kw)


def test_a_falling_bike_keeps_its_velocity_until_ground_is_under_it(landing):
    bike = _crashed(State.FALLING, direction=24, vx=0, vy=0x400)
    bike.step(THROTTLE, 0)
    assert bike.state is State.FALLING and bike.y == 0x4400
    bike = landing(0, _touching(below=0), state=State.FALLING, vx=0, vy=0x400)
    assert bike.state is State.CRASHING


def test_a_tumble_turns_the_bike_end_over_end():
    bike = _crashed(State.CRASHING, direction=28, attitude=30, tumble_air=1)
    bike.step(0, 0)
    assert bike.attitude == 0


def test_a_tumble_on_level_ground_everywhere_under_it_is_down(landing):
    """Level, or the level a climb's tumble (32) comes to rest on; any other
    heading tumbles on."""
    for direction, state in ((0, State.DOWN), (32, State.DOWN), (26, State.CRASHING)):
        bike = landing(0, _touching(below_left=0, below=0), state=State.CRASHING,
                       direction=direction, speed=Speed(index=0))
        assert bike.state is state, direction
    assert bike.down_timer == 0
    down = landing(0, _touching(below_left=0, below=0), state=State.CRASHING,
                   direction=32, speed=Speed(index=0))
    assert down.down_timer == 57 and down.thrown_back


def test_a_tumble_down_a_climb_travels_back_down_it():
    """Direction 32 + k -- a tumble on the slope it was climbing -- moves as
    16 + k: down the slope, the wrong way round."""
    from game.engine.vector import velocity
    for k in range(9):
        assert velocity(52, 32 + k) == velocity(52, 16 + k)
    vx, vy = velocity(52, 36)
    assert vx < 0 and vy > 0


def test_down_is_the_riders_story_and_the_bike_comes_back_where_it_stopped():
    """57 ticks: the items go and the place is remembered; the rider is thrown,
    lies, walks back; the place comes back; and the bike is stopped there, on the
    8 px grid -- x and y as they were, save y's last three pixels."""
    bike = _crashed(State.DOWN, down_timer=57, x=0x71234, y=0xEB40, jet=True, no_slope=True,
                    speed=Speed(index=0, cap=111))
    xs = []
    for _ in range(57):
        bike.step(0, 0)
        xs.append(bike.x >> 8)
    assert bike.state is State.STOPPED
    assert bike.x == 0x71234 and bike.y == 0xE840
    assert (bike.direction, bike.attitude) == (0, 0)
    assert not bike.jet and not bike.no_slope and bike.speed.cap == 111 - 32
    assert min(xs) < 0x712, "the rider was never thrown"
    assert not bike.rider_off


def test_a_rock_tumbles_the_rider_eight_ticks_in_the_air_first():
    ground = Ground(cells={(r, c): 1 for r in range(16) for c in range(256)},
                    tiles={1: (0xEF,) * 4}, hits={0xEF: Hit(True, False, False, 0)})
    bike = Bike(ground, x=0x4000, y=0x4000, state=State.RIDING, speed=Speed(index=40))
    bike.step(THROTTLE, 0)
    assert bike.state is State.CRASHING and bike.tumble_air == 8 and bike.direction == 32
