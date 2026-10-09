"""Where everything in the editor's window is: arithmetic, and no drawing.

The window is 640x480 -- twice the game's 4:3, which Pyxel brings up at a scale
of two on an ordinary display, so the art is two real pixels to one. A toolbar
along the top, a status line along the bottom, the map on the left with its
scrollbar under it, and the palette in a fixed column on the right.

**The course is 256 px tall and the map pane is taller**, so at 1:1 the whole
height of a course is always in view and only the width scrolls. At 2:1 it
scrolls both ways.

**The scrollbars are where the view is**, a metatile a step, and nothing
else keeps a copy: a second copy of a scroll is two things that disagree about
where the view is, and the bar is the one an author can see and drag. A course
is a ring, but the view runs from its first column to its last -- a stamping
that runs past the end still comes round to the start, and that is the ring's
business rather than the scroll's.

No pyxel.
"""

from collections.abc import Sequence
from typing import NamedTuple

from game.course import COLS, METATILE_PX, ROWS

WINDOW_W = 640
WINDOW_H = 480
TOOLBAR_H = 14
STATUS_H = 12
SCROLL_H = 7
#: The vendored scrollbar's thickness, which it fixes itself.
BAR = 7
PALETTE_W = 200
TAB_H = 12
#: The glyph box of Pyxel's built-in font, which a label is measured in.
FONT_W = 4
FONT_H = 6

#: The course in pixels: one lap across, and the height a `y` wraps at.
COURSE_W = COLS * METATILE_PX
COURSE_H = ROWS * METATILE_PX
ZOOMS = (1, 2)

Cell = tuple[int, int]


class Rect(NamedTuple):
    x: int
    y: int
    w: int
    h: int

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


MAP = Rect(0, TOOLBAR_H, WINDOW_W - PALETTE_W - BAR, WINDOW_H - TOOLBAR_H - STATUS_H - SCROLL_H)
SCROLL = Rect(0, MAP.y + MAP.h, MAP.w, SCROLL_H)
VSCROLL = Rect(MAP.x + MAP.w, MAP.y, BAR, MAP.h)
PALETTE = Rect(WINDOW_W - PALETTE_W, TOOLBAR_H, PALETTE_W, WINDOW_H - TOOLBAR_H - STATUS_H)
TABS = Rect(PALETTE.x, PALETTE.y, PALETTE.w, TAB_H)
ENTRIES = Rect(PALETTE.x, PALETTE.y + TAB_H, PALETTE.w - BAR, PALETTE.h - TAB_H)
PALETTE_BAR = Rect(PALETTE.x + PALETTE.w - BAR, ENTRIES.y, BAR, ENTRIES.h)
STATUS = Rect(0, WINDOW_H - STATUS_H, WINDOW_W, STATUS_H)

#: The palette's tabs, in order: what a map is drawn with, from the pieces an
#: author reaches for first to the smallest thing there is to put down, and
#: then what is on a course that is not ground.
TAB_NAMES = ("pieces", "metatiles", "things")
#: ...and in an enhanced course, the enhanced vocabulary's own, before the things.
EXTRA = "extra"
ENHANCED_TAB_NAMES = ("pieces", "metatiles", EXTRA, "things")


class View:
    """What the map pane shows: a scroll in metatiles, which the scrollbars
    hold, and a zoom."""

    def __init__(self) -> None:
        self.col = 0
        self.row = 0
        self.zoom = 1

    @property
    def x(self) -> int:
        return self.col * METATILE_PX

    @property
    def y(self) -> int:
        return self.row * METATILE_PX

    def cell_at(self, px: float, py: float) -> Cell | None:
        """The metatile cell under a window point, as `(row, col)`, or None
        outside the map pane or off the course's rows."""
        if not MAP.contains(px, py):
            return None
        wx = int((px - MAP.x) // self.zoom) + self.x
        wy = int((py - MAP.y) // self.zoom) + self.y
        row = wy // METATILE_PX
        if not 0 <= row < ROWS:
            return None
        return row, (wx // METATILE_PX) % COLS

    def world_at(self, px: float, py: float) -> tuple[int, int] | None:
        """The course pixel under a window point, `x` round the ring, or None
        outside the map pane."""
        if not MAP.contains(px, py):
            return None
        return ((int((px - MAP.x) // self.zoom) + self.x) % COURSE_W,
                int((py - MAP.y) // self.zoom) + self.y)

    def screen_x(self, wx: int) -> int:
        """Where a course `x` is drawn: its copy nearest the pane's left."""
        return MAP.x + ((wx - self.x) % COURSE_W) * self.zoom

    def screen_y(self, wy: int) -> int:
        return MAP.y + (wy - self.y) * self.zoom

    def screen_of(self, row: int, col: int) -> tuple[int, int]:
        """Where a cell's top-left corner is drawn: the copy of it nearest the
        left of the pane, since the ring puts one every lap."""
        wx = (col * METATILE_PX - self.x) % COURSE_W
        return MAP.x + wx * self.zoom, MAP.y + (row * METATILE_PX - self.y) * self.zoom

    def visible(self) -> range:
        """The columns in view, left to right, as unwrapped numbers from the
        scroll -- take each `% COLS` for the cell."""
        first = self.x // METATILE_PX
        return range(first, first + MAP.w // (METATILE_PX * self.zoom) + 2)

    def columns_in_view(self) -> int:
        return MAP.w // (METATILE_PX * self.zoom)

    def rows_in_view(self) -> int:
        return min(ROWS, MAP.h // (METATILE_PX * self.zoom))


class Entry(NamedTuple):
    """One thing on a palette tab: its name, and the box its picture needs."""

    name: str
    w: int
    h: int


def label_w(name: str) -> int:
    return len(name) * FONT_W


def flow(entries: Sequence[Entry], width: int = ENTRIES.w, gap: int = 4) -> list[Rect]:
    """Each entry's box, laid out in rows left to right, relative to the tab's area.

    A box is wide enough for its picture and its label, and tall enough for both,
    the label under the picture. Rows are as tall as their tallest box.
    """
    out: list[Rect] = []
    x, y, row_h = gap, gap, 0
    for entry in entries:
        w = max(entry.w, label_w(entry.name)) + 2
        h = entry.h + FONT_H + 3
        if x + w > width - gap and x > gap:
            x, y, row_h = gap, y + row_h + gap, 0
        out.append(Rect(x, y, w, h))
        x += w + gap
        row_h = max(row_h, h)
    return out


def flow_groups(groups: Sequence[tuple[str, Sequence[Entry]]], width: int = ENTRIES.w,
                gap: int = 4) -> tuple[list[Rect], list[tuple[Rect, str]]]:
    """`flow`, a group at a time, each under a heading of its own on a row of its
    own: the entries' boxes in order, and the headings' boxes with their titles."""
    boxes: list[Rect] = []
    headings: list[tuple[Rect, str]] = []
    y = 0
    for title, entries in groups:
        if not entries:
            continue
        headings.append((Rect(gap, y + gap, width - 2 * gap, FONT_H), title))
        top = y + gap + FONT_H + 2
        placed = flow(entries, width, gap)
        boxes += [Rect(box.x, box.y + top, box.w, box.h) for box in placed]
        y = top + flow_height(placed, gap) - gap
    return boxes, headings


def flow_height(boxes: Sequence[Rect], gap: int = 4) -> int:
    return max((box.y + box.h for box in boxes), default=0) + gap


def tab_rect(index: int, count: int = len(TAB_NAMES)) -> Rect:
    """Where a tab's label sits in the tab strip, of `count` tabs."""
    width = TABS.w // count
    return Rect(TABS.x + index * width, TABS.y, width, TABS.h)
