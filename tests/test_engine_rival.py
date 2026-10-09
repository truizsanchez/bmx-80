"""The computer's bike and the camera: the rules the original drives them by.

On grounds built in the tests. That they reproduce the original -- a race against
the computer run free, tick for tick, the camera included -- is checked against
recorded runs, where a cartridge exists.
"""

from game.engine import rival as rivals
from game.engine.bike import Bike
from game.engine.camera import Camera
from game.engine.original import Y_LIMIT
from game.engine.rules import Auto, State
from game.engine.original import CAP, LEFT, THROTTLE, UP
from game.engine.run import Run
from game.engine.original import COUNTDOWN
from tests.test_engine_bike import Ground, _floor, _solid_from


def _bike(x, **kw):
    return Bike(Ground(), x=x << 8, y=232 << 8, **kw)


# -- its buttons and its handicap ---------------------------------------------------


def test_the_computer_holds_the_throttle_and_up_and_left_to_bring_a_tumble_round():
    assert rivals.buttons(_bike(0, state=State.RIDING)) == THROTTLE | UP
    flying_left = _bike(0, state=State.AIR, direction=12, attitude=5)
    assert rivals.buttons(flying_left) == THROTTLE | UP | LEFT
    level = _bike(0, state=State.AIR, direction=12, attitude=0)
    assert rivals.buttons(level) == THROTTLE | UP


def test_just_ahead_it_is_at_its_best_and_far_ahead_it_is_held_back():
    """Level A lets it run 64 px ahead at cap 119 with the R, landing anyhow;
    further ahead it is cap 79, no R, its landings checked, and no Up for a loop."""
    player, camera = _bike(100), Camera()
    near = _bike(150)
    held = rivals.drive(near, player, camera, level=0)
    assert near.speed.cap == rivals.BEST_CAP and near.no_slope and not near.checks_landing
    assert held & UP
    far = _bike(200)
    held = rivals.drive(far, player, camera, level=0)
    assert far.speed.cap == CAP and not far.no_slope and far.checks_landing
    assert not held & UP
    # Level C lets it run further ahead before holding it back.
    assert rivals.drive(_bike(200), player, camera, level=2) & UP


def test_far_behind_it_is_put_back_just_off_the_screen():
    """48 px behind the player, it is put 16 px left of the view's edge, riding,
    on the stretch's own row -- and never further back than it is."""
    camera = Camera()
    camera.x = 500 << 8
    player = _bike(540)
    behind = _bike(300, state=State.DOWN, attitude=0x33, down_timer=20)
    rivals.drive(behind, player, camera, level=0)
    assert behind.px == (484, 232) and behind.state is State.RIDING
    assert behind.attitude == 0 and behind.down_timer == 0
    close = _bike(510)
    rivals.drive(close, player, camera, level=0)
    assert close.px[0] == 510, "40 px behind is close enough"


# -- the camera -----------------------------------------------------------------


def test_the_camera_moves_by_the_players_velocity_of_the_iteration_before():
    camera = Camera()
    bike = _bike(32, vx=780, vy=0)
    camera.take(bike)
    assert camera.x == 0, "taking the velocity does not move it"
    camera.move()
    assert camera.x == 780


def test_the_camera_follows_up_or_down_only_from_the_half_the_bike_leaves():
    camera = Camera()
    camera.y = 64 << 8
    falling = _bike(0, vy=300)
    camera.sprite_y = 0x20          # in the upper half, heading down: stays
    camera.take(falling)
    camera.move()
    assert camera.y == 64 << 8
    camera.sprite_y = 0x60          # in the lower half, heading down: follows
    camera.take(falling)
    camera.move()
    assert camera.y == (64 << 8) + 300


def test_the_camera_never_shows_below_the_course():
    camera = Camera()
    camera.sprite_y = 0x60
    camera.take(_bike(0, vy=2000))
    camera.move()
    assert camera.y == Y_LIMIT


def test_the_camera_stops_while_the_bike_celebrates():
    """Past the line the bike rides on out of the picture: the original's camera
    returns early in its fourth automatic mode, and a race that ends in view of
    the bike would be this one's invention."""
    camera = Camera()
    camera.y, camera.sprite_y = 64 << 8, 0x60
    camera.take(_bike(0, vx=780, vy=300, auto=Auto.CELEBRATING))
    camera.move()
    assert (camera.x, camera.y) == (0, 64 << 8)


# -- a race against it -------------------------------------------------------------


def test_the_computers_bike_leaves_the_grid_with_the_player_and_runs_its_own_race():
    ground = _solid_from(_floor(0), 15)
    run = Run(ground, rival=True)
    assert run.rival.speed.cap == rivals.BEST_CAP and run.rival.speed.nitros == 0xFF
    for _ in range(COUNTDOWN + 20):
        run.step(0)
    assert run.bike.state is State.STOPPED, "the player held nothing"
    assert run.rival.state is State.RIDING and run.rival.px[0] > run.bike.px[0]
