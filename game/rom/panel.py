"""What the original puts on the screen that is not the course or the bikes: the
panel under the view, and the three sprites of the start.

The bottom sixteen pixels of the screen are the Game Boy's **window**: two rows
of twenty tiles, held in memory and copied to the window's map every frame. This
builds the same forty tiles out of a race, and `render/ride_draw.py` draws them
in the cartridge's own art.

What is on it, left to right:

- the **speedometer**, which is most of it: a needle in two tiles by the speed's
  magnitude, six tiles of bar chosen from the cartridge's own tables, and two
  more where the cap is -- so an S crate is read off the panel as the mark
  moving out;
- **TIRE** and **JET**, when an R or a J is being held;
- **TIME**, a bar rather than a clock: the seconds left, capped at fifty-five,
  eight levels to a tile;
- **NTR**, a canister for each nitro, up to eight.

**No clock and no lap counter**: the original has neither on the panel.

The ground the labels sit on is painted out of the cartridge as well, by the
same little program the original paints it with (`_painted`). Nothing here is a
table copied out of the cartridge: the bars are read from it where it keeps
them, and what is written down is the handful of tile numbers the code itself
carries.

**The marker** is two sprites over the player's bike -- a block with a point
under it, saying which of the two is yours. The computer's never has one.

**TIME UP** is a box of nine tiles by three in the middle of the view, with the
words blinking inside it -- background tiles, not sprites, written where the
screen is rather than where the course is.

**The start** is three sprites in the middle of the view: nothing, then three,
two, one, and then `GO!`. They change where the countdown's beeps are, because
the original counts one thing and both read it.

Pyxel-free: which tiles these are is a question about a race.
"""

from game.engine.original import J, MINI
from game.engine.run import Run
from game.engine.original import BEEPS_AT, GO_AT
from game.rom import screen
from game.rom.cartridge import Cartridge

#: The panel: two rows of a map thirty-two wide, of which twenty are on screen.
ROWS, ROW, WIDE = 2, 20, 32
#: Where the original keeps it, which is what its painter's addresses are in.
PANEL = 0xCBC0
#: The tile the whole of it is painted over before anything else.
GROUND = 0x42
#: Nothing, where a label is not showing.
BLANK = 0x7F

#: The program that paints the panel's labels, run by `screen.paint` -- the same
#: interpreter the screens between races are painted by.
LABELS = 0x0E9E

# -- the speedometer ----------------------------------------------------------------

#: The needle's two tiles. The top by magnitude 8 and 12, the bottom by 1 and 4.
NEEDLE_TOP, NEEDLE_BOTTOM = (0x57, 0x58, 0x59), (0xFA, 0xFB, 0xFC)
#: The bar's tables: below `FAST` and above it, six tiles each.
SLOW, FAST = 0x0E27, 0x0E5D
#: The mark for the cap, two tiles: where the magnitude puts it, and where it
#: goes with no S picked up at all.
MARK, NO_MARK = 0x0E75, 0x0E7F
#: The magnitudes the bar is read at: the slow table is stepped every four from
#: `SLOW_FROM`, the fast one every eight from `FAST_FROM`, and it stops at `TOP`.
SLOW_FROM, FAST_FROM, TOP = 0x0C, 0x30, 0x4F
#: ...and the mark's, every eight between these two.
MARK_FROM, MARK_TO = 0x50, 0x70
#: The cap reads as one tile from here, and two from `CAP_WIDE`.
CAP_MARKED, CAP_WIDE = 0x50, 0x60

# -- the rest -----------------------------------------------------------------------

#: `TIRE`, four tiles from here, when an R is held; `JET`, three, when a J is.
TIRE, JET = 0x45, 0x26
#: A nitro, one tile each.
CANISTER = 0x49
#: The time bar: empty, and the levels of a tile above it; and a full tile.
EMPTY, FULL = 0xA0, 0xA8
#: Levels to a tile, tiles to the bar, and the seconds it is full at.
LEVELS, BARS, LONGEST = 8, 8, 55

#: Where each piece starts, counted from `PANEL`.
NEEDLE, SPEED_BAR, CAP, TIME_BAR = 0, 1, 7, 13
RIDER_TIRE, RIDER_JET, NITROS = WIDE + 1, WIDE + 6, WIDE + 12
#: ...and the needle's lower half, which is the second row's first tile.
NEEDLE_LOW = WIDE


#: The start's three sprites: where the first goes, and how far apart they are.
START_X, START_Y, START_STEP = 88, 48, 8
#: What is drawn before the first of the three, which is nothing at all.
START_BLANK = 0x9A
#: The digits, from zero: the start counts down from `len(BEEPS_AT)`.
DIGITS = 0xF0
#: `GO!`, and its exclamation mark is not the tile after its O.
GO = (0xDD, 0xDE, 0xE1)


#: The TIME UP box: where its corner is, and how many tiles it is each way.
BOX_X, BOX_Y, BOX_W, BOX_H = 64, 40, 9, 3
#: What it is filled with, and the words in its middle row -- TIME, a gap, UP.
BOX = 0x98
TIME_UP = (0x92, 0x93, 0x94, 0x95, BOX, 0x96, 0x97)
#: The words show while this bit of the wait's counter is clear, so they are on
#: for eight frames and off for eight.
BLINK = 0x08

#: The barrier in front of the bike on the grid, and where it stands: sixteen
#: pixels along from where the bike starts and eight down.
BARRIER = (0xFD, 0xFE, 0xFF)
BARRIER_X, BARRIER_Y = 16, 8

#: What a secret taken leaves on the screen, by which one was taken: four tiles,
#: two by two. **It is the only thing that says a secret was there** -- the J
#: and the mini-maniacs are not in the map and are taken upside down, so without
#: this the jet arrives out of a clear sky.
SECRETS = {J: (0xC5, 0xC6, 0xC7, 0xC8), MINI: (0xD8, 0xD9, 0xDA, 0xDB)}
SECRET_WIDE = 2

#: The marker over the player's bike: a block and the point under it.
MARKER = (0xEC, 0xED)
#: Where it sits on the bike's sixteen pixels: centred, and clear above it.
MARKER_X, MARKER_Y = 4, -16


def timeup(held: int) -> list[tuple[int, int, int]]:
    """The TIME UP box, for a race the clock has run out on.

    Nine tiles by three of one tile, and the words in the middle row a tile in
    from each side. They **blink on displayed frames** -- on what the wait has
    left, which is the counter the original blinks them on -- and not on the
    race's iterations, which have stopped by the time the box is up.

    Background tiles rather than sprites, and the original writes them where the
    screen is: the box does not move with the course under it.
    """
    tiles = [(BOX_X + col * START_STEP, BOX_Y + row * START_STEP, BOX)
             for row in range(BOX_H) for col in range(BOX_W)]
    if not held & BLINK:
        middle = BOX_Y + (BOX_H // 2) * START_STEP
        tiles += [(BOX_X + (1 + step) * START_STEP, middle, tile)
                  for step, tile in enumerate(TIME_UP)]
    return tiles


def barrier(countdown: int, x: int, y: int) -> list[tuple[int, int, int]]:
    """The barrier on the grid, drawn at `(x, y)`: one sprite and one tile.

    It **falls rather than lifts**, and it falls at the very end: the first of
    its three tiles stands while the countdown has more than an iteration left,
    the second is the one iteration before the bike is let go, and the third is
    flat on the ground from then on.

    Unlike the start's three sprites this one is anchored to the course and not
    to the screen, so the caller hands it the camera's arithmetic -- and the
    original drops it the moment that puts it off the left of the screen, and
    never brings it back.
    """
    if x < 0:
        return []
    last = len(BARRIER) - 1
    return [(x, y, BARRIER[last - min(countdown, last)])]


def secret(kind: int, x: int, y: int) -> list[tuple[int, int, int]]:
    """The flourish a secret taken leaves, drawn at `(x, y)`: four tiles, 2x2.

    Anchored to the course like the barrier, and dropped the same way once the
    course has carried it off the left -- the original stops counting it down
    there rather than letting it wrap.
    """
    tiles = SECRETS.get(kind)
    if tiles is None or x < 0:
        return []
    return [(x + (step % SECRET_WIDE) * START_STEP,
             y + (step // SECRET_WIDE) * START_STEP, tile)
            for step, tile in enumerate(tiles)]


def marker(x: int, y: int) -> list[tuple[int, int, int]]:
    """The two sprites that say which bike is yours, for a bike drawn at `(x, y)`.

    Always, from the moment the race is on the screen: the original never takes
    it away, not in the air and not in a crash.
    """
    return [(x + MARKER_X, y + MARKER_Y + step * START_STEP, tile)
            for step, tile in enumerate(MARKER)]


def start(countdown: int) -> list[tuple[int, int, int]]:
    """The start's sprites for this iteration: `(x, y, tile)` each, or none.

    They change on the countdown's own numbers -- `BEEPS_AT` and `GO_AT`, the
    iterations the start beeps on -- rather than on a clock of their own, which
    is why the tone and the digit land together.

    The two either side of the digit are a tile with nothing in it, and it is
    drawn rather than skipped: what the original puts there is what goes there.
    """
    if not countdown:
        return []
    if countdown <= GO_AT:
        tiles = GO
    else:
        passed = sum(1 for beep in BEEPS_AT if countdown <= beep)
        tiles = (START_BLANK,
                 DIGITS + len(BEEPS_AT) + 1 - passed if passed else START_BLANK,
                 START_BLANK)
    return [(START_X + step * START_STEP, START_Y, tile)
            for step, tile in enumerate(tiles)]


def start_word(countdown: int) -> str:
    """What the start's sprites say this iteration: nothing, a digit, or `GO!`.

    The same count `start` reads, for a course with no cartridge to draw the
    three sprites out of.
    """
    if not countdown:
        return ""
    if countdown <= GO_AT:
        return "GO!"
    passed = sum(1 for beep in BEEPS_AT if countdown <= beep)
    return str(len(BEEPS_AT) + 1 - passed) if passed else ""


def rows(cartridge: Cartridge, run: Run) -> list[list[int]]:
    """The panel for this moment of this race: two rows of twenty tiles."""
    tiles = _painted(cartridge)
    _speed(cartridge, tiles, run.bike.magnitude, run.bike.speed.cap)
    _time(tiles, run.left)
    _held(tiles, RIDER_TIRE, 4, TIRE if run.bike.no_slope else None)
    _held(tiles, RIDER_JET, 3, JET if run.bike.jet else None)
    _nitros(tiles, run.bike.speed.nitros)
    return [tiles[row * WIDE:row * WIDE + ROW] for row in range(ROWS)]


def _painted(cartridge: Cartridge) -> list[int]:
    """The panel with nothing of the race on it: the ground everywhere, and the
    labels the cartridge's own program paints over it.

    The program is run by `screen.paint`, which is the interpreter the screens
    between races are painted by as well -- the panel is written in the same
    little language, at an address in memory rather than in the tile map.
    """
    tiles = [GROUND] * (ROWS * WIDE)
    for address, tile in screen.paint(cartridge, LABELS).items():
        index = address - PANEL
        if 0 <= index < len(tiles):
            tiles[index] = tile
    return tiles


def _speed(cartridge: Cartridge, tiles: list[int], magnitude: int, cap: int) -> None:
    """The needle, the bar, and the mark where the cap is."""
    tiles[NEEDLE] = NEEDLE_TOP[(magnitude >= 8) + (magnitude >= 12)]
    tiles[NEEDLE_LOW] = NEEDLE_BOTTOM[(magnitude >= 1) + (magnitude >= 4)]

    # Six tiles an entry in both tables, and they get there differently: the slow
    # one steps every four magnitudes and the fast one every eight, so the fast
    # one halves before it takes its half again.
    if magnitude < FAST_FROM:
        step = (max(magnitude, SLOW_FROM) & 0x3C) - SLOW_FROM
        at = SLOW + step + (step >> 1)
    else:
        step = ((min(magnitude, TOP) & 0x78) - FAST_FROM) >> 1
        at = FAST + step + (step >> 1)
    for offset in range(6):
        tiles[SPEED_BAR + offset] = cartridge.byte(at + offset)

    marked = min(max(magnitude, MARK_FROM) & 0xF8, MARK_TO)
    at = MARK + ((marked - MARK_FROM) >> 2)
    wide = 2
    if cap >= CAP_MARKED:
        wide = 2 if cap >= CAP_WIDE else 1
    else:
        at = NO_MARK
    for offset in range(wide):
        tiles[CAP + offset] = cartridge.byte(at + offset)
    # One tile between `CAP_MARKED` and `CAP_WIDE`, which is the one place this
    # panel and the original's can differ: the original keeps its panel and
    # rewrites the parts that moved, so the tile it does not write there is
    # whatever was written last; this one is composed from nothing every frame
    # and shows the ground. **No cap the game sets is in that window** -- it
    # sets 79 and 111 -- so it is a difference in a state a race does not reach.
    # Swept against the original with a hook on its own routine: 1099
    # compositions, magnitudes 0 to 108, not one tile different.


def _time(tiles: list[int], left: int) -> None:
    """The bar: the seconds left, eight levels to a tile.

    Capped at `LONGEST`, so a race that starts with more than a minute starts
    with the bar full and standing still -- which is what the original does,
    reading only the seconds of its clock and giving up above fifty-five.
    """
    whole, part = divmod(min(left // 100, LONGEST), LEVELS)
    for offset in range(BARS):
        tiles[TIME_BAR + offset] = (FULL if offset < whole
                                    else EMPTY + part if offset == whole else EMPTY)


def _held(tiles: list[int], at: int, wide: int, first: int | None) -> None:
    """A word of `wide` tiles from `first`, or nothing where it is not held."""
    for offset in range(wide):
        tiles[at + offset] = BLANK if first is None else first + offset


def _nitros(tiles: list[int], nitros: int) -> None:
    """A canister each, up to eight; the rest of the row is nothing."""
    for offset in range(BARS):
        tiles[NITROS + offset] = CANISTER if offset < min(nitros, BARS) else BLANK
