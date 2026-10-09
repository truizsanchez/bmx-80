"""What the engine knows about the ground: tiles, and what the collision makes of one.

The original sees the ground as tiles and never as geometry. A course is a map of
16x16 **metatiles**, each four 8x8 tile ids; each tile id has a collision byte;
and a bike standing on a tile takes that tile's direction as its own.

`Ground` is what a course has to answer for the engine to ride it, in the
original's own terms -- a map of metatiles, the tiles of a metatile, the collision
of a tile, and which cells of the window around the bike are probed for each
direction. Whatever builds a course answers the same questions: the original's
own data read out of a cartridge (`game/rom/`), or this game's maps. The engine
does not know which it got.
"""

from collections.abc import Sequence
from typing import NamedTuple, Protocol


class Hit(NamedTuple):
    """A tile, as the collision sees it."""

    #: The bike cannot pass through it.
    solid: bool
    #: Sand: the slope term is `original.SOFT_TERM` while the wheels are on it, level.
    soft: bool
    #: A wheelie cannot start on it -- and the sand is not read on it, though
    #: none of the tiles the original marks this way is sand.
    no_wheelie: bool
    #: The direction of travel on it, 0-31 (see `game/engine/__init__.py`).
    direction: int
    #: What riding it does beyond the original's four facts: `NORMAL` on every
    #: tile the original has, and one of the others only on a tile an enhanced
    #: course declares (`maps/enhanced/tiles.json`).
    surface: int = 0


#: What a tile does to a bike riding it, past the original's rules, by the name
#: a tile declares it under. The original has one kind of surface, the first,
#: and a cartridge's tile is always that.
SURFACES = {name: kind for kind, name in enumerate(("normal", "ice", "spring", "rush"))}
NORMAL, ICE, SPRING, RUSH = SURFACES.values()

#: What an empty cell is.
SKY = Hit(False, False, False, 0)

#: A metatile as its four tile ids: top left, top right, bottom left, bottom right.
Tiles = tuple[int, int, int, int]
#: The cells of the window probed for one direction, as window indices.
Probed = tuple[int, int, int]


class Ground(Protocol):
    """A course, as the engine reads it."""

    def metatile(self, row: int, col: int) -> int:
        """The metatile id at a cell of the map. `row` runs from -1 to 16: the
        window around a bike on the top or bottom row reaches one past it, and
        the ground answers what the original reads there."""
        ...

    def tiles(self, metatile: int) -> Tiles: ...

    def collision(self, tile: int) -> Hit: ...

    def is_rock(self, tile: int) -> bool:
        """Whether a tile is a rock: found by what it is, not by its collision."""
        ...

    def probes(self, direction: int) -> Probed:
        """Which cells of the 6x6 window the three floor probes read for a
        direction, as row * 6 + col."""
        ...

    def items(self) -> Sequence[tuple[int, int, int]]:
        """The things on the course to pick up: `(kind, row, col)`, by metatile."""
        ...

    def teleports(self) -> Sequence[tuple[int, int, int]]:
        """Where the computer's bike may be put back on the course: stretches
        `(start, end, y)` in pixels, from the finish back to the start."""
        ...

    def put(self, row: int, col: int, metatile: int) -> None:
        """Change a cell of the map: where a crate is taken, and put back."""
        ...

    def goal(self) -> None:
        """Put the sign over the finish on the course, which the original does
        as the player starts the last lap.

        **What the sign is, and whether there is one at all, is the course's**:
        the engine knows only that the lap line was crossed. A course with no
        sign does nothing here.
        """
        ...

    def throw(self, step: int) -> tuple[int, int]:
        """Where a crash throws the rider, one step of `THROW_STEPS`: `(dy, dx)`,
        dy in 1/256 px and dx in whole pixels, thrown backwards. The original's
        path is a hand-made arc, so it is the ground's to hand over."""
        ...

