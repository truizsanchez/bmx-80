"""How the bike feels the ground: a 6x6 window of tiles, and a few of them probed.

Each tick the original copies the 3x3 metatiles around the bike into a **window**
of 6x6 tile ids -- from one metatile row above the bike's, and from the bike's own
metatile column rightwards -- and reads the collision of a handful of its cells:

- **three floor probes**, which cells depending on the direction of travel, so
  they rotate with it: under the wheels on the level, to the right up a wall,
  above on a ceiling. At direction 4, while riding, the first is cell 22;
- **the cell beside the third**, one to its right in the window: the original
  reads it by stepping on from the third probe's cell;
- **two by attitude**, the first two cells of the probe set for where the bike
  points;
- **four fixed cells**, whatever the direction.

A cell is shifted one row down when the bike is in the lower half of its
metatile, and one column left when it is in the left half.

Which cells are probed per direction is the ground's to say (`Ground.probes`):
the original's are a table, hand-made and irregular, read from the cartridge.
"""

from typing import NamedTuple

from game.engine.original import (
    FIXED, HALF_METATILE, METATILE, RIDING_UP_45, UP_45, WINDOW, WINDOW_METATILES)
from game.engine.rules import State
from game.engine.terrain import Ground, Hit


class Probes(NamedTuple):
    """What the collision made of each probed cell, named by where it sits."""

    first: Hit
    second: Hit
    third: Hit
    beside_third: Hit
    below_left: Hit      # cell 26
    below: Hit           # cell 27
    attitude_first: Hit
    attitude_second: Hit
    above: Hit           # cell 15
    at: Hit              # cell 21
    #: Cell 21's tile id itself, which is how a rock is found: by what it is,
    #: not by its collision.
    at_tile: int


def window(ground: Ground, y: int, x: int) -> list[int]:
    """The 36 tile ids around a bike at pixel `(x, y)`, row by row."""
    row0 = y // METATILE - 1
    col0 = x // METATILE
    cells = [0] * (WINDOW * WINDOW)
    for r in range(WINDOW_METATILES):
        for c in range(WINDOW_METATILES):
            tiles = ground.tiles(ground.metatile(row0 + r, col0 + c))
            at = 2 * r * WINDOW + 2 * c
            cells[at], cells[at + 1] = tiles[0], tiles[1]
            cells[at + WINDOW], cells[at + WINDOW + 1] = tiles[2], tiles[3]
    return cells


def _shifted(index: int, y: int, x: int) -> int:
    if y & HALF_METATILE:
        index += WINDOW
    if not x & HALF_METATILE:
        index -= 1
    return index


def _cell(cells: list[int], index: int, y: int, x: int) -> int:
    return cells[_shifted(index, y, x)]


def probe(ground: Ground, cells: list[int], y: int, x: int, direction: int,
          attitude: int, state: State) -> Probes:
    """The probes of a bike at pixel `(x, y)`, read off its window."""
    first, second, third = ground.probes(direction)
    if direction == UP_45 and state is State.RIDING:
        first = RIDING_UP_45
    by_attitude = ground.probes(attitude)

    def hit(index: int) -> Hit:
        return ground.collision(_cell(cells, index, y, x))

    return Probes(
        hit(first), hit(second), hit(third),
        ground.collision(cells[_shifted(third, y, x) + 1]),
        hit(FIXED[0]), hit(FIXED[1]),
        hit(by_attitude[0]), hit(by_attitude[1]),
        hit(FIXED[2]), hit(FIXED[3]),
        _cell(cells, FIXED[3], y, x),
    )
