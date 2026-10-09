"""The original's front end as a model: which screen is up and what it chose.

The window is not here and neither is a cartridge. What these pin is the shape
of the thing a player walks through -- one screen with two steps on it, a card
that is a wait, and a way back round to the start -- because that shape is what
`main.App` reads to decide what to draw and when a race begins.

The scoreboard half is here too: a race started from these screens has to reach
the same board the menu writes, and the record on the card is read back out of
it.
"""

from game import records as scoreboard
from game.front import (
    CARD,
    CARD_HOLD,
    GAMEOVER,
    GAMEOVER_HOLD,
    SPLASH,
    SPLASH_HOLD,
    COURSE,
    LEVEL,
    MODES,
    NO_RACE,
    SECOND_BIKE,
    SETUP,
    RACE,
    RESULTS,
    TIMEUP,
    TIMEUP_HOLD,
    TITLE,
    VS_COMPUTER,
    VS_TWO,
    Front,
)


def _front(courses=8, records=None, path="/dev/null"):
    """A front end over `courses` courses that build nothing: nothing here rides."""
    return Front([("course %d" % n, lambda: None) for n in range(1, courses + 1)],
                 records={} if records is None else records, path=path)


def _titled(front):
    """Past the screen the game opens on, which Start gets past."""
    front.confirm()
    return front


def _chosen(front):
    """...and past the title, where everything but those two tests starts."""
    _titled(front).confirm()
    return front


def test_it_opens_on_a_screen_of_its_own_that_start_gets_past():
    """Why this test: it is the one screen a press moves on -- the card holds
    for its whole length whatever is pressed -- and it ends by itself as well,
    so both ways out have to work or the game opens and stays there."""
    front = _front()
    assert front.step is SPLASH and front.held == SPLASH_HOLD
    front.confirm()
    assert front.step is TITLE
    waited = _front()
    assert not any(waited.tick() for _ in range(SPLASH_HOLD))
    assert waited.step is TITLE, "and it gives way on its own as well"


def test_the_title_is_next_solo_with_the_first_course_in_hand():
    front = _titled(_front())
    assert front.step is TITLE and front.mode == 0 and not front.rival
    assert front.course == 1 and front.level == 0


def test_the_title_walks_three_ways_to_play_and_the_middle_one_is_the_computer():
    """The cursor walks; **settling is what puts a bike beside you**, because
    the mode word is written then and it is the word the race is built from."""
    front = _titled(_front())
    front.move(1)
    assert MODES[front.mode] == "VS COMPUTER"
    assert not front.rival, "nothing is settled while the cursor is still walking"
    front.confirm()
    assert front.rival
    assert front.mode_word == SETUP | SECOND_BIKE


def test_two_players_asks_for_the_cable_and_nobody_answers():  # noqa: D202
    """Why this test: the third way to play is not a dead end in the original --
    it settles the choice, writes the mode word with the link bit in it, sends a
    byte down the cable and, getting its own back, puts the word to nothing and
    goes **back to the screen the game opens on**. Measured there with no cable:
    the mode word 0 and 263 frames of that screen before the title comes round.
    So the thing to pin is the whole of it, and not just that the race does not
    start -- a race that started solo from here would say it was one thing and
    be another, and a title that simply refused would be a screen the original
    does not have.
    """
    front = _titled(_front())
    front.move(-1)
    assert front.mode == VS_TWO
    front.confirm()
    assert front.step is SPLASH and front.held == SPLASH_HOLD
    assert front.mode_word == NO_RACE, "and no race was left set up behind it"
    assert not front.rival
    # ...and from there the game walks round as it always does.
    for _ in range(SPLASH_HOLD):
        front.tick()
    assert front.step is TITLE
    front.move(1)
    front.confirm()
    assert front.step is COURSE


def test_the_course_is_chosen_after_the_title():
    front = _chosen(_front())
    assert front.step is COURSE and front.course == 1


def test_the_cursor_wraps_at_either_end_of_whichever_row_is_in_hand():
    """Why this test: the original wraps -- eight goes round to one and C round
    to A -- and a cursor that stopped at the end instead would be a course you
    reach by pressing left seven times or not at all.
    """
    front = _chosen(_front())
    front.move(-1)
    assert front.course == 8
    front.move(1)
    assert front.course == 1
    front.confirm()
    front.move(-1)
    assert front.level == 2, "and the level's row wraps too, the other way round"
    assert front.course == 1, "which is the row in hand, and the other is settled"


def test_confirm_walks_the_screens_and_the_card_is_the_last_of_them():
    front = _chosen(_front())
    front.confirm()
    assert front.step is LEVEL
    front.confirm()
    assert front.step is CARD and front.held == CARD_HOLD


def test_the_mode_is_a_word_of_bits_and_it_goes_out_with_the_race():
    """Why this test: every screen after the title reads the word rather than
    the cursor, and the original clears it when a race is done -- leaving the
    results, and at the end of a race the clock ran out on. A word left standing
    would be the next screen describing a race nobody is riding.
    """
    front = _titled(_front())
    front.confirm()
    assert front.mode_word == SETUP, "solo: a race, and no second bike"
    front.over()
    front.confirm()
    assert front.mode_word == NO_RACE
    front = _chosen(_front())
    front.ran_out()
    assert front.mode_word == NO_RACE, "a clock that ran out ends the race too"


def test_the_card_is_a_wait_and_the_race_starts_when_it_is_over():
    """Why this test: the card is the only screen that ends by itself, and it is
    what holds the race back -- a card that never ran down would be a race that
    never starts, and one that ran down at once would be the two numbers on it
    gone before they were read.
    """
    front = _chosen(_front())
    front.confirm()
    front.confirm()
    started = [front.tick() for _ in range(CARD_HOLD)]
    assert started[-1] and not any(started[:-1])
    assert front.step is RACE
    assert not front.tick(), "and it is over once, not every frame after it"


def test_the_results_go_back_round_to_the_course():
    """The original starts again where it started: another course, another race."""
    front = _front()
    front.over()
    assert front.step is RESULTS
    front.confirm()
    assert front.step is COURSE


def test_the_record_belongs_to_one_race_and_not_to_the_screen():
    """Why this test: the record flag decides a line on the results and which of
    two tunes plays, and both have to be about **the race just ridden**. A flag
    that outlived its race would put a record on the next screen for a time
    nobody rode -- so the thing this checks is that it goes out, which is what
    the original does before it composes the screen at all.
    """
    front = _chosen(_front())
    assert not front.record_set
    front.over(True)
    assert front.step is RESULTS and front.record_set
    # ...round again: the results, a course, a level, and the card the next race
    # starts behind.
    for _ in range(3):
        front.confirm()
    assert front.step is CARD
    assert not front.record_set, "a new race starts with no record behind it"
    front.over()
    assert not front.record_set, "and an ordinary finish claims none"


def test_a_clock_that_ran_out_walks_the_two_waits_back_to_the_start():
    """Why this test: the original makes the end of a race it stopped one thing
    -- the box over the race, then `GAME OVER` -- and comes out of it at the
    screen it opens on and not at the course. Before this the app had nowhere to
    go at all and sat in the race for ever, so what is pinned here is that each
    wait is its own length and that the last of them lands on the splash.
    """
    front = _chosen(_front())
    front.ran_out()
    assert front.step is TIMEUP and front.held == TIMEUP_HOLD
    for _ in range(TIMEUP_HOLD - 1):
        assert not front.tick() and front.step is TIMEUP
    assert not front.tick()
    assert front.step is GAMEOVER and front.held == GAMEOVER_HOLD
    for _ in range(GAMEOVER_HOLD - 1):
        assert not front.tick() and front.step is GAMEOVER
    assert not front.tick(), "and none of the four waits is the one that races"
    assert front.step is SPLASH and front.held == SPLASH_HOLD


def test_a_clock_that_ran_out_is_offered_to_nothing(tmp_path):
    """Why this test: `finished` is the only door to the board and the rule it
    states is that only a finish goes through it. The two waits are the one
    place that rule could be broken quietly, so it is asserted where they are.
    """
    records = {}
    front = _chosen(_front(records=records, path=str(tmp_path / "records.json")))
    front.ran_out()
    for _ in range(TIMEUP_HOLD + GAMEOVER_HOLD):
        front.tick()
    assert records == {}
    assert not (tmp_path / "records.json").exists()


def test_a_finished_race_reaches_the_board_under_the_courses_own_name(tmp_path):
    """Why this test: the board is shared with the menu and keyed by name and
    level, so a race started from these screens has to offer the same two -- a
    time filed under the wrong name is a record nobody can beat.
    """
    records = {}
    front = _chosen(_front(records=records, path=str(tmp_path / "records.json")))
    front.move(2)
    front.confirm()
    front.move(1)
    assert front.name == "course 3" and front.level == 1
    assert front.finished(43.21)
    assert scoreboard.best(records, "course 3", 1) == 43.21
    assert front.best == 43.21 and front.record == 4321


def test_a_course_nobody_has_ridden_has_no_record():
    """Which the original cannot have -- it ships a table of times and shows one
    of those -- so the screens have to have an answer for a board with nothing
    on it."""
    assert _front().record is None


def test_the_computers_bike_is_carried_from_the_title_into_the_race():
    """What the title chose is what the race is: the model carries it, and
    nothing between the two asks again."""
    front = _titled(_front())
    front.move(VS_COMPUTER)
    front.confirm()
    front.confirm()
    front.confirm()
    assert front.step is CARD and front.rival
