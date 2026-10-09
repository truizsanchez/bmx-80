"""The course in hand: the file's contents, and every edit made to it by name.

**The document is the file** -- the dict `maps/read.py` reads and `read.dump`
writes -- and nothing is kept beside it that the file does not hold. What the
editor saves is exactly what it has been drawing.

**A course is a list, and its order is part of it.** Every stamping merges into
whatever the ones before it left (`game/course.Tileset.merge`), so the same
pieces in another order are another course. That is why an edit here is always
said in terms of the list: a new stamping goes **on top** -- at the end -- a
right-click takes away the one on top of a cell, and raising or lowering one
moves it past the next stamping it actually shares a cell with, which is the
only kind of move that changes anything.

A stamping covers every cell of its piece's grid, `.` included -- a `.` erases,
and an erasure is something on that cell like any other. A column past the last
comes round to the first and a row past the last is not there, as in `Course`.

No pyxel.
"""

import copy
import json
from collections.abc import Mapping, Sequence
from typing import Any

from game.course import COLS, CRATES, METATILE_PX, ROWS, Course, Tables, Tileset, vocabulary
from maps import read
from tools.editor.history import History

Cell = tuple[int, int]
Data = dict[str, Any]

#: A new course's clocks, in seconds, one a level: long enough to ride round and
#: find out what a lap costs before the author sets them.
NEW_LIMITS = [600.0, 600.0, 600.0]
#: The kinds of crate an author can put down, in the engine's order.
ITEM_KINDS = tuple(CRATES)


def empty() -> Data:
    """A course with nothing on it, in the file's own field order."""
    return {"pieces": [], "items": [], "limits": list(NEW_LIMITS), "teleports": []}


class Document:
    """One course being edited, its undo history, and a revision to cache on."""

    def __init__(self, tiles: Tileset, pieces: "Mapping[str, Sequence[Sequence[str]]]",
                 tables: Tables, data: Data | None = None) -> None:
        self.tiles = tiles
        self.tables = tables
        #: Everything that can be stamped, by name: the pieces and every metatile.
        self.offered = vocabulary(pieces, tiles)
        self.data: Data = copy.deepcopy(data) if data is not None else empty()
        for key, value in empty().items():
            self.data.setdefault(key, value)
        self.history: History[str] = History(self._snapshot())
        #: Rises on every change to what is drawn, undo and redo included.
        self.revision = 0
        self._built: tuple[int, Course] | None = None

    # -- the state ------------------------------------------------------------

    def _snapshot(self) -> str:
        return json.dumps(self.data)

    def _changed(self, amend: bool = False) -> None:
        self.revision += 1
        state = self._snapshot()
        if not (amend and self.history.amend(state)):
            self.history.record(state)

    def _restore(self, state: str | None) -> bool:
        if state is None:
            return False
        self.data = json.loads(state)
        self.revision += 1
        return True

    def undo(self) -> bool:
        return self._restore(self.history.back())

    def redo(self) -> bool:
        return self._restore(self.history.forward())

    def text(self) -> str:
        """The file this document is: what a save writes."""
        return read.dump(self.data)

    def built(self) -> Course:
        """The course as the game would build it, once per revision."""
        if self._built is None or self._built[0] != self.revision:
            self._built = (self.revision, self.build(self.data))
        return self._built[1]

    def build(self, data: Data) -> Course:
        """Any contents built in this document's vocabulary -- which is how a
        stamping not yet made is shown already merged."""
        return read.course_from(data, self.tiles, self.offered, self.tables)

    # -- what is where ---------------------------------------------------------

    @property
    def stampings(self) -> list[list[Any]]:
        stampings: list[list[Any]] = self.data["pieces"]
        return stampings

    def size(self, name: str) -> tuple[int, int]:
        """A piece's footprint as `(rows, cols)`."""
        grid = self.offered[name]
        return len(grid), max((len(line) for line in grid), default=0)

    def cells(self, row: int, col: int, name: str) -> list[Cell]:
        """The cells a stamping of `name` at `(row, col)` covers, as `(row, col)`,
        wrapped round the ring and without the rows below the last."""
        return [(row + down, (col + along) % COLS)
                for down, line in enumerate(self.offered[name]) if row + down < ROWS
                for along in range(len(line))]

    def stack(self, row: int, col: int) -> list[int]:
        """The stampings covering a cell, by their place in the list, bottom first."""
        cell = (row, col % COLS)
        return [at for at, (r, c, name) in enumerate(self.stampings)
                if cell in self.cells(r, c, name)]

    def top(self, row: int, col: int) -> int | None:
        stack = self.stack(row, col)
        return stack[-1] if stack else None

    # -- edits -----------------------------------------------------------------

    def stamp(self, row: int, col: int, name: str, amend: bool = False) -> int:
        """Put `name` down on top of everything, its top-left corner at the cell.

        `amend` folds this into the edit before it, which is how a drag that
        repeats a piece along a row is one undo however many it puts down.
        """
        if name not in self.offered:
            raise ValueError("nothing called %r to stamp" % name)
        if not 0 <= row < ROWS:
            raise ValueError("row %d is off the course" % row)
        self.stampings.append([row, col % COLS, name])
        self._changed(amend)
        return len(self.stampings) - 1

    def remove(self, at: int) -> None:
        del self.stampings[at]
        self._changed()

    def remove_top(self, row: int, col: int) -> bool:
        """Take away what is on top of a cell: its crate first, then the last
        stamping covering it. False where there is nothing there."""
        if self.remove_item(row, col):
            return True
        at = self.top(row, col)
        if at is None:
            return False
        self.remove(at)
        return True

    def raise_(self, at: int) -> int:
        """Move a stamping above the next one it shares a cell with; its new place."""
        return self._move(at, 1)

    def lower(self, at: int) -> int:
        """Move a stamping below the one under it that it shares a cell with."""
        return self._move(at, -1)

    def _move(self, at: int, step: int) -> int:
        mine = set(self.cells(*self._where(at)))
        other = at + step
        while 0 <= other < len(self.stampings):
            if mine & set(self.cells(*self._where(other))):
                moved = self.stampings.pop(at)
                self.stampings.insert(other, moved)
                self._changed()
                return other
            other += step
        return at

    def _where(self, at: int) -> tuple[int, int, str]:
        row, col, name = self.stampings[at]
        return row, col, name

    # -- the things that are not ground ---------------------------------------

    @property
    def items(self) -> list[list[Any]]:
        items: list[list[Any]] = self.data["items"]
        return items

    def item_at(self, row: int, col: int) -> int | None:
        for at, (_, r, c) in enumerate(self.items):
            if (r, c % COLS) == (row, col % COLS):
                return at
        return None

    def put_item(self, kind: str, row: int, col: int) -> None:
        """A crate on a cell, in place of whatever crate was there."""
        if kind not in ITEM_KINDS:
            raise ValueError("no crate of kind %r" % kind)
        at = self.item_at(row, col)
        if at is not None:
            del self.items[at]
        self.items.append([kind, row, col % COLS])
        self._changed()

    def remove_item(self, row: int, col: int) -> bool:
        at = self.item_at(row, col)
        if at is None:
            return False
        del self.items[at]
        self._changed()
        return True

    # -- where the computer's bike is put back ----------------------------------

    @property
    def teleports(self) -> list[list[int]]:
        teleports: list[list[int]] = self.data["teleports"]
        return teleports

    def add_teleport(self, start: int, end: int, y: int) -> None:
        """A stretch `(start, end, y)` in pixels where the computer's bike may be
        put back when it falls behind. Kept **from the finish back to the
        start**, which is the order the rival walks them in."""
        start, end = min(start, end), max(start, end)
        self.teleports.append([start, end, y])
        self.teleports.sort(key=lambda stretch: -stretch[0])
        self._changed()

    def teleport_at(self, x: int, y: int, reach: int = METATILE_PX) -> int | None:
        """The stretch passing within `reach` of a point, if there is one."""
        for at, (start, end, height) in enumerate(self.teleports):
            if start <= x <= end and abs(height + METATILE_PX - y) <= reach:
                return at
        return None

    def remove_teleport(self, at: int) -> None:
        del self.teleports[at]
        self._changed()

    def set_limit(self, level: int, seconds: float) -> None:
        """A level's clock. **Outside the undo**: a clock is stepped ten at a
        time on a held button, and undo is about the drawing."""
        self.data["limits"][level] = float(seconds)
