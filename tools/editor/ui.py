"""The course editor's window.

    python main.py --edit <name>          # a course by name, or a new draft
    python main.py --edit <name> --rom <file.gb>  # ...its tiles in the cartridge's own art
    python main.py --edit <name> --enhanced       # a new draft in the enhanced vocabulary
    python tools/editor/ui.py <name>

**Built the way Pyxel's own editor is built**, on its toolkit vendored in
`widgets/`: the window is a tree of widgets, and the map and the palette are
two of them. The toolkit is what knows a click from a drag, keeps a drag on the
widget it started on however far the pointer wanders, and repeats a held
scrollbar arrow -- which is why none of that is written here.

**What is in hand is whatever was last picked from the palette** -- a piece, or
a metatile on its own -- and the map does the obvious thing with it:

- a **click** stamps it with its top-left cell there, **on top** of everything:
  what the pane then shows is the merge the game will build, because the ghost
  under the pointer is already drawn merged;
- a **drag along the row** repeats it, a piece's width at a time, as one undo;
- the **right button** takes away what is on top of a cell -- a crate, a
  stretch where the computer's bike is put back, then the last stamping -- and
  dragging it keeps taking;
- **ALT and a click** picks up what is on top of a cell;
- from the **things** tab, a click puts down a crate, and a drag along the
  surface lays a **respawn** stretch for the computer's bike.

**The order is the merge**, so it can be seen and changed: `TAB` walks the
stampings stacked under the pointer, and `[` and `]` move the one chosen -- the
top one if none is -- below or above the next one it overlaps.

The scrollbars, the wheel (`SHIFT` for across), the arrows and the middle button
move the view. `Z` switches between 1:1 and 2:1, `C` between the art and the
collision, `G` outlines what the game would show from the pointer and `O` is
the whole lap at once. The three clocks are on the toolbar. `R` rides what is
drawn, saved or not, in a window of its own. `CTRL-S` saves, `CTRL-Z` and
`CTRL-Y` undo and redo, and `ESC` leaves -- asking once first when there is
something unsaved. `H` lists every key.

Every click, edit and save goes to `./editor.log` (`--no-log`, `--log <path>`):
read it before believing a report about the editor.
"""

import math
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import pyxel  # noqa: E402

from game import paths  # noqa: E402
from game.constants import TILE  # noqa: E402
from game.course import (  # noqa: E402
    COLS, DEGREES, LEVEL_LETTERS, METATILE_PX, METATILE_TILES, NOTHING, ROWS, Course)
from game.engine.original import LAP_LINE, START_X
from game.render import assets, rom_art  # noqa: E402
from game.render import style as palette_style  # noqa: E402
from game.rom.cartridge import Cartridge, NotTheCartridge  # noqa: E402
from game.trace import Trace, log_wanted  # noqa: E402
from maps import read  # noqa: E402
from tools.editor import palette, view  # noqa: E402
from tools.editor.document import ITEM_KINDS, Document  # noqa: E402
from tools.editor.map_file import MapFile  # noqa: E402
from tools.editor.view import (  # noqa: E402
    ENTRIES, MAP, PALETTE, PALETTE_BAR, SCROLL, STATUS, VSCROLL, Entry, Rect)
from tools.editor.widgets import NumberPicker, ScrollBar, TextButton, Widget  # noqa: E402
from tools.label_vocab import METATILE_KINDS, PIECE_KINDS  # noqa: E402

DEFAULT_LOG = paths.user_path("editor.log")
#: Where what is drawn is written for `R` to ride, saved or not: beside the
#: game's other writes and outside `maps/`, so it is never listed as a course.
RIDE_FILE = paths.user_path("editor-ride.json")

#: The things tab: the crates by the letter the engine counts them by, and the
#: stretch the computer's bike is put back on.
RESPAWN = "respawn"
THINGS = (*ITEM_KINDS, RESPAWN)
#: What each thing is, for the status line: the crates, the two secrets -- which
#: are not in the map and are taken upside down -- and the respawn stretches,
#: the orange lines along the ground.
THING_WORDS = {"s": "crate S: a higher top speed", "t": "crate T: ten more seconds",
               "n": "crate N: four more nitros", "r": "crate R: no slowing uphill",
               "j": "secret J: invisible, taken upside down -- nitro in the air",
               "mini": "secret mini-maniac: invisible, taken upside down",
               RESPAWN: "respawn: drag along the ground -- where the computer's "
                        "bike is put back when it falls behind (orange)"}
#: What the game shows around the bike, from the camera's own anchors: the bike
#: this far in from the view's left and down from its top, and the view's size.
GAME_LEFT, GAME_TOP, GAME_W, GAME_H = 32, 104, 160, 128
#: How far one notch of the wheel moves the palette, in pixels.
WHEEL_PX = 16

#: What `H` shows over the map: every key and every gesture, one line each.
HELP = (
    ("click", "stamp what is in hand, on top"),
    ("drag along a row", "repeat it, one undo"),
    ("right click / drag", "take away what is on top"),
    ("ALT + click", "pick up what is on top"),
    ("things: drag", "a respawn stretch for the computer's bike"),
    ("TAB / [ / ]", "walk the stack / lower / raise"),
    ("wheel, SHIFT-wheel", "scroll down, across"),
    ("arrows, middle drag", "move the view; SHIFT moves further"),
    ("Z / C / G / O", "zoom / collision / game view / whole lap"),
    ("R", "ride it"),
    ("CTRL-S", "save"),
    ("CTRL-Z / CTRL-Y", "undo / redo"),
    ("H", "this help"),
    ("ESC", "leave, asking once if unsaved"),
)


class Hand(NamedTuple):
    """What a click on the map puts down: which tab it came from, and its name."""

    tab: str
    name: str


class Editor(Widget):  # type: ignore[misc]
    """The root widget: the document, what is in hand, and the two panes."""

    def __init__(self, name: str, log: str | None = DEFAULT_LOG,
                 where: read.Where | None = None, rom: str | None = None,
                 enhanced: bool = False) -> None:
        super().__init__(None, 0, 0, view.WINDOW_W, view.WINDOW_H)
        #: The cartridge file the tiles are shown in, if there is one: `R`
        #: hands it on, so the race is drawn in the same art as the editor.
        self.rom = rom
        self.file = MapFile.named(name, enhanced=enhanced)
        existing = self.file.read()
        #: The vocabulary the course is written in: the one its place says,
        #: unless the caller hands one over.
        self.where = where if where is not None else self.file.vocabulary
        self.enhanced = self.where == read.ENHANCED_VOCABULARY
        self.doc = Document(read.tileset(self.where), read.pieces(self.where),
                            read.tables(self.where), existing)
        self.trace = Trace(log, frame=lambda: pyxel.frame_count)
        self.trace.note("open", name=name, path=self.file.path, new=existing is None)
        self.view = view.View()
        # An enhanced course's own pieces and metatiles are a tab of their own,
        # so the original's stay where an author knows to look for them.
        every = read.pieces(self.where)
        own = set(read.own(self.where, read.PIECES)) | set(read.own(self.where, read.METATILES))
        self.tabs = view.ENHANCED_TAB_NAMES if self.enhanced else view.TAB_NAMES
        #: A name a person can read, and a kind to group by, for every metatile
        #: and piece (`maps/labels.json`) -- the ids are the original's numbers.
        self.labels = read.labels(self.where)
        self.groups = {
            "pieces": self._grouped("pieces", set(every) - own, PIECE_KINDS),
            "metatiles": self._grouped("metatiles", set(self.doc.offered) - set(every) - own,
                                       METATILE_KINDS),
            view.EXTRA: [("", sorted(own & set(self.doc.offered)))],
            "things": [("", list(THINGS))]}
        self.contents = {tab: [name for _, names in groups for name in names]
                         for tab, groups in self.groups.items()}
        #: What the pointer is over in the palette, said on the status line.
        self.pointing: str | None = None
        self.tab = self.tabs[0]
        first = self.contents["pieces"] or self.contents["metatiles"]
        self.hand: Hand | None = Hand(self.tabs[0], first[0]) if first else None
        self.message = ("new course" if existing is None
                        else "opened %s" % paths.short(self.file.path))
        self.quitting = False
        self.show_help = False
        #: The stamping `TAB` chose under the pointer, by its place in the list.
        self.chosen: int | None = None
        self.collision = False
        self.game_frame = False
        self.overview = False

        self._build_toolbar()
        self.map_panel = MapPanel(self)
        self.palette_panel = PalettePanel(self)
        self.add_event_listener("update", self.__on_update)
        self.add_event_listener("draw", self.__on_draw)

    # -- the toolbar ------------------------------------------------------------

    def _build_toolbar(self) -> None:
        x = 2
        for label, action in (("save", self.save), ("undo", self.undo),
                              ("redo", self.redo), ("ride", self.ride),
                              ("help", self.toggle_help)):
            button = TextButton(self, x, 3, text=label)
            button.add_event_listener("press", action)
            x += button.width + 3
        x += 12
        #: Where each clock's letter is written, and the pickers beside them.
        self.clock_x: list[int] = []
        self.clocks: list[Any] = []
        for level in range(len(LEVEL_LETTERS)):
            self.clock_x.append(x)
            limit = int(self.doc.data["limits"][level])
            picker = NumberPicker(self, x + 8, 3, min_value=1, max_value=999, value=limit)
            picker.add_event_listener("change", self._on_clock(level))
            self.clocks.append(picker)
            x += 8 + picker.width + 8

    def _on_clock(self, level: int) -> Any:
        def changed(value: int) -> None:
            self.doc.set_limit(level, value)
            self.trace.note("clock", level=LEVEL_LETTERS[level], seconds=value)
        return changed

    def _sync_clocks(self) -> None:
        """Undo puts the file back, clocks included, so the pickers follow it."""
        for level, picker in enumerate(self.clocks):
            value = int(self.doc.data["limits"][level])
            if picker.value_var != value:
                picker.value_var = value

    # -- what the author asks for, each said once --------------------------------

    def save(self) -> None:
        path = self.file.write(self.doc.text())
        self.message = "saved %s" % paths.short(path)
        self.trace.note("save", path=path, stampings=len(self.doc.stampings))

    def undo(self) -> None:
        self.message = "undone" if self.doc.undo() else "nothing to undo"
        self._sync_clocks()
        self.trace.note("undo", revision=self.doc.revision)

    def redo(self) -> None:
        self.message = "redone" if self.doc.redo() else "nothing to redo"
        self._sync_clocks()
        self.trace.note("redo", revision=self.doc.revision)

    def toggle_help(self) -> None:
        self.show_help = not self.show_help

    def ride(self) -> None:
        """Ride what is drawn, in a window of its own: Pyxel has one window a
        process, so the race is another process, on a copy written aside."""
        os.makedirs(os.path.dirname(RIDE_FILE), exist_ok=True)
        with open(RIDE_FILE, "w") as handle:
            handle.write(self.doc.text())
        command = ([sys.executable] if paths.frozen()
                   else [sys.executable, os.path.join(ROOT, "main.py")])
        rom = ["--rom", self.rom] if self.rom else []
        enhanced = ["--enhanced"] if self.enhanced else []
        subprocess.Popen(command + ["--ride", RIDE_FILE] + rom + enhanced, cwd=ROOT)
        self.message = "riding it in another window"
        self.trace.note("ride", path=RIDE_FILE, stampings=len(self.doc.stampings))

    def show_tab(self, tab: str) -> None:
        self.tab = tab
        self.trace.note("tab", tab=tab)

    def pick(self, hand: Hand) -> None:
        self.hand = hand
        self.tab = hand.tab
        if hand.tab == "things":
            self.message = ("drag along a surface: the computer's bike is put back there"
                            if hand.name == RESPAWN else "crate %s" % hand.name)
        else:
            rows, cols = self.doc.size(hand.name)
            self.message = "%s (%dx%d)" % (hand.name, cols, rows)
        self.trace.note("pick", tab=hand.tab, name=hand.name)

    def hand_for(self, name: str) -> Hand:
        """The tab a name lives on: a piece where there is one, else a metatile."""
        for tab in self.tabs:
            if name in self.contents[tab]:
                return Hand(tab, name)
        return Hand("metatiles", name)

    def stamp(self, row: int, col: int, amend: bool = False) -> None:
        if self.hand is None:
            return
        self.doc.stamp(row, col, self.hand.name, amend=amend)
        self.message = "stamped %s" % self.hand.name
        self.trace.note("stamp", name=self.hand.name, row=row, col=col, run=amend,
                        stack=self.stack_names(row, col))

    def remove(self, row: int, col: int, wx: int, wy: int) -> None:
        """Take away what is on top here: a crate, a stretch, then a stamping."""
        at = self.doc.teleport_at(wx, wy)
        if at is not None and self.doc.item_at(row, col) is None:
            self.doc.remove_teleport(at)
            self.message = "took away a respawn stretch"
            self.trace.note("remove", row=row, col=col, what="respawn")
            return
        before = self.stack_names(row, col)
        crate = self.doc.item_at(row, col) is not None
        gone = self.doc.remove_top(row, col)
        what = "crate" if crate else before[-1] if gone and before else None
        self.message = "took away %s" % what if what else "nothing there"
        self.trace.note("remove", row=row, col=col, stack=before, what=what)

    def eyedrop(self, row: int, col: int) -> None:
        at = self.doc.top(row, col)
        if at is None:
            self.message = "nothing there to pick up"
            return
        self.pick(self.hand_for(self.doc.stampings[at][2]))

    def walk_stack(self, row: int, col: int) -> None:
        """Choose the next stamping down the stack under the pointer, from the top."""
        stack = self.doc.stack(row, col)
        if not stack:
            self.chosen = None
            return
        at = stack.index(self.chosen) if self.chosen in stack else len(stack)
        self.chosen = stack[(at - 1) % len(stack)]
        name = self.doc.stampings[self.chosen][2]
        self.message = "chosen %s (%d of %d from the top)" % (
            name, len(stack) - stack.index(self.chosen), len(stack))

    def reorder(self, cell: tuple[int, int], move: Any) -> None:
        """Lower or raise the chosen stamping, or the one on top of the cell."""
        at = self.chosen if self.chosen is not None else self.doc.top(*cell)
        if at is None:
            self.message = "nothing there to move"
            return
        name = self.doc.stampings[at][2]
        moved = move(at)
        self.chosen = moved
        self.message = ("%s moved to %d of %d" % (name, moved + 1, len(self.doc.stampings))
                        if moved != at else "%s overlaps nothing further that way" % name)
        self.trace.note("reorder", name=name, was=at, now=moved)

    def stack_names(self, row: int, col: int) -> list[str]:
        return [self.doc.stampings[at][2] for at in self.doc.stack(row, col)]

    def _grouped(self, section: str, names: "set[str]",
                 kinds: Sequence[str]) -> list[tuple[str, list[str]]]:
        """`names` by kind, in the kinds' order; whatever has no label last."""
        labels = self.labels.get(section, {})
        order = {kind: at for at, kind in enumerate(kinds)}
        groups: dict[str, list[str]] = {}
        for name in sorted(names):
            groups.setdefault(labels.get(name, {}).get("kind", "other"), []).append(name)
        return sorted(groups.items(), key=lambda group: order.get(group[0], len(order)))

    def label(self, name: str) -> str:
        """What a metatile or a piece is called, and its id: `up 45 full (m0c)`."""
        for section in ("pieces", "metatiles"):
            label = self.labels.get(section, {}).get(name)
            if label:
                return "%s (%s)" % (label["name"], name)
        return THING_WORDS.get(name, name)

    def set_zoom(self, zoom: int) -> None:
        self.view.zoom = zoom
        self.map_panel.fit_bars()
        self.message = "%d:1" % zoom

    # -- keys -------------------------------------------------------------------

    def __on_update(self) -> None:
        ctrl = pyxel.btn(pyxel.KEY_CTRL)
        for key, action in (self._ctrl_keys() if ctrl else self._plain_keys()):
            if pyxel.btnp(key):
                action()
        cell = self.view.cell_at(pyxel.mouse_x, pyxel.mouse_y)
        if cell is not None:
            self._stack_keys(cell)
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._leave()

    def _ctrl_keys(self) -> "tuple[tuple[int, Callable[[], None]], ...]":
        return ((pyxel.KEY_S, self.save), (pyxel.KEY_Z, self.undo), (pyxel.KEY_Y, self.redo))

    def _plain_keys(self) -> "tuple[tuple[int, Callable[[], None]], ...]":
        return ((pyxel.KEY_Z, self.toggle_zoom), (pyxel.KEY_H, self.toggle_help),
                (pyxel.KEY_C, self.toggle_collision), (pyxel.KEY_G, self.toggle_game_frame),
                (pyxel.KEY_O, self.toggle_overview), (pyxel.KEY_R, self.ride))

    def _stack_keys(self, cell: "tuple[int, int]") -> None:
        """TAB walks what is stacked under the pointer; `[` and `]` move it."""
        if pyxel.btnp(pyxel.KEY_TAB):
            self.walk_stack(*cell)
        for key, move in ((pyxel.KEY_LEFTBRACKET, self.doc.lower),
                          (pyxel.KEY_RIGHTBRACKET, self.doc.raise_)):
            if pyxel.btnp(key):
                self.reorder(cell, move)

    def _leave(self) -> None:
        """ESC: out, or -- with something unsaved -- a warning first."""
        dirty = self.file.dirty(self.doc.text())
        if dirty and not self.quitting:
            self.quitting = True
            self.message = "unsaved changes: ESC again to leave, CTRL-S to save"
        else:
            self.trace.note("quit", dirty=dirty)
            pyxel.quit()

    def toggle_zoom(self) -> None:
        self.set_zoom(2 if self.view.zoom == 1 else 1)

    def toggle_collision(self) -> None:
        self.collision = not self.collision
        self.message = "collision" if self.collision else "art"

    def toggle_game_frame(self) -> None:
        self.game_frame = not self.game_frame

    def toggle_overview(self) -> None:
        self.overview = not self.overview

    # -- pictures, shared by both panes -------------------------------------------

    def picture_size(self, name: str) -> tuple[int, int]:
        if name in THINGS:
            return METATILE_PX, METATILE_PX
        rows, cols = self.doc.size(name)
        return cols * METATILE_PX, rows * METATILE_PX

    def tile(self, name: str, x: int, y: int, zoom: int = 1) -> None:
        u, v = assets.terrain_uv(name)
        shift = TILE * (zoom - 1) // 2
        pyxel.blt(x + shift, y + shift, assets.TERRAIN_BANK, u, v, TILE, TILE,
                  palette.SKY_INDEX, rotate=0.0, scale=float(zoom))

    def metatile(self, course: Course, metatile: int, x: int, y: int, zoom: int = 1) -> None:
        for index, tile in enumerate(course.tiles(metatile)):
            name = course.tile_name(tile)
            if name is not None:
                self.tile(name, x + (index % METATILE_TILES) * TILE * zoom,
                          y + (index // METATILE_TILES) * TILE * zoom, zoom)

    def piece_picture(self, name: str, x: int, y: int) -> None:
        """A piece as it would be stamped on nothing: built on its own, so a
        transparent corner shows the sky it would let through."""
        data = {"pieces": [[0, 0, name]], "items": [], "limits": [1.0] * 3, "teleports": []}
        course = self.doc.build(data)
        for down, line in enumerate(self.doc.offered[name]):
            for along, metatile in enumerate(line):
                if metatile != NOTHING:
                    self.metatile(course, course.metatile(down, along),
                                  x + along * METATILE_PX, y + down * METATILE_PX)

    def __on_draw(self) -> None:
        pyxel.cls(palette.CHROME_BACK)
        for level, x in enumerate(self.clock_x):
            pyxel.text(x, 4, LEVEL_LETTERS[level], palette.CHROME_TEXT)
        cell = self.view.cell_at(pyxel.mouse_x, pyxel.mouse_y)
        dirty = "*" if self.file.dirty(self.doc.text()) else ""
        where = ""
        if self.pointing is not None:
            where = self.pointing
        elif cell is not None:
            stack = [self.label(name) for name in self.stack_names(*cell)]
            where = "row %d col %d%s" % (cell[0], cell[1],
                                         " [%s]" % " < ".join(stack) if stack else "")
        text = "%s%s  %d stamped  %s  %s" % (self.file.name, dirty, len(self.doc.stampings),
                                             where, self.message)
        pyxel.text(STATUS.x + 2, STATUS.y + 3, text, palette.CHROME_TEXT)


class MapPanel(Widget):  # type: ignore[misc]
    """The course, drawn as the game builds it, and the one place a stamping
    gets made. Its scrollbars are where the view is."""

    def __init__(self, editor: Editor) -> None:
        super().__init__(editor, MAP.x, MAP.y, MAP.w + VSCROLL.w, MAP.h + SCROLL.h)
        self.editor = editor
        # A child is placed relative to its parent, which is the toolkit's rule.
        self.h_bar = ScrollBar(self, SCROLL.x - MAP.x, SCROLL.y - MAP.y, width=SCROLL.w,
                               scroll_amount=COLS, slider_amount=1, value=0)
        self.v_bar = ScrollBar(self, VSCROLL.x - MAP.x, VSCROLL.y - MAP.y, height=VSCROLL.h,
                               scroll_amount=ROWS, slider_amount=ROWS, value=0)
        self.fit_bars()
        #: A drag repeating the hand along a row: the row, and the last column put.
        self._run: tuple[int, int] | None = None
        #: A respawn stretch being laid: the row, and the `x` it started at.
        self._stretch: tuple[int, int] | None = None
        #: The last cell a right-drag took something from.
        self._erasing: tuple[int, int] | None = None
        #: A middle-drag: the bars' values and the pointer where it began.
        self._pan_from: tuple[int, int, int, int] | None = None
        #: The ghost, built once per revision, hand and cell.
        self._ghost: tuple[Any, Course] | None = None
        self.add_event_listener("mouse_down", self.__on_mouse_down)
        self.add_event_listener("mouse_drag", self.__on_mouse_drag)
        self.add_event_listener("mouse_up", self.__on_mouse_up)
        self.add_event_listener("update", self.__on_update)
        self.add_event_listener("draw", self.__on_draw)

    @property
    def view(self) -> view.View:
        return self.editor.view

    @property
    def doc(self) -> Document:
        return self.editor.doc

    def fit_bars(self) -> None:
        """What each bar can reach, for the zoom: every column and every row."""
        for bar, amount, shown in ((self.h_bar, COLS, self.view.columns_in_view()),
                                   (self.v_bar, ROWS, self.view.rows_in_view())):
            bar.slider_amount = max(1, min(amount, shown))
            bar.value_var = max(0, min(bar.value_var, amount - bar.slider_amount))

    def scroll(self, dcol: int, drow: int) -> None:
        for bar, step in ((self.h_bar, dcol), (self.v_bar, drow)):
            if step:
                bar.value_var = max(0, min(bar.value_var + step,
                                           bar.scroll_amount - bar.slider_amount))

    # -- events -----------------------------------------------------------------

    def __on_mouse_down(self, key: int, x: int, y: int) -> None:
        editor = self.editor
        if not MAP.contains(x, y):
            return
        if editor.overview:
            if key == pyxel.MOUSE_BUTTON_LEFT:
                self._leave_overview(x, y)
            return
        if key == pyxel.MOUSE_BUTTON_MIDDLE:
            self._pan_from = (self.h_bar.value_var, self.v_bar.value_var, x, y)
            return
        cell = self.view.cell_at(x, y)
        world = self.view.world_at(x, y)
        if cell is None or world is None:
            return
        row, col = cell
        editor.quitting = False
        editor.chosen = None
        if key == pyxel.MOUSE_BUTTON_RIGHT:
            self._erasing = cell
            editor.remove(row, col, *world)
            return
        if key != pyxel.MOUSE_BUTTON_LEFT:
            return
        if pyxel.btn(pyxel.KEY_ALT):
            editor.eyedrop(row, col)
        else:
            self._put_down(row, col, world[0])

    def _leave_overview(self, x: int, y: int) -> None:
        """A click on the whole lap: the map scrolled to it, and the lap closed."""
        wx = _overview_x(x, y)
        if wx is not None:
            self.h_bar.value_var = 0
            self.scroll(wx // METATILE_PX - self.view.columns_in_view() // 2, 0)
            self.editor.overview = False

    def _put_down(self, row: int, col: int, world_x: int) -> None:
        """What is in hand, clicked onto the map: a stamp, a crate, or the start
        of a stretch for the computer's bike."""
        editor = self.editor
        hand = editor.hand
        if hand is None:
            return
        if hand.tab != "things":
            editor.stamp(row, col)
            self._run = (row, col)
        elif hand.name == RESPAWN:
            self._stretch = (row, world_x)
        else:
            self.doc.put_item(hand.name, row, col)
            editor.message = "crate %s" % hand.name
            editor.trace.note("item", crate=hand.name, row=row, col=col)

    def __on_mouse_drag(self, key: int, x: int, y: int, dx: int, dy: int) -> None:
        if key == pyxel.MOUSE_BUTTON_MIDDLE and self._pan_from is not None:
            h, v, from_x, from_y = self._pan_from
            size = METATILE_PX * self.view.zoom
            self.h_bar.value_var = h
            self.v_bar.value_var = v
            self.scroll((from_x - x) // size, (from_y - y) // size)
            return
        cell = self.view.cell_at(x, y)
        if cell is None:
            return
        if key == pyxel.MOUSE_BUTTON_RIGHT and self._erasing is not None:
            if cell != self._erasing:
                self._erasing = cell
                world = self.view.world_at(x, y)
                if world is not None:
                    self.editor.remove(cell[0], cell[1], *world)
            return
        if key == pyxel.MOUSE_BUTTON_LEFT and self._run is not None:
            self._extend_run(cell)

    def __on_mouse_up(self, key: int, x: int, y: int) -> None:
        if key == pyxel.MOUSE_BUTTON_LEFT and self._stretch is not None:
            self._lay_stretch(x, y)
        self._run = None
        self._stretch = None
        self._erasing = None
        self._pan_from = None

    def __on_update(self) -> None:
        self.view.col = self.h_bar.value_var
        self.view.row = self.v_bar.value_var
        if self.is_hit(pyxel.mouse_x, pyxel.mouse_y) and pyxel.mouse_wheel:
            # Down the pane, or across it when there is nothing below to see --
            # which at 1:1 is always, a course being shorter than the pane.
            across = pyxel.btn(pyxel.KEY_SHIFT) or self.v_bar.slider_amount >= ROWS
            step = -pyxel.mouse_wheel * (4 if across else 1)
            self.scroll(step if across else 0, 0 if across else step)
        far = 8 if pyxel.btn(pyxel.KEY_SHIFT) else 1
        for key, dcol, drow in ((pyxel.KEY_LEFT, -far, 0), (pyxel.KEY_RIGHT, far, 0),
                                (pyxel.KEY_UP, 0, -far), (pyxel.KEY_DOWN, 0, far)):
            if pyxel.btnp(key, hold=8, repeat=2):
                self.scroll(dcol, drow)

    def _lay_stretch(self, x: int, y: int) -> None:
        """Let go of a respawn drag: the stretch runs from where it started to
        where it ended, on the row it started on, and the bike stands on the
        middle of that row -- which is a road's surface."""
        assert self._stretch is not None
        row, start = self._stretch
        world = self.view.world_at(x, y)
        end = world[0] if world is not None else start
        editor = self.editor
        if abs(end - start) < METATILE_PX:
            editor.message = "a respawn stretch is a drag along the surface, not a click"
            return
        top = row * METATILE_PX + METATILE_PX // 2 - METATILE_PX
        self.doc.add_teleport(start, end, top)
        editor.message = "respawn stretch %d to %d" % (min(start, end), max(start, end))
        editor.trace.note("respawn", start=start, end=end, y=top)

    def _extend_run(self, cell: tuple[int, int]) -> None:
        """Put the hand down again each time the pointer is a whole piece further
        along the row it started on, either way."""
        assert self._run is not None
        hand = self.editor.hand
        if hand is None:
            return
        row, last = self._run
        width = max(1, self.doc.size(hand.name)[1])
        ahead = (cell[1] - last) % COLS
        behind = (last - cell[1]) % COLS
        if width <= ahead < COLS // 2:
            last = (last + width) % COLS
        elif width <= behind < COLS // 2:
            last = (last - width) % COLS
        else:
            return
        self.editor.stamp(row, last, amend=True)
        self._run = (row, last)

    # -- drawing ----------------------------------------------------------------

    def _ghost_course(self, cell: tuple[int, int]) -> Course:
        """The course as it would be with the hand stamped at `cell`."""
        hand = self.editor.hand
        assert hand is not None
        key = (self.doc.revision, hand, cell)
        if self._ghost is None or self._ghost[0] != key:
            data = dict(self.doc.data, pieces=self.doc.stampings + [[cell[0], cell[1],
                                                                     hand.name]])
            self._ghost = (key, self.doc.build(data))
        return self._ghost[1]

    def _ghost_footprint(self, cell: tuple[int, int] | None) -> set[tuple[int, int]]:
        hand = self.editor.hand
        if cell is None or hand is None or self._run is not None or hand.tab == "things":
            return set()
        return set(self.doc.cells(cell[0], cell[1], hand.name))

    def __on_draw(self) -> None:
        editor = self.editor
        pyxel.clip(MAP.x, MAP.y, MAP.w, MAP.h)
        pyxel.rect(MAP.x, MAP.y, MAP.w, MAP.h, palette.CHROME_BACK)
        zoom = self.view.zoom
        size = METATILE_PX * zoom
        top = MAP.y - self.view.y * zoom
        pyxel.rect(MAP.x, top, MAP.w, ROWS * size, palette.SHADE_BASE + palette.SKY_INDEX)
        cell = self.view.cell_at(pyxel.mouse_x, pyxel.mouse_y)
        course = self.doc.built()
        self._draw_cells(course, cell, zoom)
        if editor.collision:
            self._directions(course, zoom)
        self._draw_lines(top, ROWS * size)
        self._draw_things(size)
        self._draw_chosen(size)
        self._draw_pointer(cell, size)
        if editor.game_frame:
            self._draw_game_frame()
        if editor.overview:
            self._draw_overview()
        if editor.show_help:
            self._draw_help()
        pyxel.clip()

    def _draw_cells(self, course: Course, cell: "tuple[int, int] | None", zoom: int) -> None:
        """Every cell in view -- and under the pointer, the course as it would be
        with what is in hand stamped there."""
        editor = self.editor
        ghost = self._ghost_footprint(cell)
        palette.user_pal()
        for unwrapped in self.view.visible():
            col = unwrapped % COLS
            for row in range(ROWS):
                x, y = self.view.screen_of(row, col)
                drawn = self._ghost_course(cell) if cell and (row, col) in ghost else course
                if editor.collision:
                    self._collision(drawn, drawn.metatile(row, col), x, y, zoom)
                else:
                    editor.metatile(drawn, drawn.metatile(row, col), x, y, zoom)
        pyxel.pal()

    def _draw_pointer(self, cell: "tuple[int, int] | None", size: int) -> None:
        """The footprint of what is in hand, and a stretch being dragged out."""
        hand = self.editor.hand
        if cell is not None and hand is not None and hand.tab != "things" and self._run is None:
            rows, cols = self.doc.size(hand.name)
            x, y = self.view.screen_of(*cell)
            pyxel.rectb(x, y, cols * size, min(rows, ROWS - cell[0]) * size, palette.GHOST)
        if self._stretch is not None:
            row, start = self._stretch
            world = self.view.world_at(pyxel.mouse_x, pyxel.mouse_y)
            end = world[0] if world is not None else start
            y = self.view.screen_y(row * METATILE_PX + METATILE_PX // 2)
            pyxel.line(self.view.screen_x(min(start, end)), y,
                       self.view.screen_x(max(start, end)), y, palette.RESPAWN)

    def _collision(self, course: Course, metatile: int, x: int, y: int, zoom: int) -> None:
        """A metatile as the bike feels it, shaded as the game shades a course
        it has no art for: sand, level ground, and anything that slopes."""
        for index, tile in enumerate(course.tiles(metatile)):
            hit = course.collision(tile)
            if not hit.solid:
                continue
            shade = (palette_style.BULK if hit.soft else palette_style.EDGE
                     if hit.direction == 0 else palette_style.RIM)
            pyxel.rect(x + (index % METATILE_TILES) * TILE * zoom,
                       y + (index // METATILE_TILES) * TILE * zoom,
                       TILE * zoom, TILE * zoom, palette.SHADE_BASE + shade)

    def _directions(self, course: Course, zoom: int) -> None:
        """A tick on each tile that is not level, pointing the way it is ridden."""
        for unwrapped in self.view.visible():
            col = unwrapped % COLS
            for row in range(ROWS):
                x, y = self.view.screen_of(row, col)
                for index, tile in enumerate(course.tiles(course.metatile(row, col))):
                    hit = course.collision(tile)
                    if not hit.solid or hit.direction == 0:
                        continue
                    cx = x + (index % METATILE_TILES) * TILE * zoom + TILE * zoom // 2
                    cy = y + (index // METATILE_TILES) * TILE * zoom + TILE * zoom // 2
                    angle = math.radians(hit.direction * DEGREES)
                    reach = 3 * zoom
                    pyxel.line(cx, cy, cx + round(reach * math.cos(angle)),
                               cy - round(reach * math.sin(angle)), palette.CURVE)

    def _draw_lines(self, top: int, height: int) -> None:
        """Where a race starts, and the lap line -- fixed by the engine, drawn so
        an author can see where the course has to begin and end."""
        for wx, label, colour in ((START_X, "start", palette.NORMAL),
                                  (LAP_LINE, "lap", palette.MARK)):
            x = self.view.screen_x(wx)
            if MAP.x <= x < MAP.x + MAP.w:
                pyxel.line(x, top, x, top + height - 1, colour)
                pyxel.text(x + 2, top + 2, label, colour)

    def _draw_things(self, size: int) -> None:
        for kind, row, col in self.doc.items:
            x, y = self.view.screen_of(row, col)
            pyxel.rectb(x, y, size, size, palette.MARK)
            pyxel.text(x + size // 2 - 1, y + size // 2 - 2, kind[0].upper(), palette.MARK)
        for start, end, height in self.doc.teleports:
            y = self.view.screen_y(height + METATILE_PX)
            left, right = self.view.screen_x(start), self.view.screen_x(end)
            if right < left:
                right = left + (end - start) * self.view.zoom
            pyxel.line(left, y, right, y, palette.RESPAWN)
            pyxel.line(left, y - 3, left, y + 3, palette.RESPAWN)
            pyxel.line(right, y - 3, right, y + 3, palette.RESPAWN)

    def _draw_chosen(self, size: int) -> None:
        editor = self.editor
        if editor.chosen is None or editor.chosen >= len(self.doc.stampings):
            editor.chosen = None
            return
        row, col, name = self.doc.stampings[editor.chosen]
        rows, cols = self.doc.size(name)
        x, y = self.view.screen_of(row, col)
        pyxel.rectb(x - 1, y - 1, cols * size + 2, min(rows, ROWS - row) * size + 2, palette.MARK)

    def _draw_game_frame(self) -> None:
        """What the game would show with the bike at the pointer: the camera's
        own anchors, and the band under the view."""
        world = self.view.world_at(pyxel.mouse_x, pyxel.mouse_y)
        if world is None:
            return
        zoom = self.view.zoom
        x = self.view.screen_x(world[0] - GAME_LEFT)
        y = self.view.screen_y(world[1] - GAME_TOP)
        pyxel.rectb(x, y, GAME_W * zoom, GAME_H * zoom, palette.NORMAL)
        pyxel.rectb(x, y + GAME_H * zoom, GAME_W * zoom, 16 * zoom, palette.NORMAL)

    def _draw_overview(self) -> None:
        """The whole lap as the bike feels it, in two halves of a pixel a tile,
        with the view's edges on it. A click takes the view there."""
        course = self.doc.built()
        pyxel.rect(MAP.x, MAP.y, MAP.w, OVERVIEW_H * 2 + 30, palette.CHROME_BACK)
        pyxel.text(MAP.x + 4, MAP.y + 4, "the whole lap: click to go there, O to close",
                   palette.CHROME_TEXT)
        half = COLS // 2 * METATILE_TILES
        for strip in (0, 1):
            pyxel.rect(OVERVIEW_X, OVERVIEW_Y + strip * (OVERVIEW_H + 8), half, OVERVIEW_H,
                       palette.SHADE_BASE + palette.SKY_INDEX)
        for tile_col in range(COLS * METATILE_TILES):
            strip, along = divmod(tile_col, half)
            y0 = OVERVIEW_Y + strip * (OVERVIEW_H + 8)
            for tile_row in range(ROWS * METATILE_TILES):
                metatile = course.metatile(tile_row // 2, tile_col // 2)
                hit = course.collision(course.tiles(metatile)[(tile_row % 2) * 2 + tile_col % 2])
                if hit.solid:
                    shade = palette_style.BULK if hit.soft else palette_style.EDGE
                    pyxel.pset(OVERVIEW_X + along, y0 + tile_row, palette.SHADE_BASE + shade)
        first = self.view.x // TILE
        for tile_col in (first, first + self.view.columns_in_view() * METATILE_TILES):
            strip, along = divmod(tile_col % (COLS * METATILE_TILES), half)
            y0 = OVERVIEW_Y + strip * (OVERVIEW_H + 8)
            pyxel.line(OVERVIEW_X + along, y0 - 2, OVERVIEW_X + along, y0 + OVERVIEW_H + 1,
                       palette.GHOST)

    def _draw_help(self) -> None:
        key_w = max(view.label_w(key) for key, _ in HELP) + 12
        w = key_w + max(view.label_w(what) for _, what in HELP) + 12
        h = len(HELP) * 10 + 22
        x, y = MAP.x + (MAP.w - w) // 2, MAP.y + (MAP.h - h) // 2
        pyxel.rect(x, y, w, h, palette.CHROME_BACK)
        pyxel.rectb(x, y, w, h, palette.CHROME_TEXT)
        pyxel.text(x + 6, y + 6, "keys  (H to close)", palette.CHROME_TEXT)
        for index, (key, what) in enumerate(HELP):
            line = y + 18 + index * 10
            pyxel.text(x + 6, line, key, palette.MARK)
            pyxel.text(x + key_w, line, what, palette.CHROME_TEXT)


class PalettePanel(Widget):  # type: ignore[misc]
    """Everything that can be put down, a tab of it at a time, each drawn at
    1:1 over its own footprint -- a piece shrunk to an icon is another shape.
    What does not fit scrolls, by its own bar or the wheel."""

    def __init__(self, editor: Editor) -> None:
        super().__init__(editor, PALETTE.x, PALETTE.y, PALETTE.w, PALETTE.h)
        self.editor = editor
        self.boxes: dict[str, list[Rect]] = {}
        self.headings: dict[str, list[tuple[Rect, str]]] = {}
        for tab in editor.tabs:
            self.boxes[tab], self.headings[tab] = view.flow_groups(
                [(title, [Entry(name, *editor.picture_size(name)) for name in names])
                 for title, names in editor.groups[tab]])
        self.bar = ScrollBar(self, PALETTE_BAR.x - PALETTE.x, PALETTE_BAR.y - PALETTE.y,
                             height=PALETTE_BAR.h, scroll_amount=1, slider_amount=1, value=0)
        self._shown: str | None = None
        self.add_event_listener("mouse_down", self.__on_mouse_down)
        self.add_event_listener("update", self.__on_update)
        self.add_event_listener("draw", self.__on_draw)

    def entry_rect(self, box: Rect) -> Rect:
        """A palette box in window coordinates, for the tab's scroll."""
        return Rect(ENTRIES.x + box.x, ENTRIES.y + box.y - self.bar.value_var, box.w, box.h)

    def slot_rect(self, tab: str, name: str) -> Rect | None:
        """Where an entry is drawn now, or None when its tab is not the one up."""
        if tab != self.editor.tab:
            return None
        for box, entry in zip(self.boxes[tab], self.editor.contents[tab]):
            if entry == name:
                return self.entry_rect(box)
        return None

    def __on_mouse_down(self, key: int, x: int, y: int) -> None:
        if key != pyxel.MOUSE_BUTTON_LEFT:
            return
        tabs = self.editor.tabs
        for index, tab in enumerate(tabs):
            if view.tab_rect(index, len(tabs)).contains(x, y):
                self.editor.show_tab(tab)
                return
        tab = self.editor.tab
        if not ENTRIES.contains(x, y):
            return
        for box, name in zip(self.boxes[tab], self.editor.contents[tab]):
            if self.entry_rect(box).contains(x, y):
                self.editor.pick(Hand(tab, name))
                return

    def __on_update(self) -> None:
        tab = self.editor.tab
        if tab != self._shown:
            # A tab is its own height: the bar is re-measured and starts at the top.
            self._shown = tab
            self.bar.scroll_amount = max(1, view.flow_height(self.boxes[tab]))
            self.bar.slider_amount = max(1, min(self.bar.scroll_amount, ENTRIES.h))
            self.bar.value_var = 0
        self.editor.pointing = self._under(pyxel.mouse_x, pyxel.mouse_y)
        if self.is_hit(pyxel.mouse_x, pyxel.mouse_y) and pyxel.mouse_wheel:
            self.bar.value_var = max(0, min(self.bar.value_var - pyxel.mouse_wheel * WHEEL_PX,
                                            self.bar.scroll_amount - self.bar.slider_amount))

    def _draw_headings(self, tab: str) -> None:
        """Each kind's name over its group, and a rule across to the edge."""
        for rect, title in self.headings[tab]:
            if title:
                at = self.entry_rect(rect)
                pyxel.text(at.x, at.y, title.upper(), palette.MARK)
                pyxel.line(at.x + len(title) * view.FONT_W + 2, at.y + 2,
                           at.x + at.w, at.y + 2, palette.CHROME_TEXT)

    def _under(self, x: int, y: int) -> str | None:
        """What the entry under the pointer is, in words, or None."""
        if not ENTRIES.contains(x, y):
            return None
        tab = self.editor.tab
        for box, name in zip(self.boxes[tab], self.editor.contents[tab]):
            if self.entry_rect(box).contains(x, y):
                return self.editor.label(name)
        return None

    def __on_draw(self) -> None:
        editor = self.editor
        pyxel.rect(PALETTE.x, PALETTE.y, PALETTE.w, PALETTE.h, palette.CHROME_BACK)
        pyxel.rect(PALETTE.x, PALETTE.y, PALETTE.w, view.TAB_H, 0)
        for index, name in enumerate(editor.tabs):
            rect = view.tab_rect(index, len(editor.tabs))
            here = name == editor.tab
            if here:
                pyxel.rect(rect.x, rect.y, rect.w - 1, rect.h, palette.CHROME_BACK)
            pyxel.text(rect.x + 3, rect.y + 3, name, palette.MARK if here else palette.CHROME_TEXT)
        tab = editor.tab
        pyxel.clip(ENTRIES.x, ENTRIES.y, ENTRIES.w, ENTRIES.h)
        self._draw_headings(tab)
        for box, name in zip(self.boxes[tab], editor.contents[tab]):
            rect = self.entry_rect(box)
            if rect.y > ENTRIES.y + ENTRIES.h or rect.y + rect.h < ENTRIES.y:
                continue
            w, h = editor.picture_size(name)
            pyxel.rect(rect.x, rect.y, w + 2, h + 2, palette.SHADE_BASE + palette.SKY_INDEX)
            if tab == "things":
                colour = palette.RESPAWN if name == RESPAWN else palette.MARK
                pyxel.rectb(rect.x + 1, rect.y + 1, w, h, colour)
                pyxel.text(rect.x + w // 2 - 1, rect.y + h // 2 - 2,
                           "~" if name == RESPAWN else name[0].upper(), colour)
            else:
                palette.user_pal()
                editor.piece_picture(name, rect.x + 1, rect.y + 1)
                pyxel.pal()
            pyxel.text(rect.x + 1, rect.y + rect.h - view.FONT_H - 1, name, palette.CHROME_TEXT)
            if editor.hand == Hand(tab, name):
                pyxel.rectb(rect.x - 1, rect.y - 1, rect.w + 2, rect.h + 2, palette.GHOST)
        pyxel.clip()


#: The overview's two strips, a pixel a tile: where they start and how tall.
OVERVIEW_X = MAP.x + (MAP.w - COLS) // 2
OVERVIEW_Y = MAP.y + 16
OVERVIEW_H = ROWS * METATILE_TILES


def _overview_x(mx: int, my: int) -> int | None:
    """The course `x` under a click on the overview, or None off both strips."""
    half = COLS // 2 * METATILE_TILES
    along = mx - OVERVIEW_X
    if not 0 <= along < half:
        return None
    for strip in (0, 1):
        y0 = OVERVIEW_Y + strip * (OVERVIEW_H + 8)
        if y0 <= my < y0 + OVERVIEW_H:
            return (strip * half + along) * TILE
    return None


def rom_wanted(argv: Sequence[str]) -> tuple[str | None, list[str]]:
    """The cartridge file after `--rom`, and the argv with the two words taken out."""
    rest = list(argv)
    if "--rom" not in rest:
        return None, rest
    at = rest.index("--rom")
    if at + 1 >= len(rest):
        raise SystemExit("--rom takes a cartridge file")
    path = rest[at + 1]
    del rest[at:at + 2]
    return path, rest


def main(argv: Sequence[str]) -> int:
    log, rest = log_wanted(argv, DEFAULT_LOG)
    rom, rest = rom_wanted(rest)
    enhanced = "--enhanced" in rest
    rest = [word for word in rest if word != "--enhanced"]
    cartridge = None
    if rom is not None:
        try:
            cartridge = Cartridge.from_file(rom)
        except (OSError, NotTheCartridge) as refused:
            print("cannot read %s: %s" % (rom, refused))
            return 1
    name = rest[0] if rest else "draft"
    paths.make_chdir_target(__file__)
    pyxel.init(view.WINDOW_W, view.WINDOW_H, title="bmx-80 editor: %s" % name,
               fps=30, quit_key=pyxel.KEY_NONE)
    # The pointer is the system's own, and Pyxel hides it unless asked: without
    # this it shows only where something is drawn under it.
    pyxel.mouse(True)
    palette.install()
    if cartridge is not None:
        # The original's tiles in its own art, over this game's drawings of
        # them -- in the bank only, so nothing on the disk changes.
        rom_art.paint_terrain(cartridge)
    editor = Editor(name, log, rom=rom, enhanced=enhanced)
    if log:
        print("log: %s" % log)
    pyxel.run(editor.update_all, editor.draw_all)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
