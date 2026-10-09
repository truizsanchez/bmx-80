"""What the original's screen holds of the course, which is not always the map.

The Game Boy's background is 32 x 32 tiles, 256 px square -- as tall as a
course, so every row of it is always there, and an eighth of a lap wide. The
original fills it a tile column at a time as the view scrolls: **a column is
read out of the map when it comes into view, and not again** until the view has
gone a whole background's width on and the same slot is wanted for another.

So a change to the map does not reach the screen by itself. The one change that
must -- a crate taken, which the original blanks in video memory as well as in
the map -- is written through (`take`). The ones made at the lap line -- the
crates back, and the sign over the finish -- are written into the map alone, and
the lap line is just past the sign: **the sign goes up behind the player and is
not seen until they come round to it again.** Drawing the map as it is would put
it on the screen the moment the line is crossed.

A column is its place in the course, in tiles, and the map's column as it was
when that one scrolled in. Pyxel-free, so the suite can read what the screen
shows without opening one.
"""

from game.engine.original import COLS, ROWS, SLOTS, TILE, VIEW_W
from game.engine.terrain import Ground


class Background:
    """The course as the screen has it: a map column a slot, as it scrolled in."""

    def __init__(self, ground: Ground) -> None:
        self.ground = ground
        #: Slot -> the tile column in it and its metatiles, top row first.
        self._slots: dict[int, tuple[int, list[int]]] = {}

    def scroll(self, x: int) -> None:
        """The view is at `x` pixels: any column it touches that is not in its
        slot is read in, and whatever that slot held is gone."""
        first = x // TILE
        for col in range(first, first + VIEW_W // TILE + 1):
            self._column(col)

    def tile(self, row: int, col: int) -> int:
        """The tile the screen shows at a tile's cell of the course. A column
        not in yet is read in now, as it would be scrolling into view."""
        metatile = self._column(col)[row // 2 % ROWS]
        return self.ground.tiles(metatile)[(row % 2) * 2 + col % 2]

    def take(self, row: int, col: int, metatile: int) -> None:
        """A crate taken: its cell, in metatiles, is changed on the screen too
        -- where the screen has that cell, since the original writes into
        whatever the slot holds and the crate is always in view."""
        for half in (0, 1):
            tile_col = col * 2 + half
            held = self._slots.get(tile_col % SLOTS)
            if held is not None and held[0] // 2 % COLS == col % COLS:
                held[1][row] = metatile

    def _column(self, col: int) -> list[int]:
        held = self._slots.get(col % SLOTS)
        if held is None or held[0] != col:
            held = (col, [self.ground.metatile(row, col // 2) for row in range(ROWS)])
            self._slots[col % SLOTS] = held
        return held[1]
