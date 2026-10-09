"""A whole screen of the original's: the interpreter that paints one, and the
results screen it paints after a race.

No cartridge ships with the repository, so the programs here are written into a
cartridge-shaped file. What these check is the rules -- where the interpreter's
cursor goes, what erasing a screen does, which columns the time's digits land
in. That the screens are the original's tile for tile is checked against the
running game, where a cartridge exists.
"""

import pytest

from game.rom import screen as screen_module
from game.rom.cartridge import SIZE, Cartridge
from game.rom.screen import (
    BLANK,
    CARD,
    COURSE_CURSORS,
    CURSOR_SEED,
    COURSE_AT,
    COURSE_DIGIT,
    DIGITS,
    END,
    GAMEOVER,
    LEVEL_AT,
    LEVELS,
    LEVEL_CURSORS,
    MAP,
    MINUTE,
    MODE_SPRITE,
    MODE_Y,
    NEXT,
    NO_TIME,
    NUMBERS_AT,
    NUMBER_DIGIT,
    QUALIFYING_AT,
    RECORD,
    RECORD_AT,
    RESULTS,
    RESULTS_RIVAL,
    SELECT,
    SELECT_CHOSEN,
    RUN,
    SPRITE_X,
    SPRITE_Y,
    STOP,
    VS_COMPUTER,
    RIVAL_TIME_AT,
    SCREEN_H,
    SCREEN_W,
    TIME_AT,
    WIDE,
    card,
    clock,
    gameover,
    cursor,
    paint,
    paint_runs,
    results,
    screen,
    select,
)


def _cartridge(*programs):
    """A cartridge holding each `(address, bytes)` program where it says."""
    raw = bytearray(SIZE)
    for at, body in programs:
        raw[at:at + len(body)] = bytes(body)
    return Cartridge(bytes(raw), check=False)


def _program(at, *tiles):
    return [at & 0xFF, at >> 8] + list(tiles) + [END]


# -- the interpreter --------------------------------------------------------------


def test_a_program_writes_its_tiles_where_its_address_says():
    at = MAP + 3
    tiles = paint(_cartridge((0x4000, _program(at, 0xAA, 0xBB))), 0x4000)
    assert tiles == {at: 0xAA, at + 1: 0xBB}


def test_a_program_can_move_to_another_address_and_carry_on():
    """`NEXT` is how one program paints a banner and the words under it."""
    first, second = MAP + 3, MAP + WIDE
    body = [first & 0xFF, first >> 8, 0xAA,
            NEXT, second & 0xFF, second >> 8, 0xBB, END]
    tiles = paint(_cartridge((0x4000, body)), 0x4000)
    assert tiles == {first: 0xAA, second: 0xBB}


def test_the_cursor_wraps_at_the_end_of_its_row():
    """Why this test: the cursor walks a row of a map thirty-two wide and comes
    back to that row's start; it does **not** run into the row below. A cursor
    that ran on would fill the next row with the tail of this one, and a screen
    would still look nearly right -- which is the kind of wrong that goes
    unnoticed until somebody reads a word that is not there.
    """
    at = MAP + WIDE - 2
    tiles = paint(_cartridge((0x4000, _program(at, 0xAA, 0xBB, 0xCC))), 0x4000)
    assert tiles == {at: 0xAA, at + 1: 0xBB, MAP: 0xCC}


def test_a_program_run_the_other_way_erases_what_it_wrote():
    """Why this test: the original takes a screen away with **the program that
    drew it**, writing the blank tile instead of each tile. So the two have to
    touch exactly the same places, which is only true while one function does
    both.
    """
    body = _program(MAP + 3, 0xAA, 0xBB)
    cartridge = _cartridge((0x4000, body))
    drawn = paint(cartridge, 0x4000)
    erased = paint(cartridge, 0x4000, draw=False)
    assert erased.keys() == drawn.keys()
    assert set(erased.values()) == {BLANK}


def test_a_program_that_never_ends_is_given_up_on():
    """A cartridge-shaped file of zeroes is not a program, and reading one for
    ever is not how this should say so."""
    assert paint(_cartridge(), 0x4000) is not None


# -- the results ------------------------------------------------------------------


@pytest.mark.parametrize("elapsed, digits", [
    (0, "00000"),
    (2 * MINUTE + 23 * 100 + 26, "22326"),
    (9 * MINUTE + 59 * 100 + 99, "95999"),
    (MINUTE - 1, "05999"),
])
def test_the_time_is_five_digits_of_the_cartridges_own(elapsed, digits):
    """A minute, two of seconds and two of hundredths -- and no colons, because
    the screen's program has painted those already."""
    assert clock(elapsed) == [DIGITS + int(digit) for digit in digits]


def test_the_time_steps_over_the_colons_that_are_painted_already():
    """Why this test: the digits are written into a row that already has its two
    colons in it, so they go 0, skip, 2, 3, skip, 5, 6 -- and a run of five in a
    row would write over both colons and read as five digits and nothing else.
    """
    cartridge = _cartridge((RESULTS, _program(TIME_AT, 0x01)))
    tiles = results(cartridge, 2 * MINUTE + 23 * 100 + 26)
    written = [tiles.get(TIME_AT + column) for column in range(7)]
    assert written == [DIGITS + 2, None, DIGITS + 2, DIGITS + 3,
                       None, DIGITS + 2, DIGITS + 6]


def test_the_computers_line_is_only_run_when_there_was_a_computer():
    """Its words are a program of their own, under the player's."""
    cartridge = _cartridge((RESULTS, _program(TIME_AT, 0x01)),
                           (RESULTS_RIVAL, _program(RIVAL_TIME_AT - 3, 0xC0)),
                           (NO_TIME, [0xDD, END]))
    alone = results(cartridge, 100)
    assert RIVAL_TIME_AT - 3 not in alone and RIVAL_TIME_AT not in alone
    together = results(cartridge, 100, rival=200, computer=True)
    assert together[RIVAL_TIME_AT - 3] == 0xC0
    assert together[RIVAL_TIME_AT] == DIGITS + 0


def test_a_computer_that_did_not_finish_gets_a_word_where_its_time_would_be():
    """Why this test: that is how a race against it usually ends -- the player
    crosses the line and the other bike is still riding -- so the line is drawn
    either way and only what is on it changes. A results screen that wrote a
    time anyway would be a time nobody rode.
    """
    cartridge = _cartridge((RESULTS, _program(TIME_AT, 0x01)),
                           (RESULTS_RIVAL, _program(RIVAL_TIME_AT - 3, 0xC0)),
                           (NO_TIME, [0xDD, 0xEE, END]))
    tiles = results(cartridge, 100, computer=True)
    assert tiles[RIVAL_TIME_AT - 3] == 0xC0, "the line is there"
    assert RIVAL_TIME_AT not in tiles, "and no digit on it"
    assert [tiles[RIVAL_TIME_AT + 1], tiles[RIVAL_TIME_AT + 2]] == [0xDD, 0xEE]


def test_the_record_line_goes_up_only_when_the_record_fell():
    """Why this test: the line and the tune that goes with it are the same
    answer, and it is an answer about the race just ridden rather than about the
    screen -- so the screen has to be able to be painted both ways from the same
    cartridge. A results screen that always said the record fell would be the
    screen lying about the only thing on it that is not a time.
    """
    cartridge = _cartridge((RESULTS, _program(TIME_AT - 1, 0xB0)),
                           (RECORD, _program(TIME_AT + 0x60, 0xC1, 0xC2)))
    ordinary = results(cartridge, 100)
    assert TIME_AT + 0x60 not in ordinary
    beaten = results(cartridge, 100, record=True)
    assert [beaten[TIME_AT + 0x60], beaten[TIME_AT + 0x61]] == [0xC1, 0xC2]
    assert beaten[TIME_AT - 1] == 0xB0, "and the screen under it is the same screen"


# -- the run-length painter, and the title --------------------------------------


def test_a_count_with_the_top_bit_clear_is_one_tile_that_many_times():
    """The plain run, and most of a picture: sky, or a row of the same thing."""
    at = MAP + 2
    body = [at & 0xFF, at >> 8, 0x03, 0xAA, STOP]
    tiles = paint_runs(_cartridge((0x4000, body)), 0x4000)
    assert tiles == {at: 0xAA, at + 1: 0xAA, at + 2: 0xAA}


def test_a_count_with_the_top_bit_set_is_that_many_tiles_each_its_own():
    at = MAP
    body = [at & 0xFF, at >> 8, RUN | 0x02, 0xAA, 0xBB, STOP]
    tiles = paint_runs(_cartridge((0x4000, body)), 0x4000)
    assert tiles == {at: 0xAA, at + 1: 0xBB}


def test_the_run_on_its_own_walks_the_tile_up_as_it_goes():
    """Why this test: a drawing whose tiles are numbered in order is kept as a
    tile and a count, which is how the original fits a whole logo in a handful
    of bytes -- read as anything else it is one tile repeated, which would be a
    logo drawn as a smear.
    """
    at = MAP + 4
    body = [at & 0xFF, at >> 8, RUN, 0x40, 0x03, STOP]
    tiles = paint_runs(_cartridge((0x4000, body)), 0x4000)
    assert tiles == {at: 0x40, at + 1: 0x41, at + 2: 0x42}


def test_the_run_length_cursor_runs_on_into_the_row_below():
    """Why this test: **the two painters differ here and nowhere else that
    shows**. `paint` comes back to the start of its own row; this one carries
    straight on, which is what a drawing across the whole screen needs. Either
    rule in the other's place draws something that looks nearly right.
    """
    at = MAP + WIDE - 1
    body = [at & 0xFF, at >> 8, 0x02, 0xAA, STOP]
    tiles = paint_runs(_cartridge((0x4000, body)), 0x4000)
    assert tiles == {at: 0xAA, at + 1: 0xAA}


def test_the_cursor_on_the_title_is_a_sprites_own_tile():
    """It is not a tile of the background's at all, which is why it is drawn on
    its own: a sprite counts from `$8000` and the background cannot name that."""
    cartridge = _cartridge((MODE_SPRITE, [0x28, 0x00, 0x00]))
    assert screen_module.mode_cursor(cartridge, VS_COMPUTER) == \
        [(0x28 - SPRITE_X, MODE_Y[VS_COMPUTER] - SPRITE_Y, 0x00)]


# -- choosing a course and a level ------------------------------------------------


def _selecting(course_x=(0x18, 0x28, 0x38), level_x=(0x40, 0x58, 0x70)):
    """A cartridge with the two screens and the tables the cursors read."""
    return _cartridge(
        (SELECT, _program(MAP, 0xAA)),
        (SELECT_CHOSEN, _program(NUMBERS_AT, BLANK, BLANK, BLANK)),
        (CURSOR_SEED, [0x48, course_x[0], 0xD3, 0x00, 0x88, level_x[0], 0xD3, 0x00]),
        (COURSE_CURSORS, list(course_x)),
        (LEVEL_CURSORS, list(level_x)),
    )


def test_choosing_the_course_takes_the_other_numbers_away_and_writes_that_one_back():
    """Why this test: the screen is one screen and two steps, and the step is
    told by what is on it -- the original blanks the whole row of numbers and
    puts the chosen one back where it stood. A screen that kept all eight would
    say nothing about what had been chosen, and one that blanked the row without
    writing the number back would lose it.
    """
    cartridge = _selecting()
    picking = select(cartridge, 2)
    assert picking.get(NUMBERS_AT) == BLANK or NUMBERS_AT not in picking
    chosen = select(cartridge, 2, picking_course=False)
    # The second course's cursor is at $28, which is column (0x28 - 8) / 8 = 4.
    assert chosen[NUMBERS_AT + 4] == NUMBER_DIGIT | 2
    assert chosen[NUMBERS_AT] == BLANK


def test_the_course_cursor_goes_when_the_course_is_chosen_and_the_levels_stays():
    """Both are on the screen while the course is being chosen; only the level's
    is left afterwards, which is how the screen says which row is in hand."""
    cartridge = _selecting()
    both = cursor(cartridge, 3, 0)
    assert len(both) == 2
    assert (0x38 - SPRITE_X, 0x48 - SPRITE_Y, 0xD3) in both
    after = cursor(cartridge, 3, 2, picking_course=False)
    assert after == [(0x70 - SPRITE_X, 0x88 - SPRITE_Y, 0xD3)]


# -- the card --------------------------------------------------------------------


def test_the_card_names_the_course_and_the_level_in_its_box():
    """The course is a digit of an alphabet of its own -- `$A0` and the number --
    and the level's letter sits in the tile beside it, so `COURSE 3B` is the
    card's own program plus two tiles."""
    tiles = card(_cartridge((CARD, _program(COURSE_AT - 1, 0xAA))), 3, 1, 100, 200)
    assert tiles[COURSE_AT] == COURSE_DIGIT | 3
    assert tiles[LEVEL_AT] == LEVELS[1]


def test_the_cards_two_times_go_in_their_own_rows():
    """Why this test: the record and the time to qualify are written by the same
    routine into two rows of one program, and a card with them the other way
    round -- or in each other's row -- is a card that reads perfectly and lies.
    """
    tiles = card(_cartridge((CARD, _program(COURSE_AT - 1, 0xAA))),
                 1, 0, 2 * MINUTE + 200, 45 * 100)
    assert tiles[RECORD_AT] == DIGITS + 2            # 2:02:00, the record
    assert tiles[QUALIFYING_AT] == DIGITS + 0        # 0:45:00, the time to qualify
    assert tiles[QUALIFYING_AT + 2] == DIGITS + 4


# -- the end of a race the clock ran out on --------------------------------------


def test_game_over_is_its_own_program_and_carries_nothing_of_the_race():
    """Why this test: every other screen between races has something written
    into it -- a course, a level, a time -- and this one has nothing at all. If
    it ever grows a number, it grew one by accident.
    """
    at = MAP + WIDE * 7 + 6
    tiles = gameover(_cartridge((GAMEOVER, _program(at, 0xAA, 0xBB))))
    assert tiles == {at: 0xAA, at + 1: 0xBB}


# -- a screen on the screen -------------------------------------------------------


def test_a_screen_is_twenty_by_eighteen_and_blank_where_nothing_was_painted():
    """The map is thirty-two wide and the window shows twenty of it, so a tile
    painted past the twentieth column is in the map and not on the screen."""
    inside, outside = MAP + 5, MAP + SCREEN_W + 1
    tiles = paint(_cartridge((0x4000, _program(inside, 0xAA))), 0x4000)
    tiles[outside] = 0xBB
    laid = screen(tiles)
    assert len(laid) == SCREEN_W * SCREEN_H
    assert (40, 0, 0xAA) in laid
    assert not [cell for cell in laid if cell[2] == 0xBB]
    assert {cell[2] for cell in laid} == {BLANK, 0xAA}


def test_free_ride_is_written_under_the_three_in_the_cartridges_letters():
    """This game's fourth row on the cartridge's title: the nine tiles of
    FREE RIDE a row under VS 2-PLAYER and in its column, and the cursor a row
    further down at the original's own pitch."""
    from game.rom.screen import FREE_RIDE, FREE_RIDE_AT, FREE_RIDE_LETTERS, free_ride

    tiles = free_ride({})
    assert sorted(tiles) == list(range(FREE_RIDE_AT, FREE_RIDE_AT + len(FREE_RIDE)))
    assert [tiles[FREE_RIDE_AT + n] for n in range(len(FREE_RIDE))] == \
        [FREE_RIDE_LETTERS[letter] for letter in FREE_RIDE]
    assert tiles[FREE_RIDE_AT + 4] == BLANK, "the space is the blank tile"
    cartridge = _cartridge((MODE_SPRITE, [0x28, 0x00, 0x00]))
    fourth = screen_module.mode_cursor(cartridge, len(MODE_Y))[0][1]
    third = screen_module.mode_cursor(cartridge, len(MODE_Y) - 1)[0][1]
    assert fourth - third == MODE_Y[1] - MODE_Y[0]


def test_with_four_rows_the_ways_to_play_go_up_half_a_tile():
    """Why this test: written a row under the three, FREE RIDE sat on the
    bottom edge. The four go up half a tile together -- the words above them do
    not move -- and the cursor with them."""
    from game.rom.screen import FOUR_ROWS_LIFT, MODES_ROW, four_rows_cursor, lifted

    cells = [(0, (MODES_ROW - 1) * 8, 1), (0, MODES_ROW * 8, 2), (0, (MODES_ROW + 3) * 8, 3)]
    assert lifted(cells) == [(0, (MODES_ROW - 1) * 8, 1), (0, MODES_ROW * 8 - FOUR_ROWS_LIFT, 2),
                             (0, (MODES_ROW + 3) * 8 - FOUR_ROWS_LIFT, 3)]
    cartridge = _cartridge((MODE_SPRITE, [0x28, 0x00, 0x00]))
    assert four_rows_cursor(cartridge, 0)[0][1] == \
        screen_module.mode_cursor(cartridge, 0)[0][1] - FOUR_ROWS_LIFT
