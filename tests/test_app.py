"""The window, driven with the real keys.

`main.py` is the only file that owns the frame loop: the menu, and a ride of one
of the original's courses. What a key does there is exactly the kind of thing that works in the hand
and rots in a refactor.

Pyxel supports `init(headless=True)` + `set_btn()` + `flip()`, so this is the
real `App.update` and the real `App.draw` rather than a re-implementation of
them.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

#: Three courses that are names and nothing else: nothing here builds a map.
COURSES = [("c%d" % n, lambda: None) for n in range(3)]


@pytest.fixture
def app(pyxel_headless, tmp_path):
    import main
    from game.menu import Menu

    # The window is `tests/conftest.py`'s, because Pyxel only has one per
    # process. Everything else is the real thing.
    built = main.App(run=False, window=False)
    # Its own scoreboard, in a temporary file: a test that wrote the real one
    # would be scribbling on the player's times.
    built.menu = Menu(COURSES, records={}, path=str(tmp_path / "records.json"))
    # On the menu, which is what these are about: the title's fourth row is
    # what opens it, and that is walked by a test of its own.
    built.mode = main.MENU
    yield built
    for key in _KEYS:
        pyxel_headless.set_btn(key, False)


def _press(app, key, frames=1):
    """Hold a key for one frame of the real update, then let go.

    `btnp` reads the frame counter, so a key held across two `update`s repeats
    rather than pressing twice -- which is why every press here is followed by a
    release and a frame of nothing.
    """
    import pyxel

    for _ in range(frames):
        pyxel.set_btn(key, True)
        app.update()
        pyxel.flip()
        pyxel.set_btn(key, False)
        app.update()
        pyxel.flip()


def _all_keys():
    import pyxel

    return (pyxel.KEY_UP, pyxel.KEY_DOWN, pyxel.KEY_LEFT, pyxel.KEY_RIGHT,
            pyxel.KEY_RETURN, pyxel.KEY_ESCAPE, pyxel.KEY_TAB, pyxel.KEY_J, pyxel.KEY_K,
            pyxel.KEY_SPACE)


_KEYS = _all_keys()



def test_it_opens_on_the_menu_and_draws_it(app):
    """The first frame, drawn: a `draw` that raised would be a window that never opens."""
    app.draw()



def test_the_arrows_move_whatever_the_menu_has_in_hand(app):
    """One pair of arrows and two things to choose with it, so up and down go
    wherever TAB last left them."""
    import pyxel

    from game.course import BUMPY, CRAZY, START_LEVEL
    from game.menu import PICKING_COURSE, PICKING_LEVEL

    assert app.menu.course == 0 and app.menu.level == START_LEVEL
    assert app.menu.focus is PICKING_COURSE

    _press(app, pyxel.KEY_DOWN)
    assert app.menu.course == 1 and app.menu.level == START_LEVEL

    _press(app, pyxel.KEY_TAB)
    assert app.menu.focus is PICKING_LEVEL
    _press(app, pyxel.KEY_UP)
    assert app.menu.level == CRAZY, "the level did not wrap"
    _press(app, pyxel.KEY_UP)
    assert app.menu.level == BUMPY
    assert app.menu.course == 1, "the arrows moved the list they were not on"

    _press(app, pyxel.KEY_TAB)
    _press(app, pyxel.KEY_TAB)
    assert app.menu.focus is PICKING_COURSE, "TAB comes round the three"
    _press(app, pyxel.KEY_DOWN)
    assert app.menu.course == 2 and app.menu.level == BUMPY



def test_escape_on_the_menu_goes_back_to_the_title_and_on_the_title_quits(
        app, monkeypatch):
    """ESC is back, and out of the game from the front end.

    Which is only true because `pyxel.init` names `quit_key=KEY_NONE`. Its
    default is ESC, so for a long time Pyxel took the key first and `main`'s own
    ESC never ran in a real window at all.

    **No test could have caught that**, this one included: the quit key is read
    inside `pyxel.run`, and every test here drives `update` directly. What is
    checkable is the half that is ours, so that is what this checks.

    `pyxel.quit` is replaced rather than called: it does not return, it ends the
    process, and a test that let it through would take pytest with it.
    """
    import pyxel

    import main

    asked = []
    monkeypatch.setattr(pyxel, "quit", lambda: asked.append(True))

    _press(app, pyxel.KEY_ESCAPE)
    assert app.mode is main.FRONT and not asked, "ESC on the menu is back to the title"
    _press(app, pyxel.KEY_ESCAPE)
    assert asked == [True], "ESC on the front end did not ask to quit"


def test_without_a_cartridge_the_front_end_rides_the_projects_courses(
        pyxel_headless, tmp_path):
    """Why this test: the original's screens -- the title, the card, the
    results, the clock running out -- were written for a run without a
    cartridge too, and nothing ever reached them: with no `--rom` the game
    opened on the menu, and a race off it ended on a frozen screen. Now the
    front end is the game either way, on the courses `maps/courses/` has.
    """
    import main
    import maps
    from game import front as front_model

    app = main.App(run=False, window=False)
    assert app.mode is main.FRONT and app.front is not None
    assert [name for name, _ in app.front.courses] == [name for name, _ in maps.LISTED]
    assert front_model.MORE in app.front.rows, "and a way to the rest"


def test_the_titles_fourth_row_opens_the_menu(pyxel_headless, tmp_path):
    """FREE RIDE -- the eight and the drafts, in any mode -- is behind the
    title's fourth row, with a cartridge or without one."""
    import pyxel

    import main
    from game import front as front_model

    app = main.App(run=False, window=False)
    app.front.records, app.front.path = {}, str(tmp_path / "r.json")
    _press(app, pyxel.KEY_RETURN)                 # past the opening screen
    for _ in range(len(front_model.MODES)):
        _press(app, pyxel.KEY_DOWN)
    _press(app, pyxel.KEY_RETURN)
    assert app.mode is main.MENU
    assert app.menu.label == "courses", "FREE RIDE opens on the eight"
    assert app.front.step is front_model.TITLE, "and ESC finds the title where it was"
    app.draw()


def test_a_race_off_the_menu_goes_back_to_the_menu(app):
    """With a front end in the game, a race is either one of its own or one off
    the menu, and each goes back where it came from: ESC out of a menu race
    with the title behind it is the menu, not the title."""
    import pyxel

    import main
    from game.course import Course, Tileset
    from game.menu import Menu
    from maps import read

    tiles = Tileset({"floor": {"dir": 0}}, {"road": ["sky", "sky", "floor", "floor"]})
    app.menu = Menu([("ours", lambda: Course(
        tiles, {"road": [["road"]]}, read.tables(),
        stampings=[(15, c, "road") for c in range(256)]))], records={}, path=None)
    _press(app, pyxel.KEY_RETURN)
    assert app.mode is main.RACING
    _press(app, pyxel.KEY_ESCAPE)
    assert app.mode is main.MENU


def test_left_and_right_switch_the_list(app, tmp_path):
    """The menu's own tabs, driven through the real key path.

    Its own two-section menu rather than the app's: `maps/drafts/` is gitignored,
    so the number of tabs on the author's machine is not the number on a clone
    and a test that read it would pass here and fail there.
    """
    import pyxel

    from game.menu import Menu

    app.menu = Menu(COURSES, drafts=[("draft", lambda: None)],
                    records={}, path=str(tmp_path / "records.json"))
    assert app.menu.label == "courses"

    _press(app, pyxel.KEY_RIGHT)
    assert app.menu.label == "custom" and app.menu.name == "draft"

    _press(app, pyxel.KEY_LEFT)
    assert app.menu.label == "courses"



def test_the_horizontal_arrows_are_handed_over_with_the_rest(app, tmp_path):
    """TAB hands over all four arrows and not half of them.

    This asserted the opposite for one revision -- left and right went on
    switching the list from the level row -- and the level, which is the one
    thing on this screen laid out horizontally, had no horizontal key at all.
    """
    import pyxel

    from game.course import BUMPY, EASY
    from game.menu import Menu, PICKING_LEVEL

    app.menu = Menu(COURSES, drafts=[("draft", lambda: None)],
                    records={}, path=str(tmp_path / "records.json"))
    _press(app, pyxel.KEY_TAB)
    assert app.menu.focus is PICKING_LEVEL and app.menu.level == EASY

    _press(app, pyxel.KEY_RIGHT)
    assert app.menu.level == BUMPY
    assert app.menu.label == "courses", "the arrows still moved the list"

    _press(app, pyxel.KEY_LEFT)
    assert app.menu.level == EASY

    # And round, past the mode, to where they mean the lists again.
    _press(app, pyxel.KEY_TAB)
    _press(app, pyxel.KEY_TAB)
    _press(app, pyxel.KEY_RIGHT)
    assert app.menu.label == "custom" and app.menu.level == EASY



def test_the_menu_draws_with_two_tabs_and_a_scrolled_list(app, tmp_path):
    """The picture, over the states the model can be in. Asserts nothing about
    pixels -- what it catches is a `draw_menu` that raises on one of them, which
    is how a window-free suite covers a screen."""
    from game.menu import Menu, WINDOW
    from game.render import menu_draw

    long_list = [("c%d" % n, lambda: None) for n in range(WINDOW + 4)]
    app.menu = Menu(long_list, drafts=[("draft", lambda: None)],
                    records={}, path=str(tmp_path / "records.json"))
    menu_draw.draw_menu(app.menu)
    app.menu.course = len(long_list) - 1
    assert app.menu.more_above and not app.menu.more_below
    menu_draw.draw_menu(app.menu)
    app.menu.move_section(1)
    menu_draw.draw_menu(app.menu)
    app.menu.move_focus()
    menu_draw.draw_menu(app.menu)



def test_the_screen_says_which_of_the_two_the_arrows_are_on(pyxel_headless):
    """The one mode this screen has, and the reason it is an honest one.

    Both halves are drawn the whole time and the live one is filled where the
    other is outlined, so the pixels differ between the two states -- which is
    what "you can see which it is" means, measured rather than asserted about the
    source. A menu that drew the same picture either way would be the invisible
    mode the editor has paid for four times.
    """
    from game.constants import SCREEN_H, SCREEN_W
    from game.menu import Menu
    from game.render import menu_draw

    def pixels():
        return [pyxel_headless.screen.pget(x, y)
                for y in range(SCREEN_H) for x in range(SCREEN_W)]

    menu = Menu([("a", lambda: None), ("b", lambda: None)], records={})
    menu_draw.draw_menu(menu)
    on_course = pixels()
    menu.move_focus()
    menu_draw.draw_menu(menu)
    on_level = pixels()
    assert on_course != on_level


# -- riding the original's courses ------------------------------------------------


def _cartridge_app(pyxel_headless, tmp_path, **kw):
    """The window with one course of a cartridge's on it -- a ground built here,
    since no cartridge ships with the repository.

    **No cartridge object**, only its courses, which is the run this game has to
    hold up as well: every screen is then drawn from nothing rather than out of
    the cartridge's own tiles.
    """
    import main
    from game.front import Front
    from tests.test_engine_bike import _floor, _solid_from

    course = ("course 1", lambda: _solid_from(_floor(0), 15))
    app = main.App(run=False, window=False, cartridge=[course], **kw)
    app.front = Front([course], records={}, path=str(tmp_path / "r.json"), more=True)
    return app


def _ride(app):
    """Start a race the way a player does: the course, the level, and the card.

    A helper rather than four lines in each test, because the front end is
    between the window opening and a race for every one of them and none of them
    is about it.
    """
    import pyxel

    from game import front as front_model

    _press(app, pyxel.KEY_RETURN)                 # past the opening screen
    _press(app, pyxel.KEY_RETURN)                 # the way to play
    _press(app, pyxel.KEY_RETURN)                 # the course
    _press(app, pyxel.KEY_RETURN)                 # the level
    while app.front.step is front_model.CARD:
        app.update()
        pyxel.flip()


def test_the_card_is_shown_before_the_race_and_then_gets_out_of_the_way(
        pyxel_headless, tmp_path):
    """Why this test: the original names the course, its record and the time to
    qualify for about two seconds before the race, and nothing the player does
    shortens it. A card that stayed would be a race nobody can see, and one that
    never came up would take the two numbers with it.
    """
    import main
    import pyxel

    from game import front as front_model

    app = _cartridge_app(pyxel_headless, tmp_path)
    _press(app, pyxel.KEY_RETURN)                 # past the opening screen
    _press(app, pyxel.KEY_RETURN)                 # the way to play
    _press(app, pyxel.KEY_RETURN)                 # the course
    _press(app, pyxel.KEY_RETURN)                 # the level
    assert app.front.step is front_model.CARD
    app.draw()
    for _ in range(front_model.CARD_HOLD - 3):
        app.update()
        pyxel.flip()
    assert app.front.step is front_model.CARD, \
        "the whole of it, and Start does not cut it short"
    assert app.ride.iterations == 0, "and nothing steps behind it"
    for _ in range(3):
        app.update()
        pyxel.flip()
    assert app.mode is main.RACING


def test_with_a_cartridge_the_originals_screens_are_the_front_end(
        pyxel_headless, tmp_path):
    """Why this test: with a cartridge the game starts where the original starts
    -- on its own screen, choosing a course -- and **not** on this game's menu,
    which is the door to this game's own maps. A menu tab of cartridge courses
    would be two doors to one race, and the original's card and results belong
    behind only one of them.
    """
    import main
    import pyxel

    from game import front as front_model

    app = _cartridge_app(pyxel_headless, tmp_path)
    assert app.mode is main.FRONT and app.front.step is front_model.SPLASH
    app.draw()
    _press(app, pyxel.KEY_RETURN)
    assert app.front.step is front_model.TITLE
    app.draw()
    assert "cartridge" not in [label for label, _rows in app.menu.sections]
    _ride(app)
    assert app.mode is main.RACING and app.ride is not None
    app.draw()


def test_the_engine_steps_41_times_for_every_60_frames(pyxel_headless, tmp_path):
    """Racing, that is: the start is held and then counted down at a slower rate
    of its own, so the rate this pins is measured once the race is running."""
    import pyxel

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    while app.ride.countdown:
        app.update()
        pyxel.flip()
    before = app.ride.iterations
    for _ in range(60):
        app.update()
        pyxel.flip()
    assert app.ride.iterations - before == 41


def _free_ride(app, tmp_path):
    """A race off FREE RIDE on a course of flat road, SOLO, at whatever mode
    the menu is set to."""
    from game.course import Course, Tileset
    from game.menu import Menu
    from maps import read

    tiles = Tileset({"floor": {"dir": 0}}, {"road": ["sky", "sky", "floor", "floor"]})
    mode = app.menu.mode
    app.menu = Menu([("flat", lambda: Course(
        tiles, {"road": [["road"]]}, read.tables(),
        stampings=[(15, c, "road") for c in range(256)]))],
        records={}, path=str(tmp_path / "r.json"), mode=mode)
    app._ride()


def test_excessive_steps_the_same_race_once_a_frame(pyxel_headless, tmp_path):
    """Why this test: the excessive mode is the same race sooner, and "sooner" is
    this number and nothing else -- the rules it rides by are classic's, so a
    course is ridden iteration for iteration as it is there. It is FREE RIDE's
    to choose, and `--mode` is where the menu starts."""
    import pyxel

    import main
    from game.engine.rules import CLASSIC
    from game.mode import EXCESSIVE

    app = main.App(run=False, window=False, mode=EXCESSIVE)
    assert app.menu.mode == "excessive"
    _free_ride(app, tmp_path)
    assert app.ride.rules is CLASSIC
    app.start_hold = 0
    while app.ride.countdown:
        app.update()
        pyxel.flip()
    before = app.ride.iterations
    for _ in range(60):
        app.update()
        pyxel.flip()
    assert app.ride.iterations - before == 60


def test_the_front_end_is_the_originals_whatever_the_mode(pyxel_headless, tmp_path):
    """The original's screens ride the original's way: `--mode excessive` sets
    where FREE RIDE starts and leaves the front end at 41 steps a second."""
    from game.mode import CLASSIC, EXCESSIVE

    app = _cartridge_app(pyxel_headless, tmp_path, mode=EXCESSIVE)
    _ride(app)
    assert app.play is CLASSIC


def test_a_finish_in_excessive_is_not_offered_to_the_board(pyxel_headless, tmp_path):
    """Two ways of playing are two races, and the board is classic's: a time in
    excessive would sit beside the original's as if it were one."""
    import main
    from game.engine.run import FINISHED
    from game.mode import EXCESSIVE

    app = main.App(run=False, window=False, mode=EXCESSIVE)
    _free_ride(app, tmp_path)
    app.start_hold = 0
    app.ride.elapsed = 4321
    app.ride.over = FINISHED
    app.update()
    assert app.menu.best is None


def test_a_course_of_our_own_plays_one_of_the_cartridges_tunes_by_its_name():
    """With a cartridge a draft sounds like the rest of the game: one of the
    eight course tunes, the same one every time for the same name."""
    import main

    tunes = {main.tune_of("draft%d" % n) for n in range(64)}
    assert tunes <= set(range(1, 9)) and len(tunes) > 1
    assert main.tune_of("my course") == main.tune_of("my course")


def test_a_mode_there_is_none_of_is_refused_by_name():
    import main

    assert main.mode_wanted([]).name == "classic"
    assert main.mode_wanted(["--mode", "excessive"]).name == "excessive"
    with pytest.raises(SystemExit, match="classic, excessive"):
        main.mode_wanted(["--mode", "turbo"])


def test_the_start_is_held_before_anything_steps(pyxel_headless, tmp_path):
    """The original sits on the grid for about 54 frames with the countdown at
    48 before it starts down, every level. Here that is frames in which the race
    does not move -- the sound's own clock runs through them, as its driver does
    on the timer whatever the main loop is doing.
    """
    import main
    import pyxel

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    for _ in range(main.START_HOLD - 1):
        app.update()
        pyxel.flip()
    assert app.ride.iterations == 0, "held: nothing has stepped"
    for _ in range(4):
        app.update()
        pyxel.flip()
    assert app.ride.iterations > 0, "and then it goes"


def test_k_is_the_throttle_and_j_the_nitro(pyxel_headless, tmp_path):
    """A on K and B on J, where the right hand held them."""
    import pyxel

    from game.engine.original import COUNTDOWN

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    pyxel_headless.set_btn(pyxel.KEY_K, True)
    while app.ride.iterations < COUNTDOWN + 5:
        app.update()
        pyxel.flip()
    assert app.ride.bike.speed.index > 0
    for _ in range(4):
        pyxel_headless.set_btn(pyxel.KEY_J, True)
        app.update()
        pyxel.flip()
    pyxel_headless.set_btn(pyxel.KEY_J, False)
    pyxel_headless.set_btn(pyxel.KEY_K, False)
    assert app.ride.bike.speed.nitros == 3


def test_start_pauses_the_ride_and_escape_leaves_it(pyxel_headless, tmp_path):
    import pyxel

    import main

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    _press(app, pyxel.KEY_RETURN)
    assert app.mode is main.PAUSED
    held = app.ride.iterations
    for _ in range(10):
        app.update()
        pyxel.flip()
    assert app.ride.iterations == held
    app.draw()
    _press(app, pyxel.KEY_ESCAPE)
    assert app.mode is main.FRONT, "out of a race is back to the screen it was chosen on"


def test_the_menu_rides_a_course_of_this_games_own(app):
    """Why this test, and it is the one this whole rebuild was for: a course of
    this game's own answers the engine exactly as the cartridge's does -- both
    are a `Ground` -- so Start on the menu has to start a race, on our data,
    with no cartridge anywhere.

    It used to assert the opposite, because `App._ride` was a stub. This is the
    same test with the claim turned over.
    """
    import pyxel

    import main
    from game.course import Course, Tileset
    from game.menu import Menu
    from maps import read

    tiles = Tileset({"floor": {"dir": 0}},
                    {"road": ["sky", "sky", "floor", "floor"]})
    pieces = {"road": [["road"]]}

    def build():
        return Course(tiles, pieces, read.tables(),
                      stampings=[(15, c, "road") for c in range(256)])

    app.menu = Menu([("ours", build)], records={}, path=None)
    _press(app, pyxel.KEY_RETURN)
    assert app.mode is main.RACING
    assert app.ride is not None
    assert isinstance(app.ride.ground, Course), "and it is riding a course of ours"
    assert app.ride.bike.ground is app.ride.ground


def test_a_course_of_our_own_starts_on_its_own_clock_at_the_level_ridden(app):
    """Why this test: every course file carries the three qualifying times, and
    for a long time no race read them -- ours ran on ten minutes while the
    cartridge's ran on its own. A level is a clock, so without this the three
    levels of our courses were one."""
    import pyxel

    from game.course import Course, Tileset
    from game.engine.original import NO_LIMIT
    from game.menu import Menu
    from maps import read

    tiles = Tileset({"floor": {"dir": 0}}, {"road": ["sky", "sky", "floor", "floor"]})

    def build(limits):
        return lambda: Course(tiles, {"road": [["road"]]}, read.tables(),
                              stampings=[(15, c, "road") for c in range(256)], limits=limits)

    app.menu = Menu([("timed", build((80.0, 45.5, 16.0))), ("untimed", build(()))],
                    records={}, path=None)
    app.menu.level = 1
    _press(app, pyxel.KEY_RETURN)
    assert app.ride.left == app.limit == 4550
    import main
    assert main.own_limit(build(())(), 1) == NO_LIMIT


def test_select_on_the_menu_puts_the_computers_bike_in_the_race(app):
    """Why this test: Select toggled VS COMPUTER on the menu and the race never
    heard of it -- `_ride` built the run without the rival, so a player with no
    cartridge chose to race the computer and rode alone."""
    import pyxel

    from game.course import Course, Tileset
    from game.menu import Menu
    from maps import read

    tiles = Tileset({"floor": {"dir": 0}}, {"road": ["sky", "sky", "floor", "floor"]})

    def build():
        return Course(tiles, {"road": [["road"]]}, read.tables(),
                      stampings=[(15, c, "road") for c in range(256)])

    app.menu = Menu([("ours", build)], records={}, path=None)
    _press(app, pyxel.KEY_SPACE)
    assert app.menu.rival, "Select did not choose VS COMPUTER"
    _press(app, pyxel.KEY_RETURN)
    assert app.ride.rival is not None, "the race has no computer's bike in it"


def test_ride_goes_straight_onto_one_course_and_nothing_else(pyxel_headless, tmp_path):
    """Why this test: the editor rides what it is drawing by starting the game
    on one course file with `--ride`, and that has to be a race at once -- not
    the menu, and not the cartridge's front end -- on exactly that file."""
    import json

    import main
    from game.course import Course
    from maps import read

    path = tmp_path / "drawn.json"
    path.write_text(read.dump({"pieces": [], "items": [], "limits": [60.0] * 3,
                               "teleports": []}))
    ride = main.ride_wanted(["main.py", "--ride", str(path)])
    assert ride is not None and ride[0] == "drawn"
    app = main.App(run=False, window=False, ride=ride)
    assert app.mode is main.RACING
    assert isinstance(app.ride.ground, Course)
    assert [name for name, _ in app.menu.tracks] == ["drawn"]
    assert json.loads(path.read_text())["limits"] == [60.0] * 3
    with pytest.raises(SystemExit):
        main.ride_wanted(["main.py", "--ride"])


def test_a_course_with_art_draws_it_and_one_without_draws_its_collision(pyxel_headless, tmp_path):
    """Both pictures of a run are drawn: the cartridge's tiles out of their bank,
    and the collision's squares when there is no art."""

    from game.render import rom_art

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    from game.render.style import EDGE, SKY

    # Every tile the darkest colour: the sky in the corner comes out dark.
    rom_art.install_art(lambda tile: (3,) * 64)
    app.draw()
    assert pyxel_headless.screen.pget(10, 10) == EDGE
    rom_art.install_art(None)
    app.draw()
    assert pyxel_headless.screen.pget(10, 10) == SKY


def test_the_flourishes_past_the_line_are_the_bike_rearing_up(pyxel_headless):
    """The rider's flourishes are poses past 31, and the rider's own poses live
    there too: read as those, the bike vanished in the air after the take-over
    line and came back on landing. They are the whole bike, nose ever higher."""
    from game.engine.original import FLOURISHES
    from game.render import ride_draw

    pictures = [ride_draw.bike_picture(a) for a in FLOURISHES]
    assert all(p is not None and p.startswith("bike") for p in pictures)
    assert pictures == sorted(pictures) and len(set(pictures)) == len(pictures)
    assert ride_draw.bike_picture(0x29) is None, "the rider thrown off is not on the bike"


def test_with_a_cartridge_the_bike_is_its_own_and_the_wreck_stays_where_it_fell(
        pyxel_headless):
    """Why this test: with a cartridge the bike is drawn in the cartridge's own
    sprites, every pose of it, where it used to be a picture on disk whatever
    was installed. The pose the rider comes off in draws the bike lying on the
    ground in slots the thrown rider's poses do not reach, so it has to stay at
    the place the crash saved, not follow the rider through the air. And the
    computer's bike goes through the second palette, which is what makes it the
    other bike.
    """
    from types import SimpleNamespace

    from game.engine.original import PIXEL
    from game.render import ride_draw, rom_art
    from game.rom.cartridge import OBJECT_PALETTES
    from tests.test_rom import _posed

    rider, lying = 1, 2
    poses = [[1, 0, 0, rider, 0]] * 0x29
    poses += [[1, 0, 0, rider, 0], [2, 0, 0, rider, 0, 8, 0, lying, 0]]
    cartridge = _posed(poses)
    raw = bytearray(cartridge.data)
    raw[OBJECT_PALETTES[0]], raw[OBJECT_PALETTES[1]] = 0xE4, 0xA8
    cartridge = type(cartridge)(bytes(raw), check=False)
    video = bytearray(64)
    video[16:32] = b"\xff" * 16                    # the rider: colour 3 throughout
    video[32:48] = b"\xff\x00" * 8                # the bike lying: colour 1
    rom_art.install_art(lambda tile: (0,) * 64, video)
    rom_art.install_cartridge(cartridge)
    try:
        thrown = SimpleNamespace(px=(40, 40), attitude=0x29, player=True, rider_off=True,
                                 thrown_back=True, saved=(60 << PIXEL, 80))
        pyxel_headless.cls(3)
        ride_draw.draw_bike(thrown, 0, 0)
        screen = pyxel_headless.screen
        assert screen.pget(40, 40) == 0, "the rider, in the first palette"
        assert screen.pget(80, 68) == 2, "the bike lying where the crash saved it"
        assert screen.pget(40, 48) == 3, "and not under the rider"

        rival = SimpleNamespace(px=(40, 40), attitude=0, player=False, rider_off=False)
        pyxel_headless.cls(3)
        ride_draw.draw_bike(rival, 0, 0)
        assert screen.pget(40, 40) == 1, "the computer's bike in the second palette"
    finally:
        rom_art.install_art(None)
        rom_art.install_cartridge(None)


def test_the_band_says_how_the_race_ended(pyxel_headless, tmp_path):
    """Finished shows the time taken; out of time says so. Drawn both ways, since
    a band that raised on either would be the last frame of every race."""
    from game.engine.run import FINISHED, TIME_UP
    from game.render import ride_draw, rom_art

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    rom_art.install_art(None)
    for over in (FINISHED, TIME_UP):
        app.ride.over = over
        app.draw()
    assert ride_draw.clock(12345, fraction=True) == "2:03.45"
    assert ride_draw.clock(8000) == "1:20"


class _Heard:
    """A voice that writes down what it was asked for instead of playing it."""

    def __init__(self):
        self.asked = []

    def play(self, sound):
        self.asked.append(sound)

    def tick(self):
        pass


def test_each_screen_asks_for_its_own_sound_once_as_it_goes_up(
        pyxel_headless, tmp_path):
    """Why this test: the screens' sounds are asked for on a change of screen
    and the screen is decided somewhere else, so the one way this rots is a
    request made every frame -- a tune restarted sixty times a second, which is
    a tune that never plays. What is pinned is the order and the once.

    The title is silent on the original and the tune belongs to the screen a
    course is chosen on, which is the part of this that is easy to get backwards.
    """
    import pyxel

    import main
    from game import front as front_model
    from game.rom import mixer as sound

    app = _cartridge_app(pyxel_headless, tmp_path)
    app.screens = _Heard()
    for _ in range(3):
        app.update()                              # frames of the opening screen
    assert app.screens.asked == [], "the screen the game opens on is silent"
    _press(app, pyxel.KEY_RETURN)                 # past it, to the title
    app.update()
    assert app.screens.asked == [], "and so is the title"
    _press(app, pyxel.KEY_DOWN)
    assert app.screens.asked == [sound.CURSOR], "but its cursor is not"
    _press(app, pyxel.KEY_RETURN)                 # the title settles: the course
    assert app.front.step is front_model.COURSE
    assert app.screens.asked[-2:] == [sound.CONFIRM, sound.SELECT_MUSIC]
    asked = list(app.screens.asked)
    for _ in range(5):
        app.update()
    assert app.screens.asked == asked, "and the tune is asked for once, not a frame"
    _press(app, pyxel.KEY_RETURN)                 # the level
    _press(app, pyxel.KEY_RETURN)                 # settled: the card
    assert app.front.step is front_model.CARD
    assert app.screens.asked[len(asked):] == [main.SILENCE, sound.CONFIRM], \
        "and the card cuts the tune off with the sound that settled the level"


def test_a_clock_that_ran_out_blinks_over_the_race_and_ends_on_game_over(
        pyxel_headless, tmp_path):
    """Why this test: the box used to blink on the race's iteration counter --
    which stops the moment the race is over -- so it was frozen on or off for
    good, and about half of races showed a box with no words in it at all. It
    blinks on the wait now, and the wait is also what carries the game off the
    race screen: before this the app sat in a stopped race with no way out of it
    but the key that quits.
    """
    import pyxel

    import main
    from game import front as front_model
    from game.engine.run import TIME_UP
    from game.rom import panel

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    app.screens, app.screen_step = _Heard(), None
    app.ride.over = TIME_UP
    app.update()
    assert app.mode is main.FRONT and app.front.step is front_model.TIMEUP

    def box():
        """The middle row of the box, where the words are drawn."""
        y = panel.BOX_Y + panel.BOX_H * 8 // 2
        return tuple(pyxel_headless.screen.pget(panel.BOX_X + x, y)
                     for x in range(panel.BOX_W * 8))

    drawn = set()
    for _ in range(2 * panel.BLINK):
        app.draw()
        pyxel.flip()
        drawn.add(box())
        app.update()
    assert len(drawn) == 2, "the words are there half the time and gone the other half"

    while app.front.step is front_model.TIMEUP:
        app.update()
    assert app.front.step is front_model.GAMEOVER
    app.draw()
    while app.front.step is front_model.GAMEOVER:
        app.update()
    assert app.front.step is front_model.SPLASH, \
        "and the original comes out of it at the screen it opens on"
    from game.rom import mixer as sound
    assert app.screens.asked == [main.SILENCE, sound.GAMEOVER_MUSIC], \
        "one tune across both waits, asked for as the first of them goes up"


def test_finishing_a_course_offers_the_time_to_the_board(pyxel_headless, tmp_path):

    from game.engine.run import FINISHED

    app = _cartridge_app(pyxel_headless, tmp_path)
    _ride(app)
    app.ride.elapsed = 4321
    app.ride.over = FINISHED
    app.update()
    assert app.front.best == pytest.approx(43.21)


def test_select_picks_solo_or_vs_computer_and_the_race_has_the_computers_bike(
        pyxel_headless, tmp_path):
    """Space is the Game Boy's Select, which on the original's title walks the
    three ways to play -- and the middle one is the computer's bike.

    The bike arrives when the choice is **settled**, not while the cursor is
    still on the row: the original writes its mode word then, and that word is
    what the race is built from.
    """
    import pyxel

    app = _cartridge_app(pyxel_headless, tmp_path)
    _press(app, pyxel.KEY_RETURN)                 # past the opening screen
    assert not app.front.rival, "solo is where the cursor starts"
    _press(app, pyxel.KEY_SPACE)
    from game.front import MODES

    assert MODES[app.front.mode] == "VS COMPUTER", "Select walks the three ways to play"
    app.draw()
    _ride(app)
    assert app.ride.rival is not None
    app.draw()


def test_without_a_cartridge_the_band_is_the_panel_drawn_from_nothing(pyxel_headless):
    """Why this test: without a cartridge the band was a line of text -- a
    clock, a lap -- where the original has a panel; now it is the panel's own
    things drawn from nothing. What is held here is that it answers the race:
    faster fills more of the speedometer, and fewer nitros are fewer canisters.
    """
    import pyxel

    from game.course import Course, Tileset
    from game.engine.run import Run
    from game.render import ride_draw
    from game.render import rom_art
    from maps import read

    tiles = Tileset({"floor": {"dir": 0}}, {"road": ["sky", "sky", "floor", "floor"]})
    run = Run(Course(tiles, {"road": [["road"]]}, read.tables(),
                     stampings=[(15, c, "road") for c in range(256)]))
    rom_art.install_cartridge(None)

    def band():
        ride_draw.draw_band(run, paused=False)
        return [pyxel.pget(x, y) for y in range(ride_draw.VIEW_H, pyxel.height)
                for x in range(pyxel.width)]

    still = band()
    run.bike.magnitude = 60
    assert band() != still, "the speedometer did not move with the speed"
    fast = band()
    run.bike.speed.nitros -= 1
    assert band() != fast, "a nitro spent took no canister away"


def test_enter_on_an_empty_drafts_tab_rides_nothing(app, tmp_path):
    """The drafts' tab is there with nothing in it on every fresh clone, saying
    how to make one; Start on it must not try to build a course that is not
    there."""
    import pyxel

    import main
    from game.menu import Menu

    app.menu = Menu(COURSES, drafts=[], records={}, path=str(tmp_path / "r.json"))
    app.menu.move_section(1)
    assert app.menu.label == "custom" and not app.menu.tracks
    _press(app, pyxel.KEY_RETURN)
    assert app.mode is main.MENU and app.ride is None
    app.draw()


def test_with_a_cartridge_the_title_has_the_fourth_row_too(pyxel_headless, tmp_path):
    """Why this test: a player with a cartridge could not reach their own drafts
    or the excessive mode at all -- the fourth row was for runs without one.
    It is written onto the cartridge's own title, and it opens FREE RIDE."""
    import pyxel

    import main
    from game import front as front_model

    app = _cartridge_app(pyxel_headless, tmp_path)
    assert front_model.MORE in app.front.rows
    _press(app, pyxel.KEY_RETURN)                 # past the opening screen
    for _ in range(len(front_model.MODES)):
        _press(app, pyxel.KEY_DOWN)
    app.draw()
    _press(app, pyxel.KEY_RETURN)
    assert app.mode is main.MENU
