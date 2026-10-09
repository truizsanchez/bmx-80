"""A course of the original, built from the cartridge the way the game builds it.

At race start the original fills a map once and reads it for the rest of the race:

- **The map** is 16 rows by 256 columns of **metatiles**, 16x16 px each -- 4096 px,
  which is one lap: a race is two laps of the same map. `EMPTY` is sky.
- **A metatile** is four tile ids, 2x2. Ids below `FIRST_MADE` are in the
  cartridge; from `FIRST_MADE` up they are made while the map is built.
- **A course** is a list of prefab pieces, `(row, col, piece)`, stamped in order.
  A piece is `rows, cols` and then its metatile ids, row by row. A column past the
  last wraps within its row; a row past the last ends the piece.
- **The items** are a second list, `(row, col, kind)`, stamped as metatile id
  `kind`: 2 is the S crate, 3 the T, 4 the N, 5 the R. Kinds 6 (J) and 7
  (mini-maniac) are not in the map. In a mode with `MODE_T_IS_N` set, a T is
  stamped as an N.
- **Stamping** a value on a cell: an empty cell takes it, `EMPTY` empties the
  cell, and otherwise the two metatiles are merged tile by tile -- `TRANSPARENT`
  in the new one keeps the old tile -- and the merge is looked up among the
  cartridge's metatiles, then among those already made, and made if it is new.

**The lookup reads past its own table**, and this reproduces that. The made
metatiles live in a block the original fills with `FILL` for `MADE_BYTES` bytes,
which ends exactly where the map begins, and the lookup walks as many entries as
its counter's value -- so it reads on into the map. Memory is modelled here as
that one block, so the walk reads what the original reads.
"""

from game.engine.terrain import SKY, Hit, Probed, Tiles
from game.rom.cartridge import Cartridge

# Where the cartridge keeps a course.
COURSES = 0x4771
PIECES = 0x56DD
ITEMS = 0x5F0C
METATILES = 0x5A30
TELEPORTS = 0x60FB

ROWS, COLS = 16, 256
#: A metatile is this many pixels square, and this many tiles.
METATILE_PX, METATILE_TILES = 16, 2
#: The map's width in pixels: one lap.
LAP_PX = COLS * METATILE_PX
COUNT = 8

EMPTY = 0xFF
TRANSPARENT = 0x7F
FIRST_MADE = 0xA8
FILL = 0x42
MADE_BYTES = 0x160
#: Bit of the mode byte that stamps a T crate as an N.
MODE_T_IS_N = 0x04
T_CRATE, N_CRATE = 3, 4
UNSTAMPED = (6, 7)
#: The tile a rock is drawn with.
ROCK = 0xEF

#: The sign over the finish, and the cell its left half goes in. The original
#: writes these two metatiles into the map when the player starts the last lap
#: -- they are the only thing it changes about a course once a race is running.
#: The cell is empty on every one of the eight courses and **neither metatile
#: has any collision**, so the sign is scenery and cannot be ridden into.
GOAL_ROW, GOAL_COL = 13, 249
GOAL = (0, 1)

_MAP_AT = MADE_BYTES
_BLOCK = MADE_BYTES + ROWS * COLS


class Course:
    """One course's map, built from a cartridge."""

    def __init__(self, cartridge: Cartridge, course: int, mode: int = 0) -> None:
        if not 1 <= course <= COUNT:
            raise ValueError("the courses are 1 to %d, not %d" % (COUNT, course))
        self.cartridge = cartridge
        self.number = course
        self.mode = mode
        self._ram = bytearray([FILL]) * MADE_BYTES + bytearray([EMPTY]) * (ROWS * COLS)
        #: The last metatile id made.
        self.counter = FIRST_MADE
        self._stamp_pieces(cartridge.word(COURSES + 2 * (course - 1)))
        self._stamp_items(cartridge.word(ITEMS + 2 * (course - 1)))

    # -- what the engine reads ---------------------------------------------------

    def metatile(self, row: int, col: int) -> int:
        """The metatile id at a cell of the map, as the original reads it.

        Row 16 is row 0 again. Row -1 is the 256 bytes before the map, which are
        the end of the block the made metatiles live in -- the window around a
        bike on the top row reads them, so this does too.
        """
        return self._ram[_MAP_AT + (row % ROWS if row >= 0 else -1) * COLS + col % COLS]

    def tiles(self, metatile: int) -> Tiles:
        """Metatile `metatile` as tile ids: top left, top right, bottom left, bottom right."""
        if metatile < FIRST_MADE:
            at = METATILES + 4 * metatile
            data = self.cartridge.data
            return (data[at], data[at + 1], data[at + 2], data[at + 3])
        at = 4 * (metatile - FIRST_MADE)
        ram = self._ram
        return (ram[at], ram[at + 1], ram[at + 2], ram[at + 3])

    def tile(self, col: int, row: int) -> int | None:
        """The tile id at a cell of the 8 px grid, or None for sky. `col` wraps
        with the lap."""
        metatile = self.metatile(row // METATILE_TILES, (col // METATILE_TILES) % COLS)
        if metatile == EMPTY:
            return None
        return self.tiles(metatile)[(row % METATILE_TILES) * METATILE_TILES
                                    + col % METATILE_TILES]

    def hit(self, col: int, row: int) -> Hit:
        """What the collision makes of the tile at a cell of the 8 px grid."""
        tile = self.tile(col, row)
        return SKY if tile is None else self.cartridge.hit(tile)

    def collision(self, tile: int) -> Hit:
        """What the collision makes of tile id `tile`."""
        return self.cartridge.hit(tile)

    def is_rock(self, tile: int) -> bool:
        return tile == ROCK

    def items(self) -> list[tuple[int, int, int]]:
        """The course's items as `(kind, row, col)`, the J and the mini-maniacs
        included -- they are not in the map, and they can be picked up."""
        cartridge = self.cartridge
        at = cartridge.word(ITEMS + 2 * (self.number - 1))
        out = []
        while cartridge.byte(at) != EMPTY:
            row, col, kind = cartridge.byte(at), cartridge.byte(at + 1), cartridge.byte(at + 2)
            if self.mode & MODE_T_IS_N and kind == T_CRATE:
                kind = N_CRATE
            out.append((kind, row, col))
            at += 3
        return out

    def teleports(self) -> list[tuple[int, int, int]]:
        """The stretches the computer's bike may be put back on, as the original
        lists them: from the finish back, down to one starting at 0."""
        cartridge = self.cartridge
        at = cartridge.word(TELEPORTS + 2 * (self.number - 1))
        out = []
        while True:
            start, end, y = cartridge.word(at), cartridge.word(at + 2), cartridge.byte(at + 4)
            out.append((start, end, y))
            if not start:
                return out
            at += 5

    def put(self, row: int, col: int, metatile: int) -> None:
        """Set a cell of the map: a crate taken is emptied, and at the lap line
        every crate is put back -- as the bare crate, over whatever was under it."""
        self._ram[_MAP_AT + row * COLS + col % COLS] = metatile

    def goal(self) -> None:
        """Put the sign over the finish on the course.

        The original does this as the player crosses the lap line, which is the
        start of the last lap, so the sign is not there the first time round.
        It writes the two metatiles straight into the map -- no merge, like
        `put` -- into the hollow at the top of the mound the finish sits on.
        """
        for step, metatile in enumerate(GOAL):
            self.put(GOAL_ROW, GOAL_COL + step, metatile)

    def probes(self, direction: int) -> Probed:
        return self.cartridge.probes(direction)

    def throw(self, step: int) -> tuple[int, int]:
        return self.cartridge.throw(step)

    # -- building it -------------------------------------------------------------

    def _stamp_pieces(self, at: int) -> None:
        cartridge = self.cartridge
        while cartridge.byte(at) != EMPTY:
            row, col, piece = cartridge.byte(at), cartridge.byte(at + 1), cartridge.byte(at + 2)
            at += 3
            data = cartridge.word(PIECES + 2 * piece)
            rows, cols = cartridge.byte(data), cartridge.byte(data + 1)
            data += 2
            for r in range(min(rows, ROWS - row)):
                for c in range(cols):
                    self._stamp(row + r, (col + c) % COLS, cartridge.byte(data + r * cols + c))

    def _stamp_items(self, at: int) -> None:
        cartridge = self.cartridge
        while cartridge.byte(at) != EMPTY:
            row, col, kind = cartridge.byte(at), cartridge.byte(at + 1), cartridge.byte(at + 2)
            at += 3
            if kind not in UNSTAMPED:
                self._stamp(row, col, kind)

    def _stamp(self, row: int, col: int, new: int) -> None:
        cell = _MAP_AT + row * COLS + col
        if self.mode & MODE_T_IS_N and new == T_CRATE:
            new = N_CRATE
        old = self._ram[cell]
        if old == EMPTY or new == EMPTY:
            self._ram[cell] = new
            return
        merged = list(self.tiles(old))
        for i, tile in enumerate(self.tiles(new)):
            if tile != TRANSPARENT:
                merged[i] = tile
        self._ram[cell] = self._find_or_make((merged[0], merged[1], merged[2], merged[3]))

    def _find_or_make(self, tiles: Tiles) -> int:
        for metatile in range(FIRST_MADE):
            if self.tiles(metatile) == tiles:
                return metatile
        ram = self._ram
        for i in range(self.counter):
            at = 4 * i
            if at + 4 <= _BLOCK and (ram[at], ram[at + 1], ram[at + 2], ram[at + 3]) == tiles:
                return (FIRST_MADE + i) & 0xFF
        self.counter = (self.counter + 1) & 0xFF
        at = 4 * (self.counter - FIRST_MADE)
        ram[at:at + 4] = bytes(tiles)
        return self.counter
