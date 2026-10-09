"""The cartridge's tile art: each way the original loads a tile, on a file this
test writes.

No cartridge ships with the repository, so the loads are checked one at a time on
a cartridge-shaped file holding one list entry and one tile. That the loads give
the original's tiles byte for byte is checked against the running game, where a
cartridge exists.
"""

import pytest

from game.rom.cartridge import SIZE, Cartridge
from game.rom.graphics import (
    COPY,
    EXPANDED,
    FIRST_TILE,
    FLIPPED_BOTH,
    FLIPPED_H,
    FLIPPED_V,
    INVERTED,
    LETTERING,
    LOADS,
    TITLE,
    SIGNED_LOW,
    pixels,
    video,
)

SOURCE = 0x7000
#: A tile whose rows are all different, and whose bytes are not symmetric.
TILE = bytes([0x80, 0x01, 0x40, 0x02, 0x20, 0x04, 0x10, 0x08,
              0x08, 0x10, 0x04, 0x20, 0x02, 0x40, 0x01, 0x80])


def _entry(dest, method, count, source):
    return bytes([dest & 0xFF, (dest >> 8) | method << 5,
                  count & 0xFF, count >> 8, source & 0xFF, source >> 8])


def _loaded(method, count=1, data=TILE):
    raw = bytearray(SIZE)
    dest = FIRST_TILE  # tile memory's first tile
    raw[LOADS:LOADS + 6] = bytes([dest & 0xFF, (dest >> 8) | method << 5,
                                  count & 0xFF, count >> 8, SOURCE & 0xFF, SOURCE >> 8])
    raw[SOURCE:SOURCE + len(data)] = data
    return video(Cartridge(bytes(raw), check=False))[:16]


def _reverse(byte):
    return int("{:08b}".format(byte)[::-1], 2)


def test_a_copy_is_the_tile_as_stored():
    assert _loaded(COPY) == TILE


def test_inverted_is_every_byte_complemented():
    assert _loaded(INVERTED) == bytes(0xFF ^ b for b in TILE)


def test_flipped_top_to_bottom_reverses_the_rows():
    rows = [TILE[i:i + 2] for i in range(0, 16, 2)]
    assert _loaded(FLIPPED_V) == b"".join(reversed(rows))


def test_flipped_left_to_right_reverses_each_row():
    assert _loaded(FLIPPED_H) == bytes(_reverse(b) for b in TILE)


def test_flipped_both_ways_is_both():
    rows = [TILE[i:i + 2] for i in range(0, 16, 2)]
    assert _loaded(FLIPPED_BOTH) == bytes(_reverse(b) for b in b"".join(reversed(rows)))


@pytest.mark.parametrize("flags, low, high", [
    (0x0E, lambda b: 0xFF, lambda b: b),     # low plane all ones, high the source
    (0x06, lambda b: b, lambda b: b),        # both planes the source
    (0x04, lambda b: 0, lambda b: b),        # only the high plane
])
def test_expanded_is_one_bit_a_pixel_into_the_planes_the_count_names(flags, low, high):
    """Method 3 keeps a shape at one bit a pixel and draws it in any shade: three
    bits of the count's high byte say what each plane gets."""
    shape = TILE[:8]
    got = _loaded(EXPANDED, count=flags << 8 | 1, data=shape)
    assert got == bytes(v for b in shape for v in (low(b), high(b)))


def test_a_tile_reads_as_colour_numbers_from_the_signed_half():
    """Background tile 0 is at `$9000`: two planes to a row, the high bit the
    darker."""
    memory = bytearray(0x1800)
    memory[SIGNED_LOW:SIGNED_LOW + 2] = bytes([0b10100000, 0b11000000])
    row = pixels(memory, 0)[:8]
    assert row == (3, 2, 1, 0, 0, 0, 0, 0)


def test_three_lists_are_run_and_the_races_is_the_last():
    """Why this test: **a race is drawn out of everything still in tile memory
    when it starts**, and three lists have run by then -- the lettering, the
    title's, and the race's own. Each writes over what it needs and leaves the
    rest of the last one standing.

    Reading only the race's list left twenty-two tiles blank, the digits among
    them; reading it with the lettering left one, a tile of scenery the course
    draws, and a course drawn without it has a hole in it. That one comes from
    the title's list, which the game runs on its way to every race.

    The order is the whole of it: a tile two lists name has to end up the
    later one's.
    """
    raw = bytearray(SIZE)
    other, third = bytes(range(0x10, 0x20)), bytes(range(0x20, 0x30))
    raw[LETTERING:LETTERING + 12] = (_entry(FIRST_TILE, COPY, 1, SOURCE)
                                     + _entry(FIRST_TILE + 1, COPY, 1, SOURCE + 16))
    raw[TITLE:TITLE + 12] = (_entry(FIRST_TILE + 1, COPY, 1, SOURCE + 32)
                             + _entry(FIRST_TILE + 2, COPY, 1, SOURCE + 32))
    raw[LOADS:LOADS + 6] = _entry(FIRST_TILE + 1, COPY, 1, SOURCE)
    raw[SOURCE:SOURCE + 16] = TILE
    raw[SOURCE + 16:SOURCE + 32] = other
    raw[SOURCE + 32:SOURCE + 48] = third
    memory = video(Cartridge(bytes(raw), check=False))
    assert memory[:16] == TILE, "the lettering's tile, which nothing wrote over"
    assert memory[16:32] == TILE, "the one all three name ends up the race's"
    assert memory[32:48] == third, "and the title's own is still standing"
    assert other not in bytes(memory), "the lettering's second tile is gone"
