"""FREE RIDE: any course, at any level, in any mode.

The original's own screens (`game/front.py`) ride the eight courses the way the
original does, in classic. This is the menu behind the title's FREE RIDE row,
with a cartridge or without one: the same eight, and the author's own drafts, in
whichever mode -- classic, or the experimental excessive -- and SOLO or against
the computer. It is also the whole of what `--ride` opens onto.

**A list per map directory**, which is the directories' own split arriving on the
screen: `maps/courses/` is the project's courses, `maps/enhanced/courses/` the
enhanced ones and `maps/drafts/` the author's own. Drawn as one run there is
nothing to say where one ends, so they are tabs, each keeping its own cursor.
Select puts the computer's bike in the race or takes it out.

**So there is one set of arrows and two things to choose with it**, and `focus`
is which of them has it. TAB hands over, and it hands over **all four keys**: a
course is a list with another list across from it, and a level is a row of three
walked either way. It is a mode you can see -- both halves are drawn at once with the live one filled in -- so nothing
has to be remembered between presses.

**Pyxel-free**, so what the menu *says* can be tested without a window, the same
split the rest of `game/` keeps: this is a cursor and a lookup, and
`game/render/menu_draw.draw_menu` is the picture of it. The records it reads are
`game/records.py`.
"""

from typing import Callable, Sequence

from game.course import LEVELS, START_LEVEL
from game import records as scoreboard
from game.engine.terrain import Ground
from game.mode import CLASSIC, MODES, Mode

COURSES, CUSTOM = "courses", "custom"

# What the up/down arrows are pointing at. Two things are chosen on this screen
# and there is one pair of arrows, so one of them is in hand at a time and TAB is
# what hands over -- which is the arrangement the author asked for once the
# left/right arrows became the two lists.
#
# It is a mode, and this screen has spent its whole life without one. What makes
# it an honest mode rather than the kind the editor keeps paying for is that both
# halves are on the screen at once and the picture says which is live: the
# highlight is filled where the arrows will land and an outline where they will
# not, so there is nothing to remember.
PICKING_COURSE, PICKING_LEVEL, PICKING_MODE = "course", "level", "mode"
FOCUS = (PICKING_COURSE, PICKING_LEVEL, PICKING_MODE)

# How many rows of the list the screen has room for.
#
# It lives here rather than beside the other menu positions in `menu_draw.py` because
# it is not a position: the model has to keep the cursor inside the window, so
# the picture reads this number rather than the two of them agreeing by hand and
# drifting the day the logo grows a row.
WINDOW = 6

# One row of a list: the name it is shown by and how to build it. A factory and
# not what it builds -- see `build`. **A `Ground`, whichever list it came from**:
# the original's courses read out of the player's cartridge, and this game's own
# once they are back, answer the engine the same way.
Listed = tuple[str, Callable[[], Ground]]


class Menu:
    """A cursor over the courses and the levels, and what it knows about them.

    Holds the scoreboard rather than reaching for it every frame, because the
    menu is also where a new record has just been written and re-reading the
    file to draw it would be reading back what this object already knows.
    """

    def __init__(self, tracks: Sequence[Listed], drafts: Sequence[Listed] | None = None,
                 records: scoreboard.Records | None = None,
                 path: str | None = None, mode: str = CLASSIC.name) -> None:
        # `[(label, [(name, factory)])]`: the eight courses, and the author's
        # drafts (`maps.DRAFTS`).
        #
        # **The drafts are a tab even when there are none**, because the tab is
        # also where the screen says how to make one: on a fresh clone, and for
        # every player of a build, it is empty. Only `--ride`, which is one
        # course and nothing else, hands over no drafts at all -- `None` -- and
        # gets no tab.
        self.sections: list[tuple[str, list[Listed]]] = [(COURSES, list(tracks))]
        if drafts is not None:
            self.sections.append((CUSTOM, list(drafts)))
        self.tab = 0
        self.focus = PICKING_COURSE
        # A cursor and a scroll offset per section, so wandering into the other
        # list and back does not lose your place in this one.
        self.cursors = [0] * len(self.sections)
        self.tops = [0] * len(self.sections)
        # Where the scoreboard is read from and written back to. A parameter so
        # a test can point it at a temporary file: a test that wrote the real one
        # would be scribbling on the player's times, and one that could not write
        # at all would leave the only part of this that touches a disk untested.
        self.path = scoreboard.PATH if path is None else path
        self.records = scoreboard.load(self.path) if records is None else records
        # `START_LEVEL` and deliberately not `DEFAULT_LEVEL`: the second is the
        # middle clock every course is balanced against, and this is a question
        # about the screen. See `game/course.py`.
        self.level = START_LEVEL
        # Whether the original's courses are raced against the computer's bike:
        # the original's Moto Mode, SOLO or VS COMPUTER, which its title screen
        # moves with Select.
        self.rival = False
        #: The way to play, by name (`game.mode.MODES`).
        if mode not in MODES:
            raise ValueError("no mode %r: there are %s" % (mode, ", ".join(MODES)))
        self.mode = mode

    # -- what is in hand ------------------------------------------------------

    @property
    def label(self) -> str:
        return self.sections[self.tab][0]

    @property
    def tracks(self) -> list[Listed]:
        """The list under the cursor. What the screen draws, and what every
        question below is asked of."""
        return self.sections[self.tab][1]

    @property
    def course(self) -> int:
        return self.cursors[self.tab]

    @course.setter
    def course(self, index: int) -> None:
        self.cursors[self.tab] = index
        self._scroll()

    @property
    def top(self) -> int:
        """The first row the window shows."""
        return self.tops[self.tab]

    # -- moving ---------------------------------------------------------------

    def move_course(self, step: int) -> None:
        """Wraps, because eight courses on a 144-pixel screen is a short list and
        walking off the end of a short list to get back to the top is worse than
        wrapping."""
        if not self.tracks:
            return
        self.course = (self.course + step) % len(self.tracks)

    def move_section(self, step: int) -> None:
        """The next list round. A no-op when there is only one, which is a clone
        with no drafts."""
        self.tab = (self.tab + step) % len(self.sections)

    def toggle_rival(self) -> None:
        """SOLO, or VS COMPUTER."""
        self.rival = not self.rival

    def move_level(self, step: int) -> None:
        self.level = (self.level + step) % len(LEVELS)

    def move_mode(self, step: int) -> None:
        names = list(MODES)
        self.mode = names[(names.index(self.mode) + step) % len(names)]

    @property
    def play(self) -> Mode:
        """The way to play chosen: its rules and its rate."""
        return MODES[self.mode]

    def move_focus(self) -> None:
        """Hand the arrows to the next thing being chosen, round the three."""
        self.focus = FOCUS[(FOCUS.index(self.focus) + 1) % len(FOCUS)]

    def move(self, step: int) -> None:
        """Up or down, on whatever is in hand."""
        if self.focus is PICKING_COURSE:
            self.move_course(step)
        else:
            self.move_across(step)

    def move_across(self, step: int) -> None:
        """Left or right, on whatever is in hand.

        **The whole arrow cluster is handed over, not half of it.** Picking a
        course, the two axes are the two axes of one list -- down the names and
        across to the other list. Picking a level, they are the level's own row,
        which is drawn across and so is walked across; up and down walk it too,
        because a key that does nothing on a screen this small is a key the
        player has to be told about.

        It read the other way for one revision -- left and right kept switching
        the list from the level row -- which left the level with no horizontal
        keys at all despite being the one thing on this screen that is laid out
        horizontally. `move` and this are the only two calls `main` makes, so
        which of the four things happens is decided here and not in the window.
        """
        if self.focus is PICKING_LEVEL:
            self.move_level(step)
        elif self.focus is PICKING_MODE:
            self.move_mode(step)
        else:
            self.move_section(step)

    def _scroll(self) -> None:
        """Keep the cursor inside the window, moving it as little as possible.

        State rather than a formula off the cursor: a window centred on the
        cursor would slide the whole list under a cursor that is not moving.
        """
        top = min(self.top, self.course)
        top = max(top, self.course - WINDOW + 1)
        self.tops[self.tab] = max(0, min(top, max(0, len(self.tracks) - WINDOW)))

    # -- what it says ---------------------------------------------------------

    @property
    def visible(self) -> list[tuple[int, str]]:
        """`[(index, name)]` for the rows the screen has room for, so the
        renderer does no arithmetic about which of them exist."""
        rows = self.tracks[self.top:self.top + WINDOW]
        return [(self.top + n, name) for n, (name, _factory) in enumerate(rows)]

    @property
    def more_above(self) -> bool:
        return self.top > 0

    @property
    def more_below(self) -> bool:
        return self.top + WINDOW < len(self.tracks)

    @property
    def name(self) -> str:
        return self.tracks[self.course][0] if self.tracks else ""

    @property
    def best(self) -> float | None:
        """The time to beat on the course and level under the cursor."""
        return scoreboard.best(self.records, self.name, self.level)

    @property
    def best_score(self) -> int:
        """The score to beat on the same two. Nought where there is none: a
        course nobody has finished has no time, and one nobody has flipped on
        has a score."""
        return scoreboard.best_score(self.records, self.name, self.level)

    def build(self) -> Ground:
        """The chosen map, loaded when it is asked for: a list of sixty maps is
        sixty names, and only the one ridden is read off the disk."""
        return self.tracks[self.course][1]()

    def finished(self, elapsed: float, score: int = 0) -> bool:
        """Offer a finished run to the scoreboard. Returns whether either half
        of it stuck.

        **Only a finish is offered**, which is why the two travel together: a
        run that ran out of clock has a score on the HUD and no business on a
        board of things that were completed.

        Written through to disk here rather than on quitting, because a game
        nobody quits cleanly -- which is every game closed by its window button
        -- would never write anything.
        """
        if not scoreboard.put(self.records, self.name, self.level, elapsed, score):
            return False
        scoreboard.save(self.records, self.path)
        return True
