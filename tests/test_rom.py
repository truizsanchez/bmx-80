"""The cartridge reader's rules, on cartridge-shaped files this test writes.

No cartridge ships with this repository, so none is read here. What is checked is
the reader's own logic -- how a course's pieces are stamped, how two that overlap
are merged, how an item lands, how a tile is looked up -- on files of the right
shape holding a few dozen bytes each, so every rule is one case a reader can see.

Whether the reader gives *the original's* courses, byte for byte, is checked
against the real cartridge where one exists; this is the part that can be checked
without one.
"""

import pytest

from game.engine.terrain import SKY, Hit
from game.rom import cartridge as cart
from game.rom.cartridge import (
    MINIS,
    OBJECT_PALETTES,
    POSE_COUNT,
    POSES,
    MINI_FALLBACK,
    COLLISION,
    QUALIFYING,
    RECORDS,
    SIZE,
    Cartridge,
    NotTheCartridge,
    identify,
)
from game.rom.course import (
    COLS,
    COURSES,
    EMPTY,
    FIRST_MADE,
    GOAL,
    GOAL_COL,
    GOAL_ROW,
    ITEMS,
    METATILES,
    MODE_T_IS_N,
    PIECES,
    ROWS,
    TRANSPARENT,
    Course,
)

# Where the test files keep their lists and pieces: anywhere the reader is not
# already looking.
LIST, ITEM_LIST, PIECE_DATA = 0x7000, 0x7100, 0x7200


def _cartridge(records, pieces, metatiles, items=(), collision=None):
    """A cartridge-shaped file with course 1 made of `records` and `pieces`.

    `records` is `(row, col, piece)`, `pieces` a list of row lists of metatile
    ids, `metatiles` `{id: four tile ids}`, `items` `(row, col, kind)`, and
    `collision` `{tile: byte}`. Everything else is zero.
    """
    data = bytearray(SIZE)

    def word(at, value):
        data[at], data[at + 1] = value & 0xFF, value >> 8

    word(COURSES, LIST)
    at = LIST
    for record in records:
        data[at:at + 3] = bytes(record)
        at += 3
    data[at] = EMPTY
    word(ITEMS, ITEM_LIST)
    at = ITEM_LIST
    for item in items:
        data[at:at + 3] = bytes(item)
        at += 3
    data[at] = EMPTY
    at = PIECE_DATA
    for index, rows in enumerate(pieces):
        word(PIECES + 2 * index, at)
        data[at], data[at + 1] = len(rows), len(rows[0])
        at += 2
        for row in rows:
            data[at:at + len(row)] = bytes(row)
            at += len(row)
    for metatile, tiles in metatiles.items():
        data[METATILES + 4 * metatile:METATILES + 4 * metatile + 4] = bytes(tiles)
    for tile, value in (collision or {}).items():
        data[COLLISION + tile] = value
    return Cartridge(bytes(data), check=False)


# Two metatiles that do not overlap anything: tile ids start above zero, because
# an unset entry in these files reads as four zeros.
GROUND, ROCK = 10, 11
TILES = {GROUND: (1, 2, 3, 4), ROCK: (5, TRANSPARENT, TRANSPARENT, 6)}


def test_a_piece_is_stamped_row_by_row_where_its_record_says():
    course = Course(_cartridge([(3, 7, 0)], [[[GROUND, ROCK, GROUND], [ROCK, GROUND, ROCK]]],
                               TILES), 1)
    assert [course.metatile(3, c) for c in range(7, 10)] == [GROUND, ROCK, GROUND]
    assert [course.metatile(4, c) for c in range(7, 10)] == [ROCK, GROUND, ROCK]
    assert course.metatile(2, 7) == EMPTY and course.metatile(3, 10) == EMPTY


def test_a_column_past_the_last_wraps_within_its_row():
    course = Course(_cartridge([(5, COLS - 1, 0)], [[[GROUND, ROCK]]], TILES), 1)
    assert course.metatile(5, COLS - 1) == GROUND
    assert course.metatile(5, 0) == ROCK
    assert course.metatile(6, 0) == EMPTY


def test_a_row_past_the_last_ends_the_piece():
    course = Course(_cartridge([(ROWS - 1, 0, 0)], [[[GROUND], [ROCK]]], TILES), 1)
    assert course.metatile(ROWS - 1, 0) == GROUND


def test_an_empty_id_in_a_piece_empties_the_cell():
    course = Course(_cartridge([(0, 0, 0), (0, 0, 1)], [[[GROUND]], [[EMPTY]]], TILES), 1)
    assert course.metatile(0, 0) == EMPTY


def test_two_pieces_on_one_cell_are_merged_tile_by_tile():
    """A rock over the ground keeps the ground where the rock is transparent. The
    merge is new, so it is made -- as the first id past the cartridge's -- and a
    second identical merge reuses it rather than making another."""
    records = [(0, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1)]
    course = Course(_cartridge(records, [[[GROUND]], [[ROCK]]], TILES), 1)
    made = FIRST_MADE + 1
    assert course.metatile(0, 0) == course.metatile(0, 1) == made
    assert course.tiles(made) == (5, 2, 3, 6)
    assert course.counter == made


def test_a_merge_the_cartridge_already_has_is_not_made_again():
    tiles = dict(TILES)
    tiles[12] = (5, 2, 3, 6)
    course = Course(_cartridge([(0, 0, 0), (0, 0, 1)], [[[GROUND]], [[ROCK]]], tiles), 1)
    assert course.metatile(0, 0) == 12
    assert course.counter == FIRST_MADE


def test_items_are_stamped_as_their_kind_and_two_kinds_are_not():
    items = [(2, 2, 3), (2, 3, 6), (2, 4, 7)]
    course = Course(_cartridge([], [], TILES, items=items), 1)
    assert course.metatile(2, 2) == 3
    assert course.metatile(2, 3) == EMPTY and course.metatile(2, 4) == EMPTY


def test_the_sign_over_the_finish_goes_up_where_the_original_puts_it():
    """Why this test: the sign is the only thing the original changes about a
    course once a race is running, and it is written raw into two cells -- so
    the cells it lands in are the whole of it being right. It goes up on the
    last lap and not before, which is why the map has to be bare until `goal`
    is called.
    """
    course = Course(_cartridge([], [], TILES), 1)
    assert course.metatile(GOAL_ROW, GOAL_COL) == EMPTY
    assert course.metatile(GOAL_ROW, GOAL_COL + 1) == EMPTY
    course.goal()
    assert [course.metatile(GOAL_ROW, GOAL_COL + step) for step in range(len(GOAL))] \
        == list(GOAL)


def test_a_mini_maniac_has_a_tile_for_every_direction_and_a_mirror_bit():
    """Why this test: a mini-maniac is one tile, chosen by the pose the player
    was in, and the cartridge writes the mirror into the top bit of the same
    byte -- so reading the byte as a tile gives a tile no cartridge has. The
    poses past the thirty-two directions are the rider's own, and a
    mini-maniac has no picture for those: the original draws pose 4.
    """
    raw = bytearray(SIZE)
    raw[MINIS:MINIS + 32] = bytes(range(0x40, 0x50)) + bytes(range(0xC0, 0xD0))
    cartridge = Cartridge(bytes(raw), check=False)
    assert cartridge.mini(0) == (0x40, False)
    assert cartridge.mini(15) == (0x4F, False)
    assert cartridge.mini(16) == (0x40, True), "the top half of the circle is mirrored"
    assert cartridge.mini(31) == (0x4F, True)
    assert cartridge.mini(0x29) == cartridge.mini(MINI_FALLBACK), \
        "a pose of the rider's own falls back to one of the bike's"


def _posed(poses):
    """A cartridge whose table of poses points at `poses`, one list of raw
    bytes each, laid one after another where the reader is not looking."""
    raw = bytearray(SIZE)
    at = PIECE_DATA
    for attitude, data in enumerate(poses):
        raw[POSES + 2 * attitude:POSES + 2 * attitude + 2] = at.to_bytes(2, "little")
        raw[at:at + len(data)] = bytes(data)
        at += len(data)
    return Cartridge(bytes(raw), check=False)


def test_a_pose_is_a_count_of_slots_and_0x80_empties_one():
    """Why this test: a pose's slots are four bytes each **except** an emptied
    one, which is the single byte `$80` -- read as four, every slot after it
    comes out shifted and the rider is drawn in pieces. The offsets are signed:
    the flourishes put the rider's head eight pixels above the bike's top.
    """
    cartridge = _posed([
        [3, 0, 8, 1, 0x20, 0x80, 0xF8, 0, 0x80, 0x60],
        [1, 0, 0, 7, 0],
    ])
    assert cartridge.pose(0) == ((0, 8, 1, 0x20), None, (-8, 0, 0x80, 0x60))
    assert cartridge.pose(1) == ((0, 0, 7, 0),)


def test_an_attitude_past_the_table_is_drawn_as_the_level_bike():
    """The table has an entry for every attitude the engine sets and no more;
    past it are other bytes, which read as a pose would be a pointer anywhere."""
    cartridge = _posed([[1, 0, 0, 7, 0]])
    assert cartridge.pose(POSE_COUNT) == cartridge.pose(0)


def test_the_object_palettes_are_read_where_the_original_writes_them():
    raw = bytearray(SIZE)
    raw[OBJECT_PALETTES[0]], raw[OBJECT_PALETTES[1]] = 0xE4, 0xA8
    cartridge = Cartridge(bytes(raw), check=False)
    assert (cartridge.object_palette(False), cartridge.object_palette(True)) == (0xE4, 0xA8)


def test_a_mode_can_turn_the_t_crate_into_an_n():
    course = Course(_cartridge([], [], TILES, items=[(2, 2, 3)]), 1, mode=MODE_T_IS_N)
    assert course.metatile(2, 2) == 4


def test_a_tile_is_read_off_the_8_pixel_grid_and_the_lap_wraps():
    course = Course(_cartridge([(1, 0, 0)], [[[GROUND]]], TILES), 1)
    assert [course.tile(0, 2), course.tile(1, 2), course.tile(0, 3), course.tile(1, 3)] == \
        [1, 2, 3, 4]
    assert course.tile(2 * COLS, 2) == 1, "one lap on, the same tile"
    assert course.tile(0, 0) is None


def test_the_collision_byte_is_solid_soft_and_a_direction():
    collision = {1: 0x80 | 4, 2: 0x80 | 0x40, 3: 28, 4: 0x80 | 0x20}
    course = Course(_cartridge([(0, 0, 0)], [[[GROUND]]], TILES, collision=collision), 1)
    assert course.hit(0, 0) == Hit(True, False, False, 4)
    assert course.hit(1, 0) == Hit(True, True, False, 0)
    assert course.hit(0, 1) == Hit(False, False, False, 28)
    assert course.hit(1, 1) == Hit(True, False, True, 0)
    assert course.hit(4, 4) == SKY


def test_a_time_is_three_bytes_of_decimal_read_the_smallest_first():
    """Why this test: the qualifying time and the record are the same three
    bytes -- hundredths, seconds, minutes, each a pair of decimal digits in a
    byte -- and a byte read as plain binary gives a time that is wrong by a
    little and looks right: `$45` is forty-five seconds, not sixty-nine.
    """
    raw = bytearray(SIZE)
    raw[QUALIFYING[1] + 3:QUALIFYING[1] + 6] = bytes([0x00, 0x45, 0x01])
    raw[RECORDS + 3:RECORDS + 6] = bytes([0x99, 0x02, 0x02])
    cartridge = Cartridge(bytes(raw), check=False)
    assert cartridge.limit(2, 1) == (60 + 45) * 100
    assert cartridge.record(2) == (2 * 60 + 2) * 100 + 99


def test_only_eight_courses():
    with pytest.raises(ValueError):
        Course(_cartridge([], [], TILES), 9)


# -- which file it is ----------------------------------------------------------


def test_a_file_of_the_wrong_size_is_refused_saying_so():
    with pytest.raises(NotTheCartridge, match="bytes"):
        identify(bytes(100))


def test_another_game_is_refused_saying_so():
    with pytest.raises(NotTheCartridge, match="not Motocross Maniacs"):
        identify(bytes(SIZE))


def test_another_release_is_refused_saying_which_is_read():
    data = bytearray(SIZE)
    data[0x134:0x134 + len(cart.TITLE)] = cart.TITLE
    with pytest.raises(NotTheCartridge, match="European"):
        identify(bytes(data))
    with pytest.raises(NotTheCartridge):
        Cartridge(bytes(data))
