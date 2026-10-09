"""The three levels, the screen you pick from, and the scoreboard.

    "Finally, use the Control Pad to choose a course (1-8) and skill level (eAsy,
    Bumpy or Crazy)."                                            (manual, p.2)

    "Each level has a different time limit."                     (manual, p.4)

    "The only difference between each level is that you start with less time."
"""

import json


from game.course import (
    BUMPY,
    CRAZY,
    DEFAULT_LEVEL,
    EASY,
    LEVEL_LETTERS,
    START_LEVEL,
)
from game.menu import Menu
from game import records


def _course(name):
    """A map that is a name and a factory: all the screen needs of one.

    What the factory builds is deliberately nothing in particular -- `Menu`
    never looks inside it, which is the point of `build` being a factory -- so
    a test here can ask about the screen without owning a map format.
    """
    return (name, lambda: object())


#: Three courses, named rather than read off the disk: a test here asks about the
#: screen, and a map is content.
TRACKS = [_course(name) for name in ("map1", "map2", "circuit1")]


# --- three clocks -------------------------------------------------------------

def test_a_limit_is_three_numbers_and_the_middle_one_is_the_reference():
    """Why this test is a stub, and what it is owed: a course declares one clock
    per level and the middle of the three is what a course is balanced around --
    `DEFAULT_LEVEL`, which has to stay `BUMPY` because moving it would re-time
    every course without touching a map.

    The half that made those numbers -- `as_limits`, and a `Course` that held
    them -- went with the map format it belonged to (`maps/__init__.py`). What
    survives is the two constants, and they are worth pinning on their own: they
    are read by the menu and by the scoreboard and neither has a format.
    """
    assert DEFAULT_LEVEL is BUMPY
    assert len(LEVEL_LETTERS) == 3


def test_the_reference_clock_and_the_opening_level_are_two_questions():
    """One constant answering both gets the second answer wrong.

    `DEFAULT_LEVEL` is what a course's bare `limit` means and what the editor
    types a limit against, so moving it re-balances every course in the repo
    without touching a map. Which level the menu *opens* on is a question about
    the screen and about no clock at all.
    """
    assert DEFAULT_LEVEL is BUMPY
    assert START_LEVEL is EASY
    assert START_LEVEL is not DEFAULT_LEVEL


# **How a course's three clocks are balanced is measured against a course.** The
# shape of it: a course running 80.7s on the throttle with nothing picked up and
# 66.0s equipped wants its hardest clock between the
# two, which is the walkthrough's own "at later levels, grabbing them is
# absolutely essential" stated as a number.


# --- the screen ---------------------------------------------------------------

def test_the_cursor_wraps_both_ways():
    menu = Menu(TRACKS, records={})
    assert menu.course == 0
    menu.move_course(-1)
    assert menu.course == len(menu.tracks) - 1
    menu.move_course(1)
    assert menu.course == 0
    assert menu.level == START_LEVEL
    menu.move_level(-1)
    assert menu.level == CRAZY, "the level did not wrap"
    menu.move_level(-1)
    assert menu.level == BUMPY


def test_a_menu_with_no_courses_does_not_move():
    menu = Menu([], records={})
    menu.move_course(1)
    assert menu.course == 0
    assert menu.name == ""


def test_what_it_builds_is_a_fresh_course_every_time():
    """A factory rather than a map, for the reason `maps.TRACKS` is one: only
    the map somebody chose is read, and it is read afresh each time."""
    menu = Menu(TRACKS, records={})
    first, second = menu.build(), menu.build()
    assert first is not second


def test_the_record_shown_is_the_one_for_the_level_in_hand():
    menu = Menu(TRACKS, records={"map2": {"A": {"t": 88.4}, "B": {"t": 71.3, "s": 300}}})
    menu.course = [name for name, _ in menu.tracks].index("map2")
    menu.level = EASY
    assert menu.best == 88.4
    assert menu.best_score == 0, "a level nobody has flipped on scores nought"
    menu.level = BUMPY
    assert menu.best == 71.3
    assert menu.best_score == 300
    menu.level = CRAZY
    assert menu.best is None
    assert menu.best_score == 0


# --- the scoreboard -----------------------------------------------------------

def test_a_record_is_keyed_by_course_and_level():
    kept = {}
    assert records.put(kept, "map2", BUMPY, 71.3)
    assert records.best(kept, "map2", BUMPY) == 71.3
    assert records.best(kept, "map2", EASY) is None
    assert kept == {"map2": {LEVEL_LETTERS[BUMPY]: {records.TIME: 71.3}}}


def test_only_a_better_time_sticks():
    kept = {}
    assert records.put(kept, "map2", BUMPY, 71.3)
    assert not records.put(kept, "map2", BUMPY, 80.0)
    assert records.put(kept, "map2", BUMPY, 70.1)
    assert records.best(kept, "map2", BUMPY) == 70.1


def test_a_first_time_is_always_a_record():
    assert records.beats({}, "map2", CRAZY, 999.0)


def test_a_record_is_written_to_a_tenth():
    assert records.clock(71.34) == "1:11.3"
    assert records.clock(125.0) == "2:05.0"
    assert records.clock(None) == "--:--"


def test_the_scoreboard_survives_a_round_trip(tmp_path):
    path = str(tmp_path / "records.json")
    kept = {}
    records.put(kept, "map2", CRAZY, 66.5)
    assert records.save(kept, path)
    assert records.load(path) == kept


def test_an_unreadable_scoreboard_is_an_empty_one(tmp_path):
    """It is a scoreboard: a corrupt file should cost the player their times and
    not the ability to start the game. Which is the opposite of a map, where
    half-loading is how you ride into a hole."""
    path = tmp_path / "records.json"
    path.write_text("{ this is not json")
    assert records.load(str(path)) == {}
    assert records.load(str(tmp_path / "nothing-here.json")) == {}

    path.write_text(json.dumps({"map2": {"Z": 1.0, "B": "soon"}, "x": 5}))
    assert records.load(str(path)) == {}

    # ...and a top level that is not an object at all, which is what half of a
    # written file looks like. The loop below `load`'s isinstance check would
    # otherwise walk a list and unpack its items as `course, times`.
    path.write_text("[]")
    assert records.load(str(path)) == {}


def test_a_scoreboard_that_cannot_be_written_costs_the_times_and_nothing_else(tmp_path):
    """`save` says whether it worked; it does not raise, and `finished` carries on.

    A read-only checkout -- or a game unpacked somewhere the player cannot write
    -- is a reason to lose the scoreboard and not a reason for the run that just
    crossed the line to end in a traceback. `records.save` is the only place that
    decides this and `Menu.finished` is the only caller, which asks for its
    return and then ignores it on purpose: the record still counts *this
    session*, it just will not outlive it.

    The path here is a directory, so `open(..., "w")` raises `IsADirectoryError`
    -- an `OSError`, which is the class the code names.
    """
    kept = {}
    records.put(kept, "map2", CRAZY, 66.5)
    assert records.save(kept, str(tmp_path)) is False

    menu = Menu(TRACKS, records={}, path=str(tmp_path))
    assert menu.finished(72.0) is True, "the run still beat something"
    assert records.best(menu.records, menu.name, menu.level) == 72.0


def test_the_two_axes_are_beaten_separately():
    """A time and a score are two races over the same ground: the fast line takes
    no jump it does not have to, and points are only earned in the air. Keeping
    the score of the fastest run would leave the trick column reading whatever
    the quick way round happened to pass through."""
    kept = {}
    assert records.put(kept, "map2", BUMPY, 71.3, 100)
    assert records.put(kept, "map2", BUMPY, 80.0, 900), "slower, but it flew"
    assert records.best(kept, "map2", BUMPY) == 71.3
    assert records.best_score(kept, "map2", BUMPY) == 900
    assert records.put(kept, "map2", BUMPY, 70.0, 0), "faster, and it took no jump"
    assert records.best(kept, "map2", BUMPY) == 70.0
    assert records.best_score(kept, "map2", BUMPY) == 900
    assert not records.put(kept, "map2", BUMPY, 99.0, 50)


def test_a_course_nobody_has_flipped_on_scores_nought():
    """Not `None`, unlike the time, and the difference is real: a course nobody
    has finished has no time at all, and one nobody has done a trick on has a
    score."""
    assert records.best_score({}, "map2", BUMPY) == 0
    assert records.best({}, "map2", BUMPY) is None


def test_a_scoreboard_of_bare_times_is_read_as_times(tmp_path):
    """What a file written before there were points looks like. Same argument as
    the rest of `load`: what is understood is kept, so a player who has a file of
    times keeps them and starts the score column at nought."""
    path = tmp_path / "records.json"
    path.write_text(json.dumps({"map2": {"B": 71.3}}))
    kept = records.load(str(path))
    assert records.best(kept, "map2", BUMPY) == 71.3
    assert records.best_score(kept, "map2", BUMPY) == 0


def test_half_a_record_is_half_a_record(tmp_path):
    """A field that is not a number is dropped and the rest of the entry stands.
    Losing the whole scoreboard over one bad value would be the map rule applied
    to a file that is not a map."""
    path = tmp_path / "records.json"
    path.write_text(json.dumps({"map2": {"B": {"t": 71.3, "s": "lots"}}}))
    kept = records.load(str(path))
    assert records.best(kept, "map2", BUMPY) == 71.3
    assert records.best_score(kept, "map2", BUMPY) == 0


def test_finishing_writes_only_when_it_beat_something(tmp_path):
    path = str(tmp_path / "records.json")
    menu = Menu(TRACKS, records={}, path=path)
    assert menu.finished(72.0) is True
    assert records.load(path) == {
        menu.name: {LEVEL_LETTERS[START_LEVEL]: {records.TIME: 72.0}}
    }
    assert menu.finished(75.0) is False
    assert menu.finished(70.0) is True
    kept = records.load(path)[menu.name][LEVEL_LETTERS[START_LEVEL]]
    assert kept[records.TIME] == 70.0

    # And the score is the other half of the same offer: a slower run that flew
    # better takes the score column and leaves the clock where it was.
    assert menu.finished(75.0, 300) is True
    kept = records.load(path)[menu.name][LEVEL_LETTERS[START_LEVEL]]
    assert kept == {records.TIME: 70.0, records.SCORE: 300}


# --- the lists and the window -------------------------------------------------

def _named(*names):
    """A section's worth of tracks, where only the names matter."""
    return [(name, lambda: None) for name in names]


def test_the_tabs_are_the_eight_and_the_drafts():
    """The line between the courses and the author's own, drawn on the screen:
    as one run there is nothing saying where one ends.

    Given its own lists rather than the disk's. Reading `maps.DRAFTS` here
    makes the test a claim about **this checkout** -- green where the author has
    drafts, red on every clone, since `maps/drafts/` is gitignored.

    **The drafts' tab is there with nothing in it**, because it is also where
    the screen says how to make one; only no drafts at all -- `--ride` -- has no
    tab. There is no enhanced tab: the enhanced vocabulary has nothing to ride.
    """
    from game.menu import COURSES, CUSTOM

    courses = [("dunes", None), ("course2", None)]
    drafts = [("half-drawn", None)]
    menu = Menu(courses, drafts=drafts, records={})
    assert [label for label, _ in menu.sections] == [COURSES, CUSTOM]
    assert menu.sections[0][1] == courses
    assert menu.sections[1][1] == drafts
    assert [label for label, _ in Menu(courses, drafts=[], records={}).sections] \
        == [COURSES, CUSTOM], "an empty drafts tab is still a tab"
    assert len(Menu(courses, records={}).sections) == 1, "and no drafts at all is none"


def test_the_sections_are_walked_round_however_many_there_are():
    """`move_section` is a modulo, so one tab is a no-op, two toggle and three
    come back round.

    Written as a walk rather than three asserts because what is being pinned is
    that the *count* is the only thing that decides: adding a fourth directory
    one day should need nothing here.
    """
    menu = Menu(_named("a"), drafts=_named("x"), records={})
    seen = []
    for _ in range(len(menu.sections)):
        seen.append(menu.label)
        menu.move_section(1)
    assert seen == ["courses", "custom"]
    assert menu.tab == 0, "walking every tab did not come back to the first"

    menu.move_section(-1)
    assert menu.label == "custom", "backwards off the first tab is the last"


def test_a_menu_with_no_drafts_has_no_second_tab():
    """Which is every clone but the author's: `maps/drafts/` is gitignored.

    A tab that opened onto nothing would be the screen offering a place the
    player cannot reach and cannot fill from here, so there is no tab -- and
    `move_section` is where that is decided, so the picture never has to ask.
    """
    menu = Menu(_named("a", "b"), records={})
    assert len(menu.sections) == 1
    menu.move_section(1)
    assert menu.tab == 0 and menu.label == "courses"


def test_each_tab_keeps_its_own_cursor():
    """`cursors` is a list per section: wandering into the other list and back
    does not lose your place in this one."""
    menu = Menu(_named("a", "b", "c"), drafts=_named("p", "q"), records={})
    menu.move_course(2)
    menu.move_section(1)
    assert menu.course == 0 and menu.name == "p"
    menu.move_course(1)
    menu.move_section(1)
    assert menu.course == 2 and menu.name == "c", "the first tab lost its place"
    menu.move_section(1)
    assert menu.name == "q", "the second tab lost its place"


def test_the_window_follows_the_cursor_and_moves_as_little_as_it_can():
    """A window centred on the cursor would slide the whole list under a cursor
    that is not moving, so the offset is state and not a formula."""
    from game.menu import WINDOW

    menu = Menu(_named(*["c%d" % n for n in range(9)]), records={})
    assert menu.top == 0 and not menu.more_above and menu.more_below

    for _ in range(WINDOW - 1):
        menu.move_course(1)
    assert menu.top == 0, "the window moved before the cursor reached its edge"

    menu.move_course(1)
    assert menu.top == 1
    assert [name for _, name in menu.visible] == ["c%d" % n for n in range(1, WINDOW + 1)]

    menu.move_course(-1)
    assert menu.top == 1, "the window followed a cursor that was still inside it"

    menu.move_course(-(WINDOW - 1))
    assert menu.course == 0 and menu.top == 0

    menu.move_course(-1)  # wraps to the last course
    assert menu.course == 8
    assert menu.top == 9 - WINDOW
    assert menu.more_above and not menu.more_below


def test_a_list_shorter_than_the_window_never_scrolls():
    menu = Menu(_named("a", "b"), records={})
    menu.move_course(-1)
    assert menu.top == 0
    assert not menu.more_above and not menu.more_below
    assert [name for _, name in menu.visible] == ["a", "b"]


def test_the_menu_opens_on_the_easiest_level():
    """The author's, and it is a question about the screen: `DEFAULT_LEVEL` goes
    on being the middle clock every course is balanced against."""
    menu = Menu(TRACKS, records={})
    assert menu.level == EASY
    assert START_LEVEL is EASY and DEFAULT_LEVEL is not START_LEVEL


def test_one_pair_of_arrows_and_three_things_to_choose_with_it():
    """`move` is the whole of what the window knows: which of the three it
    lands on -- the course, the level, the mode -- is the model's, so
    `main._update_menu` never has to say."""
    from game.menu import PICKING_COURSE, PICKING_LEVEL, PICKING_MODE

    menu = Menu(_named("a", "b", "c"), records={})
    assert menu.focus is PICKING_COURSE

    menu.move(1)
    assert menu.course == 1 and menu.level == EASY

    menu.move_focus()
    assert menu.focus is PICKING_LEVEL
    menu.move(1)
    assert menu.level == BUMPY
    assert menu.course == 1, "the arrows moved the list they were not on"

    menu.move_focus()
    assert menu.focus is PICKING_MODE
    menu.move(1)
    assert menu.mode == "excessive" and menu.level == BUMPY
    assert menu.play.steps == 60, "the mode chosen is the rate the race steps at"

    menu.move_focus()
    assert menu.focus is PICKING_COURSE
    menu.move(-1)
    assert menu.course == 0 and menu.level == BUMPY


def test_all_four_arrows_are_handed_over_and_not_half_of_them():
    """A course is a list with another list across from it; a level is a row of
    three walked either way. So `move_across` is the level's, not the list's, the
    moment the level is in hand -- which it was not for one revision, leaving the
    one horizontal thing on the screen with no horizontal key."""
    from game.menu import PICKING_LEVEL

    menu = Menu(_named("a", "b"), drafts=_named("x"), records={})
    menu.move_across(1)
    assert menu.label == "custom", "left and right are the lists on the course"
    menu.move_across(-1)
    assert menu.label == "courses"

    menu.move_focus()
    assert menu.focus is PICKING_LEVEL
    menu.move_across(1)
    assert menu.level == BUMPY
    assert menu.label == "courses", "the arrows still moved the list"
    menu.move_across(-1)
    assert menu.level == EASY

    # Up and down walk it too. A dead key on a screen this small is a key the
    # player has to be told about.
    menu.move(1)
    assert menu.level == BUMPY
