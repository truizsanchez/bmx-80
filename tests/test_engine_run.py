"""A run: the countdown, the pad read once an iteration, and the line.

On a ground built in the test, since what is under test is the loop around the
physics and not any course.
"""

from game.engine.original import FLASH, J, N, T
from game.engine.rules import Auto, State
from game.engine.original import NITRO, THROTTLE
from game.engine.run import FINISHED, TIME_UP, Run
from game.engine.original import COUNTDOWN, FINISH_LINE, HURRY, LAP_LINE, START_X, START_Y
from tests.test_engine_bike import _floor, _solid_from


def _run(items=(), **kw):
    # The original's grid is at y 232: a ground from metatile row 15 is under it.
    ground = _solid_from(_floor(0), 15)
    ground._items = list(items)
    return Run(ground, **kw)


def test_the_bike_waits_on_the_grid_through_the_countdown():
    run = _run()
    assert run.bike.px == (START_X, START_Y)
    for _ in range(COUNTDOWN - 1):
        run.step(THROTTLE)
        assert run.bike.state is State.COUNTDOWN
    assert run.bike.px[0] == START_X


def test_the_throttle_held_through_the_countdown_leaves_at_once():
    """The index climbs during the countdown, so the iteration it ends the bike is
    stopped, has a magnitude, and is riding."""
    run = _run()
    for _ in range(COUNTDOWN):
        run.step(THROTTLE)
    assert run.bike.state is State.RIDING
    assert run.bike.px[1] == START_Y, "the idling shiver was left in y"


def test_a_button_is_new_only_on_the_iteration_it_goes_down():
    run = _run()
    for _ in range(COUNTDOWN):
        run.step(THROTTLE)
    run.step(THROTTLE | NITRO)
    assert run.bike.speed.nitros == 3
    for _ in range(20):
        run.step(THROTTLE | NITRO)
    assert run.bike.speed.nitros == 3, "a held button fired again"


def test_the_loop_counter_counts_iterations():
    run = _run()
    for _ in range(300):
        run.step(0)
    assert run.iterations == 300 and run.tick == 300 & 0xFF


def _riding_at(x, **kw):
    run = _run(**kw)
    run.countdown = 0
    run.bike.state = State.RIDING
    run.bike.x = x << 8
    run.bike.speed.index = 79
    return run


def test_past_the_line_the_game_takes_the_bike_over_and_it_celebrates():
    """The throttle is held for you from the line; 48 px on the game takes the
    bike; from 8192 on the ground it celebrates, and when that is over, so is
    the race -- finished, with the clock stopped at the take-over."""
    run = _riding_at(FINISH_LINE - 2)
    run.step(0)
    assert run.bike.auto is Auto.THROTTLE
    while run.bike.auto < Auto.RIDING:
        run.step(0)
    stopped = run.elapsed
    while not run.finished:
        run.step(0)
    assert run.over == FINISHED
    assert run.elapsed == stopped
    assert run.bike.attitude == 4


def test_the_clocks_move_two_hundredths_a_tick_and_time_can_run_out():
    run = _run(limit=30)
    for _ in range(COUNTDOWN):
        run.step(THROTTLE)
    left = run.left
    run.step(THROTTLE)
    assert run.left == left - 2 and run.elapsed == 4
    while not run.finished:
        run.step(THROTTLE)
    assert run.over == TIME_UP and run.left == 0


def test_the_clock_says_when_it_is_pressing_so_the_music_can_hurry():
    """Why this test: the original reads the clock every iteration for the music
    as well as for the bar, and under ten seconds it plays the tune faster. Ten
    seconds is the number, not the bar's own scale -- the bar is capped at
    fifty-five and says nothing about this -- so it lives here with the clock it
    is a threshold on.
    """
    run = _run(limit=HURRY + 20)
    assert not run.hurrying
    while run.left > HURRY:
        run.step(THROTTLE)
    assert run.left == HURRY and not run.hurrying, "ten seconds is not under ten"
    run.step(THROTTLE)
    assert run.hurrying


def test_the_computers_bike_has_a_clock_of_its_own_and_no_time_until_the_line():
    """Why this test: the results put a time against the computer's bike, and it
    is not the player's -- the two reach the line at different moments, and the
    race ends when the *player* does, with the other bike usually still riding.
    A results screen that showed one clock for both would be a time nobody rode.
    """
    run = _run(rival=True)
    for _ in range(COUNTDOWN + 20):
        run.step(THROTTLE)
    assert run.elapsed and run.rival_elapsed, "both clocks are running"
    assert run.rival_time is None, "and neither bike is at the line yet"
    run.rival.auto = Auto.RIDING
    stopped = run.rival_elapsed
    for _ in range(10):
        run.step(THROTTLE)
    assert run.rival_elapsed == stopped, "the game has its bike; its clock is done"
    assert run.rival_time == stopped
    assert run.elapsed > stopped, "and the player's is still going"


def test_a_run_without_the_computer_has_no_time_for_it():
    run = _run()
    assert run.rival is None and run.rival_time is None


def test_a_crate_is_taken_once_and_the_lap_line_puts_it_back():
    """An N at the bike's metatile: four nitros, the cell emptied; and at the lap
    line it is back, in the map and to be taken again."""
    run = _riding_at(0x40, items=[(N, 14, 4)])
    run.step(THROTTLE)
    assert run.bike.speed.nitros == 8
    assert run.ground.metatile(14, 4) == 0xFF
    run.step(THROTTLE)
    assert run.bike.speed.nitros == 8, "taken twice"
    run.bike.x = LAP_LINE << 8
    run.step(THROTTLE)
    assert run.items[0].there and run.ground.metatile(14, 4) == N and run.laps_left == 0


def test_the_lap_line_puts_the_sign_over_the_finish_up():
    """Why this test: the sign is what tells a player the next time round the
    course is the last one, and the lap line is the only moment it can go up --
    the original writes it there and nowhere else. **The computer's bike must
    not put it up**: it crosses the same line, and the lap is the player's.
    """
    run = _run(limit=30000, rival=True)
    for _ in range(COUNTDOWN):
        run.step(THROTTLE)
    assert not run.ground.signed
    run.rival.x = LAP_LINE << 8
    run.step(THROTTLE)
    assert not run.ground.signed, "the computer's bike crossing it is not a lap"
    run.bike.x = LAP_LINE << 8
    run.step(THROTTLE)
    assert run.ground.signed


def test_a_t_adds_ten_seconds_and_a_secret_needs_the_bike_upside_down():
    run = _riding_at(0x40, items=[(T, 14, 4), (J, 14, 4)])
    left = run.left
    run.step(THROTTLE)
    assert run.left == left + 1000 - 2
    assert not run.bike.jet, "the J taken the right way up"
    run.bike.attitude = 16
    run.bike.state = State.AIR
    run.step(THROTTLE)
    assert run.bike.jet


def test_a_secret_taken_leaves_a_flourish_that_rises_and_goes():
    """Why this test: the J and the mini-maniacs are invisible and are taken
    upside down, so this is the only thing that ever says one was there -- and
    it has to end, because a flourish that stayed would be a thing on the
    course. It rises as it goes, which is what tells it from a crate.
    """
    run = _riding_at(0x40, items=[(T, 14, 4), (J, 14, 4)])
    run.bike.attitude = 16
    run.bike.state = State.AIR
    run.step(THROTTLE)
    assert run.flash is not None and run.flash.kind == J
    top, left = run.flash.y, run.flash.left
    run.step(THROTTLE)
    assert run.flash is not None
    assert run.flash.y == top - 1 and run.flash.left == left - 1
    for _ in range(FLASH):
        run.step(THROTTLE)
    assert run.flash is None, "and it is over, not a thing left on the course"


def test_a_crate_leaves_no_flourish_because_a_crate_can_be_seen():
    run = _riding_at(0x40, items=[(N, 14, 4)])
    run.step(THROTTLE)
    assert run.bike.speed.nitros == 8 and run.flash is None
