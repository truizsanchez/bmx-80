"""The original's tile art, read out of the cartridge the way the game loads it.

At race start the original fills video memory from a list of loads (`LOADS`), six
bytes each -- a destination tile, a method, a count and a source -- ending at a
zero destination. The methods are how one drawing becomes several:

- **copy** (0, and 5 and 7, which do the same): the tiles as stored, 2 bits a pixel;
- **inverted** (1): every byte complemented;
- **flipped top to bottom** (2), **left to right** (4), **both** (6): a tile's rows
  in reverse order, each row's bits in reverse order, or both;
- **expanded** (3): one bit a pixel, each plane chosen by three bits of the count --
  the low plane all ones, the source, or nothing; the high plane the source or
  nothing -- which is how one stored shape is drawn in any of the four shades.

`video(cartridge)` is the tile memory the lists leave, `$8000`-`$97FF`; a tile no
list loads is zero. `pixels(video, tile)` reads one of the background's tiles as
the course addresses it -- ids 0-127 from `$9000`, 128-255 from `$8800` -- as
sixty-four colour numbers, 0 the lightest and 3 the darkest.

**A sprite counts its tiles from `$8000` and the background does not**, so a
sprite's tile 128 to 255 is the background's id of the same number, and its 0 to
127 is nowhere in the background's range at all. The start's `3 2 1 GO!` is all
above 128, which is why it needs no reading of its own.
"""

from collections.abc import Iterator

from game.rom.cartridge import Cartridge

#: The three lists of loads a race is drawn out of, run in this order -- which
#: is the order the game runs them in on its way to one, and **all three are
#: still in tile memory when the race starts**: each writes over what it needs
#: and leaves the rest of the last one standing.
#:
#: The first is the game's own lettering -- its letters and its digits -- which
#: is how the start's `GO!` is on the screen without the race ever loading it.
#: The second is the title's, and the one tile of it a race does not write over
#: is a tile of scenery the course draws: a course drawn without it has a hole
#: in it. The third is the race's own. (`Call_000_12e9`, `Call_000_146b` and the
#: race's setup run them.)
LETTERING, TITLE, LOADS = 0x12EF, 0x1477, 0x3811
#: Tile memory: where it starts, and how big it is.
VIDEO, VIDEO_SIZE = 0x8000, 0x1800
TILE_BYTES = 16
#: A destination tile number is counted from here.
FIRST_TILE = 0x80
#: The methods, by number.
COPY, INVERTED, FLIPPED_V, EXPANDED, FLIPPED_H, FLIPPED_BOTH = 0, 1, 2, 3, 4, 6
#: Method 3's count carries its planes in three bits of its high byte.
LOW_ALL, HIGH_SOURCE, LOW_SOURCE = 0x40, 0x20, 0x10
#: The background's tiles: 0-127 at this offset, 128-255 at `SIGNED_HIGH`.
SIGNED_LOW, SIGNED_HIGH = 0x1000, 0x0800


def _reversed(byte: int) -> int:
    return int("{:08b}".format(byte)[::-1], 2)


def video(cartridge: Cartridge, *lists: int) -> bytearray:
    """The tile memory a list of loads leaves, or the three a race runs in order.

    A screen between races wants `LETTERING` on its own: the race's list writes
    over most of it, and the letters a screen is written in are what it leaves
    standing. The title wants that and its own.
    """
    data = cartridge.data
    out = bytearray(VIDEO_SIZE)
    for at in lists or (LETTERING, TITLE, LOADS):
        while data[at] or data[at + 1]:
            tile = (data[at + 1] & 1) << 8 | data[at]
            method = data[at + 1] >> 5
            count = cartridge.word(at + 2)
            source = cartridge.word(at + 4)
            _load(data, out, (tile - FIRST_TILE) * TILE_BYTES, method, count, source)
            at += 6
    return out


def _load(data: bytes, out: bytearray, dest: int, method: int, count: int,
          source: int) -> None:
    """One load, written into tile memory from `dest` -- and past its end, as
    the hardware would, nowhere."""
    for byte in _bytes(data, method, count, source):
        if 0 <= dest < VIDEO_SIZE:
            out[dest] = byte
        dest += 1


def _bytes(data: bytes, method: int, count: int, source: int) -> Iterator[int]:
    """What a load writes, a byte at a time, by its method."""
    if method == EXPANDED:
        return _expanded(data, count, source)
    if method in (FLIPPED_V, FLIPPED_BOTH):
        return _flipped(data, count, source, mirror=method == FLIPPED_BOTH)
    return (0xFF ^ byte if method == INVERTED
            else _reversed(byte) if method == FLIPPED_H else byte
            for byte in data[source:source + count * TILE_BYTES])


def _expanded(data: bytes, count: int, source: int) -> Iterator[int]:
    """A one-bit shape into a shade: each source byte becomes a row's two planes,
    each plane the byte, all ones, or nothing, as the flags say."""
    planes = (count * TILE_BYTES & 0xFFFF) >> 1
    flags, rows = planes >> 8, planes & 0x0FFF
    for i in range(rows):
        byte = data[source + i]
        yield 0xFF if flags & LOW_ALL else byte if flags & LOW_SOURCE else 0
        yield byte if flags & HIGH_SOURCE else 0


def _flipped(data: bytes, count: int, source: int, mirror: bool) -> Iterator[int]:
    """Tiles upside down, and mirrored as well when `mirror` says."""
    for tile in range(count):
        base = source + tile * TILE_BYTES
        for row in reversed(range(TILE_BYTES // 2)):
            for byte in data[base + 2 * row:base + 2 * row + 2]:
                yield _reversed(byte) if mirror else byte


#: The logo screen loads its drawing as a straight copy rather than through a
#: list -- so many bytes of the cartridge at an address, not a tile number --
#: and the cursor on the title is one tile copied the same way. (`Call_000_109c`
#: and `Call_000_0d48`.)
LOGO_ART, LOGO_AT, LOGO_BYTES = 0x10C8, 0x9400, 0x01D0
CURSOR_ART, CURSOR_AT = 0x0F72, 0x8000


def copy(cartridge: Cartridge, video: bytearray, source: int, at: int,
         count: int) -> None:
    """Bytes of the cartridge straight into tile memory, as the original does
    where it has no list to run."""
    start = at - VIDEO
    video[start:start + count] = cartridge.data[source:source + count]


def sprite_pixels(video: bytes | bytearray, tile: int) -> tuple[int, ...]:
    """A **sprite's** tile, which counts from `$8000` and so reaches the tiles no
    background id names at all: its 0 to 127 are nowhere in the background's
    range, and the cursor on the title is one of them."""
    return _read(video, tile * TILE_BYTES)


def pixels(video: bytes | bytearray, tile: int) -> tuple[int, ...]:
    """Background tile `tile` as sixty-four colour numbers, row by row."""
    return _read(video, (SIGNED_LOW + tile * TILE_BYTES) if tile < 128
                 else (SIGNED_HIGH + (tile - 128) * TILE_BYTES))


def _read(video: bytes | bytearray, at: int) -> tuple[int, ...]:
    """Sixty-four colour numbers out of one tile's sixteen bytes, row by row."""
    out: list[int] = []
    for row in range(8):
        low, high = video[at + 2 * row], video[at + 2 * row + 1]
        out.extend(((high >> (7 - x)) & 1) << 1 | ((low >> (7 - x)) & 1) for x in range(8))
    return tuple(out)
