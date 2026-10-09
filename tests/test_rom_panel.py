"""The original's panel, composed from a race: what each piece reads.

No cartridge ships with the repository, so the tables the panel is read from are
written here, in a cartridge-shaped file, with bytes that say which entry they
are. What these check is the rules -- which entry a magnitude picks, where the
cursor of the cartridge's own label painter goes, how many levels of a tile a
second is worth. That the panel is the original's tile for tile is checked
against the running game, where a cartridge exists.
"""

import pytest

from game.engine.original import J, MINI
from game.engine.original import BEEPS_AT, COUNTDOWN, GO_AT
from game.rom.cartridge import SIZE, Cartridge
from game.rom.screen import END, NEXT
from game.rom.panel import (
    BARRIER,
    BARS,
    SECRETS,
    DIGITS,
    BLINK,
    BOX,
    BOX_H,
    BOX_W,
    BOX_X,
    BOX_Y,
    GO,
    MARKER,
    BLANK,
    CANISTER,
    EMPTY,
    FAST,
    FULL,
    GROUND,
    JET,
    LABELS,
    LEVELS,
    LONGEST,
    MARK,
    NEEDLE,
    NEEDLE_BOTTOM,
    NEEDLE_LOW,
    NEEDLE_TOP,
    NITROS,
    NO_MARK,
    PANEL,
    RIDER_JET,
    RIDER_TIRE,
    ROW,
    SLOW,
    SPEED_BAR,
    START_BLANK,
    START_STEP,
    START_X,
    START_Y,
    TIME_BAR,
    TIRE,
    WIDE,
    _held,
    _nitros,
    _painted,
    _speed,
    _time,
    barrier,
    marker,
    secret,
    start,
    timeup,
)

#: The tables' entries, marked so a test can say which one was read: the slow
#: table's entries count 0x10, 0x11..., the fast one's 0x20, 0x21...
SLOW_MARK, FAST_MARK, MARK_MARK, NO_MARK_MARK = 0x10, 0x20, 0x30, 0x40


def _cartridge(program=()):
    """A cartridge with the panel's tables in it, and the label painter's
    program if a test gives one."""
    raw = bytearray(SIZE)
    # The tables sit end to end in the cartridge and these are their real sizes:
    # nine entries of six for the slow bar, four for the fast, five of two for
    # the mark. Laid out any bigger they would write over one another, which is
    # the whole reason the clamps in `_speed` are where they are.
    for entry in range(9):
        raw[SLOW + entry * 6:SLOW + entry * 6 + 6] = bytes([SLOW_MARK + entry] * 6)
    for entry in range(4):
        raw[FAST + entry * 6:FAST + entry * 6 + 6] = bytes([FAST_MARK + entry] * 6)
    for entry in range(5):
        raw[MARK + entry * 2:MARK + entry * 2 + 2] = bytes([MARK_MARK + entry] * 2)
    raw[NO_MARK:NO_MARK + 2] = bytes([NO_MARK_MARK] * 2)
    raw[LABELS:LABELS + len(program)] = bytes(program)
    return Cartridge(bytes(raw), check=False)


def _blank():
    return [GROUND] * (2 * WIDE)


# -- the labels the cartridge paints --------------------------------------------------


def test_the_labels_are_painted_by_the_cartridges_own_program():
    """The panel starts as one tile everywhere and the cartridge paints over it:
    an address, then tiles, `NEXT` for another address and `END` at the end."""
    at = PANEL + 3
    tiles = _painted(_cartridge([at & 0xFF, at >> 8, 0xAA, 0xBB,
                                 NEXT, (PANEL + WIDE) & 0xFF, (PANEL + WIDE) >> 8, 0xCC,
                                 END]))
    assert tiles[3:5] == [0xAA, 0xBB], "two tiles where the address said"
    assert tiles[WIDE] == 0xCC, "and one where the second address said"
    assert tiles[0] == tiles[2] == tiles[5] == GROUND, "the rest is the ground"


# -- the speedometer ------------------------------------------------------------------


@pytest.mark.parametrize("magnitude, top, bottom", [
    (0, 0, 0), (1, 0, 1), (3, 0, 1), (4, 0, 2), (7, 0, 2),
    (8, 1, 2), (11, 1, 2), (12, 2, 2), (144, 2, 2)])
def test_the_needle_has_three_steps_each_way(magnitude, top, bottom):
    """Five thresholds over two tiles, and they are not the same thresholds: the
    top moves at 8 and 12, the bottom at 1 and 4."""
    tiles = _blank()
    _speed(_cartridge(), tiles, magnitude, 0x4F)
    assert tiles[NEEDLE] == NEEDLE_TOP[top]
    assert tiles[NEEDLE_LOW] == NEEDLE_BOTTOM[bottom]


@pytest.mark.parametrize("magnitude, entry", [
    (0, SLOW_MARK), (0x0C, SLOW_MARK), (0x0F, SLOW_MARK),
    (0x10, SLOW_MARK + 1), (0x14, SLOW_MARK + 2), (0x2C, SLOW_MARK + 8),
    (0x2F, SLOW_MARK + 8), (0x30, FAST_MARK), (0x38, FAST_MARK + 1),
    (0x48, FAST_MARK + 3), (0x4F, FAST_MARK + 3), (144, FAST_MARK + 3)])
def test_the_bar_is_read_from_the_cartridges_two_tables(magnitude, entry):
    """Why this test: **the two tables are stepped differently** -- the slow one
    every four magnitudes and the fast one every eight -- and both are six tiles
    an entry, so an index that is out by a factor reads plausible tiles from the
    wrong place, or off the end of the table into whatever follows it.
    """
    tiles = _blank()
    _speed(_cartridge(), tiles, magnitude, 0x4F)
    assert tiles[SPEED_BAR:SPEED_BAR + 6] == [entry] * 6


@pytest.mark.parametrize("cap, magnitude, marked", [
    (0x4F, 0, [NO_MARK_MARK, NO_MARK_MARK]),
    (0x4F, 144, [NO_MARK_MARK, NO_MARK_MARK]),
    (0x50, 0, [MARK_MARK, GROUND]),
    (0x50, 0x70, [MARK_MARK + 4, GROUND]),
    (0x50, 144, [MARK_MARK + 4, GROUND]),
    (0x5F, 0x58, [MARK_MARK + 1, GROUND]),
    (0x60, 0x58, [MARK_MARK + 1] * 2)])
def test_the_cap_puts_the_speedometer_further_out(cap, magnitude, marked):
    """An S crate lengthens the bar: with none the two tiles are nothing, with
    one there is a tile more of it and with two there are two."""
    tiles = _blank()
    _speed(_cartridge(), tiles, magnitude, cap)
    assert tiles[SPEED_BAR + 6:SPEED_BAR + 8] == marked


# -- the rest -------------------------------------------------------------------------


@pytest.mark.parametrize("left, full, part", [
    (0, 0, 0), (100, 0, 1), (799, 0, 7), (800, 1, 0),
    (LONGEST * 100, LONGEST // LEVELS, LONGEST % LEVELS),
    (60000, LONGEST // LEVELS, LONGEST % LEVELS)])
def test_the_time_is_a_bar_of_seconds_and_not_a_clock(left, full, part):
    """Eight levels to a tile, one a second, and **capped**: the original reads
    only the seconds of its clock and gives up above fifty-five, so a race that
    starts with minutes on it starts with the bar full and standing still.
    """
    tiles = _blank()
    _time(tiles, left)
    assert tiles[TIME_BAR:TIME_BAR + BARS] == \
        [FULL] * full + [EMPTY + part] + [EMPTY] * (BARS - full - 1)


def test_tire_and_jet_show_only_while_they_are_held():
    tiles = _blank()
    _held(tiles, RIDER_TIRE, 4, TIRE)
    _held(tiles, RIDER_JET, 3, None)
    assert tiles[RIDER_TIRE:RIDER_TIRE + 4] == [TIRE, TIRE + 1, TIRE + 2, TIRE + 3]
    assert tiles[RIDER_JET:RIDER_JET + 3] == [BLANK] * 3
    _held(tiles, RIDER_TIRE, 4, None)
    _held(tiles, RIDER_JET, 3, JET)
    assert tiles[RIDER_TIRE:RIDER_TIRE + 4] == [BLANK] * 4
    assert tiles[RIDER_JET:RIDER_JET + 3] == [JET, JET + 1, JET + 2]


@pytest.mark.parametrize("nitros, shown", [(0, 0), (4, 4), (8, 8), (9, 8), (99, 8)])
def test_a_canister_a_nitro_up_to_eight(nitros, shown):
    """The row has room for eight and the race can hand out more."""
    tiles = _blank()
    _nitros(tiles, nitros)
    assert tiles[NITROS:NITROS + BARS] == [CANISTER] * shown + [BLANK] * (BARS - shown)


def test_the_time_bars_last_tile_is_off_the_screen():
    """The map is thirty-two tiles wide and the screen shows twenty of them. The
    bar is written eight tiles long into a row that has seven left, so the last
    of it is past the edge -- which is the original's own arithmetic, and the
    reason `_time` must not be shortened to fit.
    """
    assert TIME_BAR + BARS == ROW + 1
    tiles = _blank()
    _time(tiles, 0)
    assert len(tiles[TIME_BAR:TIME_BAR + BARS]) == BARS, "all eight are written"


# -- the start ------------------------------------------------------------------------


def test_the_start_shows_three_two_one_and_then_go():
    """Three sprites in the middle of the view, eight pixels apart: nothing at
    first, then a digit between two blanks, then `GO!` across all three."""
    assert [t for _, _, t in start(COUNTDOWN)] == [START_BLANK] * 3
    assert [t for _, _, t in start(BEEPS_AT[0])] == [START_BLANK, DIGITS + 3, START_BLANK]
    assert [t for _, _, t in start(BEEPS_AT[1])] == [START_BLANK, DIGITS + 2, START_BLANK]
    assert [t for _, _, t in start(BEEPS_AT[2])] == [START_BLANK, DIGITS + 1, START_BLANK]
    assert [t for _, _, t in start(GO_AT)] == list(GO)
    assert start(0) == [], "and nothing once the race is going"
    assert [(x, y) for x, y, _ in start(GO_AT)] == \
        [(START_X + step * START_STEP, START_Y) for step in range(3)]


def test_the_start_changes_on_the_iterations_the_countdown_beeps_on():
    """Why this test: the digit and the tone are one thing in the original -- it
    counts `$C910` and both read it -- so a start that changed on a clock of its
    own would drift away from the sound, a frame at a time, and nothing would
    say so. `BEEPS_AT` and `GO_AT` are that clock, and this is what holds them
    to it: the picture changes on those iterations and no others.
    """
    changes = [n for n in range(COUNTDOWN, -1, -1) if start(n) != start(n + 1)]
    assert changes == list(BEEPS_AT) + [GO_AT, 0], \
        "the three beeps, the go, and the iteration the race starts on"


def test_the_start_says_in_words_what_its_sprites_show():
    """Why this test: a course with no cartridge writes the start rather than
    drawing three sprites out of one, and a word worked out apart from the
    sprites could change on an iteration they do not. Walked over the whole
    countdown, the word is the digit the sprites carry, or `GO!`, or nothing."""
    from game.rom.panel import start_word

    for countdown in range(COUNTDOWN + 1):
        tiles = [t for _, _, t in start(countdown)]
        digit = [t - DIGITS for t in tiles if DIGITS < t <= DIGITS + 9]
        expected = ("GO!" if tiles == list(GO) else str(digit[0]) if digit else "")
        assert start_word(countdown) == expected, countdown


def test_the_barrier_falls_on_the_last_two_iterations_of_the_countdown():
    """Why this test: the barrier is on the screen for the whole countdown and
    moves on two of its forty-eight iterations, so a picture of it is almost
    always the standing one -- which is exactly how a barrier that never fell
    would look right in a screenshot and wrong in the hand. What is pinned is
    which iterations it moves on, and that it stays down afterwards.
    """
    at = (0, 0)
    assert [t for _, _, t in barrier(COUNTDOWN, *at)] == [BARRIER[0]]
    assert [t for _, _, t in barrier(2, *at)] == [BARRIER[0]], "standing until the last"
    assert [t for _, _, t in barrier(1, *at)] == [BARRIER[1]]
    assert [t for _, _, t in barrier(0, *at)] == [BARRIER[2]], "flat when the bike is let go"
    changes = [n for n in range(COUNTDOWN, -1, -1) if barrier(n, *at) != barrier(n + 1, *at)]
    assert changes == [1, 0], "and it moves on those two iterations and no others"


def test_the_barrier_goes_when_the_course_has_carried_it_off_the_screen():
    """Why this test: it is the one thing on the view anchored to the course
    rather than to the screen, so it is the one thing that can be drawn at a
    negative x -- and the original drops it there rather than letting it wrap."""
    assert barrier(0, 0, 100) != []
    assert barrier(0, -1, 100) == []


def test_a_secret_taken_leaves_four_tiles_of_its_own():
    """Why this test: the J and the mini-maniacs are not in the map and are only
    taken upside down, so this flourish is **the only thing on the screen that
    says one was there at all** -- take it away and the jet arrives out of a
    clear sky, which is exactly how it looked before this. Each has its own four
    tiles, and a crate has none: a crate you can see.
    """
    at = secret(J, 100, 50)
    assert [t for _, _, t in at] == list(SECRETS[J])
    assert [(x, y) for x, y, _ in at] == [(100, 50), (108, 50), (100, 58), (108, 58)], \
        "two by two, in the reading order"
    assert [t for _, _, t in secret(MINI, 0, 0)] == list(SECRETS[MINI])
    assert secret(2, 100, 50) == [], "a crate leaves nothing: it was on the map"
    assert secret(J, -1, 50) == [], "and it goes once the course has carried it off"


def test_the_marker_stands_over_the_bike_and_points_at_it():
    """The block and its point, centred on the bike's sixteen pixels and clear
    above them -- so the pin touches the bike's top and does not cover it."""
    bike_x, bike_y, bike = 100, 80, 16
    at = marker(bike_x, bike_y)
    assert [t for _, _, t in at] == list(MARKER)
    assert [(x, y) for x, y, _ in at] == [(104, 64), (104, 72)]
    left, top = at[0][0], at[0][1]
    assert left - bike_x == bike - (left + START_STEP - bike_x), "centred on the bike"
    assert top + 2 * START_STEP == bike_y, "and its point ends where the bike begins"


# -- the clock running out ------------------------------------------------------------


def test_the_time_up_box_is_nine_tiles_by_three_with_the_words_inside():
    """The box is filled with one tile and the words sit in its middle row, a
    tile in from each side -- so the four of TIME, a gap, and the two of UP come
    to seven in a box of nine."""
    blank = timeup(BLINK)
    assert len(blank) == BOX_W * BOX_H and {t for _, _, t in blank} == {BOX}
    assert min(x for x, _, _ in blank) == BOX_X
    assert max(x for x, _, _ in blank) + START_STEP == BOX_X + BOX_W * START_STEP
    assert min(y for _, y, _ in blank) == BOX_Y
    assert max(y for _, y, _ in blank) + START_STEP == BOX_Y + BOX_H * START_STEP

    shown = timeup(0)
    words = shown[len(blank):]
    assert len(words) == BOX_W - 2, "a tile of the box left either side of them"
    assert {y for _, y, _ in words} == {BOX_Y + START_STEP}, "the middle row"
    assert min(x for x, _, _ in words) == BOX_X + START_STEP


def test_the_words_blink_on_the_races_own_counter():
    """Why this test: they blink at the rate the race runs at and not at the
    window's, because the original counts its own iterations and flips a bit of
    that. Eight iterations on and eight off, which at the race's rate is about a
    fifth of a second each.
    """
    on = [n for n in range(64) if len(timeup(n)) > BOX_W * BOX_H]
    assert on == [n for n in range(64) if not n & BLINK]
    assert on[:9] == list(range(8)) + [16], "eight on, eight off, and on again"
