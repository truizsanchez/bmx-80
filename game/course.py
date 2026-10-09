"""A course of this game's own: the ring it is built on, the vocabulary it is
drawn out of, the levels it is ridden at, and how the bike feels it.

A course is in the shape the original's are: a ring of metatiles, pieces stamped
with a merge, a collision byte each tile declares (`Tileset`, `Course`). Beside
it, the **levels**, which are a fact about a race and not about a map, and the
two **tables** a course hands the engine about the bike (`Tables`).
"""

from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from game.engine.original import WINDOW
from game.engine.terrain import SKY, SURFACES, Hit, Probed, Tiles
from game.engine.original import THROW_STEPS

# The three skill levels, and a level is **one thing**: a different time limit.
# No geometry changes and nothing about the bike changes.
#
# Named with the capital that picks each one out: "eAsy", "Bumpy", "Crazy".
EASY, BUMPY, CRAZY = 0, 1, 2
LEVELS = (EASY, BUMPY, CRAZY)
LEVEL_LETTERS = ("A", "B", "C")
LEVEL_NAMES = ("eAsy", "Bumpy", "Crazy")
DEFAULT_LEVEL = BUMPY

# Two jobs and two names. `DEFAULT_LEVEL` is the **reference clock**: the middle
# of the three, and what a limit is typed against. It has to stay `BUMPY` --
# moving it would re-balance every course without touching a map.
#
# `START_LEVEL` is only the level the menu opens on, which is a question about
# the screen and about no clock at all: somebody meeting this game for the first
# time should meet it on the easy one.
START_LEVEL = EASY


# -- how the bike feels a course of ours --------------------------------------


#: The engine counts 32 directions of travel, counter-clockwise from the right:
#: 0 level, 4 a 45 up, 8 a wall, 16 a ceiling, 28 a 45 down. See
#: `game/engine/__init__.py`, which is where the convention is fixed.
DIRECTIONS = 32
DEGREES = 360.0 / DIRECTIONS
#: Every attitude the bike can have, and so every row the probe table has: the
#: 32 directions, then the poses of the rider thrown off and the flourishes.
#: The engine reads the probes by attitude as well as by direction, and the
#: original's table has a row for each.
ATTITUDES = 0x38


class Tables(NamedTuple):
    """The two things a course tells the engine about the bike rather than the
    ground, as the original's tables: `maps/tables.json`.

    `probes` is which three cells of the engine's 6x6 window the floor probes
    read, one row an attitude (`ATTITUDES`) -- the two under the wheels and the
    one at the leading corner. `throw` is the path a crash throws the rider along,
    one `(dy, dx)` a step. Both are **what the original's are**, which is what
    makes a course ride frame for frame as it does: a rule was tried for each
    and measured, and the nearest rule there is still parts from the original
    within a hundred iterations.
    """

    probes: tuple[Probed, ...]
    throw: tuple[tuple[int, int], ...]

    @classmethod
    def of(cls, probes: "Sequence[Sequence[int]]",
           throw: "Sequence[Sequence[int]]") -> "Tables":
        """Tables from a file's lists, refused when they are not the shape the
        engine reads: one row of three cells inside the window per direction,
        and one pair per step of a throw."""
        if len(probes) != ATTITUDES or any(len(row) != 3 for row in probes):
            raise ValueError("the probes are %d rows of three cells, one an attitude"
                             % ATTITUDES)
        if any(not 0 <= cell < WINDOW * WINDOW for row in probes for cell in row):
            raise ValueError("a probe is outside the %dx%d window" % (WINDOW, WINDOW))
        if len(throw) != THROW_STEPS or any(len(step) != 2 for step in throw):
            raise ValueError("a throw is %d steps of (dy, dx)" % THROW_STEPS)
        return cls(tuple((int(a), int(b), int(c)) for a, b, c in probes),
                   tuple((int(dy), int(dx)) for dy, dx in throw))


# -- a course of this game's own ----------------------------------------------


#: The ring a course is: rows and columns of metatiles, and a metatile in pixels
#: and in tiles. **The port's numbers exactly**, and deliberately: 256 columns of
#: 16 px is 4096 px, which is the lap the engine's lines are written in
#: (`game/engine/run.py`), and 16 rows of 16 px is the 256 px its `y` wraps at.
#: A course of another size would want an engine of another size.
ROWS, COLS = 16, 256
METATILE_PX, METATILE_TILES = 16, 2
LAP_PX = COLS * METATILE_PX

#: A cell with nothing in it. **The engine's own number** -- `Run` hands it to
#: `put` when a crate is taken -- so it is not ours to choose.
EMPTY = 0xFF
#: In a metatile, a tile that lets the one underneath through when this metatile
#: is stamped over another. In a piece, a cell that stamps nothing.
TRANSPARENT, NOTHING = "-", "."

#: The metatile ids the engine names for itself, in its order. `Run` stamps a
#: crate back by its kind (`game/engine/items.py`), so those four ids are the
#: crates whatever a course calls them; `Course.goal` writes the first two.
#: Kinds 6 and 7 -- the J and the mini-maniacs -- are pickups with no picture,
#: so they are ids nothing draws.
RESERVED = ("goal_left", "goal_right", "crate_s", "crate_t", "crate_n", "crate_r")
#: ...and an author's metatiles start here, past the two the reserved kinds skip.
FIRST_AUTHORED = 8

#: The tile a course is empty of, and the one it is filled with where a metatile
#: says nothing: sky, which no collision touches.
SKY_TILE = "sky"

#: The crates, by the kind the engine counts them in.
CRATES = {"s": 2, "t": 3, "n": 4, "r": 5, "j": 6, "mini": 7}

#: A tile of the vocabulary is named for its number in the original, in hex:
#: `t45` is the original's tile 0x45. `tools/vocab_from_rom.py` writes the
#: names, and a cartridge's own picture of a tile is found by them.
ORIGINAL_TILE = "t%02x"


def original_tile(name: str) -> int | None:
    """The original's number for a tile name, or None for a name that is not one."""
    if len(name) != 3 or name[0] != "t":
        return None
    try:
        return int(name[1:], 16)
    except ValueError:
        return None


class Tileset:
    """Every tile and metatile a course can be drawn out of, and their ids.

    The engine reads a course as *numbers* -- a metatile id per cell, four tile
    ids per metatile, a `Hit` per tile id -- and an author writes *names*. This
    is the one place the two meet, and nothing outside it ever sees an id that
    it did not get from here.

    **A tile declares what it collides as.** The original keeps a byte per tile
    in its cartridge and this keeps the same four facts beside the drawing:
    solid, soft, no-wheelie, and which of the engine's 32 directions is the
    direction of travel on it. Reading them off the picture instead was tried on
    the format that came before this one and it cannot answer for a plain block,
    which has no way to say which side the sky is on.
    """

    def __init__(self, tiles: "Mapping[str, Mapping[str, Any]]",
                 metatiles: "Mapping[str, Sequence[str]]", capped: bool = True) -> None:
        #: Whether a metatile id is a byte, as the original's is: 255 ids and
        #: `EMPTY` one of them. **A classic course is held to it** and an
        #: enhanced one is not (`maps/read.py`): the engine never masks an id,
        #: so past 254 they go on, stepping over `EMPTY`.
        self.capped = capped
        self.tile_id: dict[str, int] = {SKY_TILE: 0}
        self.hits: list[Hit] = [SKY]
        self.rocks: set[int] = set()
        for name, what in tiles.items():
            if name in self.tile_id:
                raise ValueError("%r is a tile twice over" % name)
            self.tile_id[name] = len(self.hits)
            if bool(what.get("rock")):
                self.rocks.add(len(self.hits))
            surface = str(what.get("surface", "normal"))
            if surface not in SURFACES:
                raise ValueError("%r is a surface there is none of, on %r; there are %s"
                                 % (surface, name, ", ".join(SURFACES)))
            self.hits.append(Hit(bool(what.get("solid", True)),
                                 bool(what.get("soft", False)),
                                 bool(what.get("no_wheelie", False)),
                                 int(what.get("dir", 0)) % DIRECTIONS,
                                 SURFACES[surface]))
        #: ...and back again, for whatever draws a course: an id is what the
        #: engine reads and a name is what a drawing is filed under.
        self.names = {at: name for name, at in self.tile_id.items() if name != SKY_TILE}
        #: An id no stamping leaves in a cell -- the merge puts what is underneath
        #: -- but `put` writes a metatile whole, as the original does, and the
        #: sign over the finish is half transparent. **It collides as sky**, as
        #: the original's own transparent tile does in its collision byte.
        self._transparent = len(self.hits)
        self.hits.append(SKY)
        self.quads: dict[int, Tiles] = {}
        self.metatile_id: dict[str, int] = {}
        for index, name in enumerate(RESERVED):
            self._metatile(name, metatiles.get(name), index)
        self._next = FIRST_AUTHORED
        for name, quad in metatiles.items():
            if name not in self.metatile_id:
                self._metatile(name, quad, self._take())
        self.quads[EMPTY] = (0, 0, 0, 0)

    def _take(self) -> int:
        """The next metatile id, refused past the byte when the set is capped."""
        if self._next == EMPTY and not self.capped:
            self._next += 1
        if self._next >= EMPTY and self.capped:
            raise ValueError("a course has run out of metatile ids")
        self._next += 1
        return self._next - 1

    def _metatile(self, name: str, quad: "Sequence[str] | None", at: int) -> None:
        if quad is None:
            self.metatile_id[name] = at
            self.quads[at] = (0, 0, 0, 0)
            return
        if len(quad) != METATILE_TILES * METATILE_TILES:
            raise ValueError("%r is %d tiles and a metatile is four" % (name, len(quad)))
        self.metatile_id[name] = at
        self.quads[at] = self.tiles_of(quad)

    def fork(self) -> "Tileset":
        """The same vocabulary, with a mint of its own.

        **A course mints into its own copy.** The names, the tiles and the
        declared metatiles are shared -- nothing changes them -- but what a
        merge mints belongs to the course that minted it, as the original's
        does to the race it built: its block of made metatiles is filled afresh
        at every race start. Shared, every course ever built out of one set --
        and the editor builds one each time the pointer moves a cell with a
        piece in hand -- spent ids that were never given back, and an original
        course ran out of them within a hundred moves of the pointer.
        """
        copy = object.__new__(Tileset)
        copy.__dict__.update(self.__dict__)
        copy.quads = dict(self.quads)
        return copy

    def tiles_of(self, quad: "Sequence[str]") -> Tiles:
        """Four tile names as four ids, top left, top right, bottom left, bottom
        right -- which is the order the engine indexes a metatile in."""
        ids = tuple(self._transparent if name == TRANSPARENT else self.tile_id[name]
                    for name in quad)
        return (ids[0], ids[1], ids[2], ids[3])

    def lets_through(self, metatile: int) -> bool:
        """Whether any of a metatile's tiles is transparent."""
        return self._transparent in self.quads[metatile]

    def merge(self, under: int, over: int) -> int:
        """`over` stamped on `under`: the id of what the cell holds after it.

        **The merge is the vocabulary.** A piece put down on an occupied cell
        does not replace it -- the two are mixed tile by tile, a transparent
        tile keeping whatever was underneath -- and a metatile the set does not
        already have is *minted*. That is how the original draws eight courses
        out of 82 small pieces, and it is why an author never has to name the
        shape where one thing meets another.
        """
        mixed = list(self.quads[under])
        for index, tile in enumerate(self.quads[over]):
            if tile != self._transparent:
                mixed[index] = tile
        return self.find_or_mint((mixed[0], mixed[1], mixed[2], mixed[3]))

    def find_or_mint(self, quad: Tiles) -> int:
        """The id of a metatile of these four tiles, minting one if there is none.

        The original does this by walking its table and then a block of RAM --
        and, past the block, on into the map itself, which is a fidelity to the
        hardware that costs it a bug. A dictionary here.
        """
        for at, have in self.quads.items():
            if have == quad and at != EMPTY:
                return at
        at = self._take()
        self.quads[at] = quad
        return at


#: Where the sign over the finish goes, and the two metatiles it is. The same
#: cell the original writes it in, because the lap line is in the same place.
GOAL_ROW, GOAL_COL = 13, 249
GOAL = (0, 1)

def vocabulary(pieces: "Mapping[str, Sequence[Sequence[str]]]",
               tiles: Tileset) -> "dict[str, Sequence[Sequence[str]]]":
    """Everything a course can stamp, by name: the pieces, and **every metatile
    as a piece of one cell** that nobody had to declare.

    A piece is the unit an author puts down, and a metatile is the smallest one
    there is; making each metatile a piece of its own by name means a detail
    never has to be declared in `pieces.json` before it can be placed. A piece
    wins where the two share a name, and the metatiles the engine keeps for
    itself -- the goal and the crates -- are not offered: a crate is an item.
    """
    offered: dict[str, Sequence[Sequence[str]]] = {
        name: [[name]] for name in tiles.metatile_id if name not in RESERVED}
    offered.update(pieces)
    return offered


class Course:
    """One course of this game's own, as the engine reads it.

    Built the way the original builds one at race start and answering the same
    ten questions (`game/engine/terrain.Ground`), so that a course of ours and a
    course of the cartridge's reach the engine by the same road. What differs is
    only where the data came from: `game/rom/course.py` reads a cartridge and
    this takes what an author wrote.

    A course is a **ring**: 16 rows by 256 columns of metatiles, a column past
    the last coming round to the first. A **piece** is a small grid of metatile
    names -- or a metatile on its own (`vocabulary`) -- and a course is a list
    of `(row, col, piece)` stamped in order, each merging into what is already
    there (`Tileset.merge`).

    Two rules of the original's that are kept because they are what an author
    ends up relying on: **a column past the last wraps within its row and a row
    past the last clips**, and **stamping nothing erases**.
    """

    def __init__(self, tiles: Tileset, pieces: "Mapping[str, Sequence[Sequence[str]]]",
                 tables: Tables,
                 stampings: "Sequence[tuple[int, int, str]]" = (),
                 items: "Sequence[tuple[str, int, int]]" = (),
                 teleports: "Sequence[tuple[int, int, int]]" = (),
                 limits: "Sequence[float]" = ()) -> None:
        self.tiles_of = tiles.fork()
        self.tables = tables
        pieces = vocabulary(pieces, tiles)
        self.limits = tuple(limits) or (0.0, 0.0, 0.0)
        self._map = [EMPTY] * (ROWS * COLS)
        self._items = [(CRATES[kind], row, col) for kind, row, col in items]
        self._teleports: list[tuple[int, int, int]] = [
            (int(a), int(b), int(y)) for a, b, y in teleports] or [(0, LAP_PX, 232)]
        self.signed = False
        for row, col, piece in stampings:
            self._piece(row, col, pieces[piece])
        for kind, row, col in self._items:
            if kind < CRATES["j"]:
                self._stamp(row, col, kind)

    # -- building it -------------------------------------------------------------

    def _piece(self, row: int, col: int, grid: "Sequence[Sequence[str]]") -> None:
        for down, line in enumerate(grid):
            if row + down >= ROWS:
                return          # a row past the last ends the piece
            for along, name in enumerate(line):
                if name == NOTHING:
                    self._stamp(row + down, col + along, EMPTY)
                else:
                    self._stamp(row + down, col + along, self.tiles_of.metatile_id[name])

    def _stamp(self, row: int, col: int, new: int) -> None:
        """A metatile onto a cell, merged into what is there -- **an empty cell
        included**, whose four tiles are sky: a transparent tile has to let
        *something* through, or it stays an id that means nothing and the
        engine's first probe of it reads past the end of the collision."""
        at = row * COLS + col % COLS
        old = self._map[at]
        if new == EMPTY or (old == EMPTY and not self.tiles_of.lets_through(new)):
            # Nothing to mix: an erasure, or a whole metatile on an empty cell,
            # which keeps its own id -- the engine names the crates by theirs.
            self._map[at] = new
            return
        self._map[at] = self.tiles_of.merge(old, new)

    # -- what the engine reads ---------------------------------------------------

    def metatile(self, row: int, col: int) -> int:
        """The metatile at a cell. Row 16 is row 0 again and a column wraps; row
        -1 is above the map and is sky, which is the one place this differs from
        the original on purpose -- it reads whatever bytes lie before its map,
        and there is nothing here for it to read."""
        if row < 0 or row >= ROWS:
            return EMPTY if row < 0 else self._map[(row % ROWS) * COLS + col % COLS]
        return self._map[row * COLS + col % COLS]

    def tiles(self, metatile: int) -> Tiles:
        return self.tiles_of.quads[metatile]

    def tile_name(self, tile: int) -> str | None:
        """What a tile id is called, or None for sky and for a tile that only
        exists to be transparent. **A course's own art is addressed by name** --
        the cartridge's is addressed by number because that is how a cartridge
        holds it -- so this is what a renderer asks."""
        return self.tiles_of.names.get(tile)

    def collision(self, tile: int) -> Hit:
        return self.tiles_of.hits[tile]

    def is_rock(self, tile: int) -> bool:
        return tile in self.tiles_of.rocks

    def probes(self, direction: int) -> Probed:
        return self.tables.probes[direction]

    def items(self) -> list[tuple[int, int, int]]:
        return list(self._items)

    def teleports(self) -> list[tuple[int, int, int]]:
        return list(self._teleports)

    def put(self, row: int, col: int, metatile: int) -> None:
        """Set a cell outright: a crate taken is emptied, and at the lap line
        every crate is put back. **No merge** -- the original writes over the
        whole cell here, so taking a crate takes the ground it was merged into
        with it, and putting it back puts back the bare crate."""
        self._map[row * COLS + col % COLS] = metatile

    def goal(self) -> None:
        """The sign over the finish, when the player starts the last lap."""
        self.signed = True
        for step, metatile in enumerate(GOAL):
            self.put(GOAL_ROW, GOAL_COL + step, metatile)

    def throw(self, step: int) -> tuple[int, int]:
        """Where a crash throws the rider, one step of `THROW_STEPS`."""
        return self.tables.throw[step]
