"""A whole screen of the original's, painted the way the original paints it.

Between races the original shows screens -- the title, the two it chooses a
course on, the card before a race and the results after one -- and **each is a
little program in the cartridge**: an address in its tile map and then the tiles
to write there. So a screen is cloned by running its program, and there is no
lettering to decode and no table to carry: the words are tile numbers where the
cartridge keeps them.

`paint` is the original's interpreter. Its cursor **walks the row it is in and
comes back to that row's start**, which is the one thing about it worth saying
twice: a cursor that ran on would fill the row below with the tail of this one,
and the screen would still look nearly right. `draw=False` writes the blank tile
instead of the program's, which is how the original takes a screen away again --
the same program, run backwards in effect.

`screen` lays a program's tiles out as the twenty by eighteen the player sees.

**Three screens so far.** The one a course and a level are chosen on, the card
before a race -- the course, the level, the
record and the time to qualify -- and the results after one: the banner, the
word, and the time, which is the only part of that one the race decides.

Pyxel-free.
"""

from game.rom.cartridge import Cartridge

#: The tile map a program's addresses are in, and how wide it is.
MAP, WIDE = 0x9800, 32
#: What the player sees of it.
SCREEN_W, SCREEN_H = 20, 18
#: Nothing, which is what a screen is made of before a program paints on it.
BLANK = 0x7F
#: A program's two commands: another address, and the end of it.
NEXT, END = 0xFE, 0xFF
#: More than any program the cartridge holds, so that bytes that are not one are
#: not read for ever.
RUNAWAY = 0x400

#: The logo screen: its drawing, painted by the run-length interpreter, and the
#: legal words under it by the other one.
LOGO, LOGO_WORDS = 0x1298, 0x12A8
#: The title: its drawing, and then four programs of words -- the game's name,
#: whose copyright it is, and the three ways to play it.
TITLE = 0x1485
TITLE_WORDS = (0x0EB5, 0x0EF5, 0x0EFC, 0x0F0A)
#: The cursor beside the three ways to play: one sprite, whose row is a number
#: in the original's code rather than a table -- eight pixels a mode -- and
#: whose column, tile and flags are three bytes of the cartridge.
MODE_SPRITE = 0x0575
MODE_Y = (0x80, 0x88, 0x90)
#: The three ways to play, in the order the cursor walks them.
SOLO, VS_COMPUTER, VS_TWO = 0, 1, 2
#: **This game's fourth row**, which the original's title has not: FREE RIDE,
#: written in the cartridge's own lettering a row under the third way to play
#: and in its column, so it reads as one more of them. The letters it needs are
#: tiles of the lettering the title is already written in -- the F is the one
#: none of the title's own words uses -- and these are those tiles.
FREE_RIDE = "FREE RIDE"
FREE_RIDE_AT = 0x9800 + 17 * 0x20 + 6
FREE_RIDE_LETTERS = {"F": 0xDC, "R": 0xE2, "E": 0xED, "I": 0xEB, "D": 0xE6, " ": 0x7F}
#: ...and with it the four ways to play go up half a tile, from the row the
#: first of them is in, so the fourth is as clear of the bottom edge as the
#: first is of the words above it.
MODES_ROW, FOUR_ROWS_LIFT = 14, 4
#: A run-length program's commands, read off the count byte: bit 7 clear is one
#: tile so many times, `RUN` on its own is a tile and a count with the tile going
#: up by one each time, and anything else is so many tiles each its own.
RUN = 0x80
#: ...and it ends on a count of nothing.
STOP = 0x00

#: The screen the course and then the level are chosen on, and the program that
#: takes the row of eight numbers away once the course is chosen.
SELECT, SELECT_CHOSEN = 0x33F8, 0x3480
#: Where the chosen course's number is written back, in digits of its own.
NUMBERS_AT, NUMBER_DIGIT = 0x98E0, 0xF0
#: The cursor: the two sprites it starts as -- `(y, x, tile, flags)` each, which
#: is where its two rows are -- and a table of where it goes along each, eight
#: for the courses and three for the levels.
CURSOR_SEED, COURSE_CURSORS, LEVEL_CURSORS = 0x3317, 0x33ED, 0x33F5
#: A sprite's own corner: the Game Boy puts one at `(x - 8, y - 16)`.
SPRITE_X, SPRITE_Y = 8, 16

#: The card before a race: the course in a box, its record and the time to beat.
#: The cartridge keeps a second one at $0F31 for the mode that has no qualifying
#: time on it, and chooses between them on a bit this game does not read yet.
CARD = 0x0F18
#: Where the course's number and the level's letter go, side by side in the box.
COURSE_AT, LEVEL_AT = 0x988D, 0x988E
#: The course's number is a digit of an alphabet of its own, and the level's
#: letter is one of three that are not next to each other.
COURSE_DIGIT, LEVELS = 0xA0, (0x8F, 0x95, 0x94)
#: The two times on it: the record above, the time to qualify below.
RECORD_AT, QUALIFYING_AT = 0x9967, 0x99E7

#: The results: the banner and the words, and the computer's line under them.
RESULTS, RESULTS_RIVAL = 0x30BB, 0x310B
#: Where each one's time goes, and the digits it is written in.
TIME_AT, RIVAL_TIME_AT, DIGITS = 0x992A, 0x996A, 0xF0
#: ...and the word that goes there instead for a bike that never reached the
#: line, which is `LOST` in the cartridge's own letters. A program with no
#: address of its own: the original drops it a tile along from where the time
#: would have started.
NO_TIME = 0x3175
#: ...and the line the original adds when the race just ridden beat the course
#: record: `IT'S A RECORD!`, fourteen tiles of its own. The original paints it
#: twice -- once with the screen, and then blinking on a frame counter, which is
#: the same trick `TIME UP` is drawn with.
RECORD = 0x315D

#: The screen a race the clock ran out on ends on: the two words, and nothing
#: else. One program and one painter -- the original has no drawing here, only
#: `GAME OVER` written into the middle of an empty screen.
GAMEOVER = 0x0EE9
#: A minute in hundredths, which is what the time is counted in.
MINUTE = 6000
#: The columns a colon sits in, counted in digits written: the screen's program
#: has painted them already, so the digits step over them.
COLONS = (0, 2)


def paint(cartridge: Cartridge, program: int, tiles: dict[int, int] | None = None,
          draw: bool = True, at: int | None = None) -> dict[int, int]:
    """Run a program: the tiles it writes, by the address it writes them at.

    An address word, then tiles, `NEXT` for another address and `END` at the
    end. The cursor wraps inside its own row of `WIDE`.

    **`at` is for the programs the cartridge keeps without an address of their
    own**, to be dropped wherever the caller's cursor already is: the word that
    goes where a time would be is one of those, and it goes in two rows.
    """
    if tiles is None:
        tiles = {}
    address = at if at is not None else cartridge.word(program)
    at = program if at is not None else program + 2
    for _ in range(RUNAWAY):
        tile = cartridge.byte(at)
        at += 1
        if tile == END:
            break
        if tile == NEXT:
            address = cartridge.word(at)
            at += 2
            continue
        tiles[address] = tile if draw else BLANK
        address = address & ~(WIDE - 1) if address % WIDE == WIDE - 1 else address + 1
    return tiles


def paint_runs(cartridge: Cartridge, program: int,
               tiles: dict[int, int] | None = None) -> dict[int, int]:
    """Run a program of the cartridge's **other** painter: a picture, in runs.

    An address word and then counts: a count with bit 7 clear is one tile
    written that many times; `RUN` on its own is a tile and a count, and the
    tile goes **up by one** each time, which is how a picture of tiles numbered
    in order is a byte and a half; any other count is that many tiles, each
    written once. A count of nothing ends it.

    **Its cursor does not wrap**, unlike `paint`'s: it runs straight on into the
    row below, which is what a picture across the screen needs and a row of
    words does not. The two interpreters are in the cartridge for that reason
    and they are two here for the same one.
    """
    if tiles is None:
        tiles = {}
    at = program
    address = cartridge.word(at)
    at += 2
    for _ in range(RUNAWAY):
        count = cartridge.byte(at)
        at += 1
        if count == STOP:
            break
        if not count & RUN:
            tile = cartridge.byte(at)
            at += 1
            for _ in range(count):
                tiles[address] = tile
                address += 1
        elif count & (RUN - 1):
            for _ in range(count & (RUN - 1)):
                tiles[address] = cartridge.byte(at)
                at += 1
                address += 1
        else:
            tile, run = cartridge.byte(at), cartridge.byte(at + 1)
            at += 2
            for _ in range(run):
                tiles[address] = tile
                address += 1
                tile = (tile + 1) & 0xFF
    return tiles


def logo(cartridge: Cartridge) -> dict[int, int]:
    """The screen the game opens on: the drawing, and the legal words under it.

    Two programs and two painters -- the drawing in runs, the words a tile at a
    time -- which is the original running both at one screen.
    """
    tiles = paint_runs(cartridge, LOGO)
    return paint(cartridge, LOGO_WORDS, tiles)


def gameover(cartridge: Cartridge) -> dict[int, int]:
    """The screen a race the clock ran out on ends on: `GAME OVER`.

    One program of words on an empty screen, painted a tile at a time, and it
    carries its own address like every other: the original erases the map first
    and writes these nine tiles into the middle of it.
    """
    return paint(cartridge, GAMEOVER)


def title(cartridge: Cartridge) -> dict[int, int]:
    """The title: the drawing, the name, the copyright and the three ways to play.

    Four programs of words after the drawing, because the original keeps them
    apart -- and it paints them in this order, which matters where two of them
    write in the same row.
    """
    tiles = paint_runs(cartridge, TITLE)
    for program in TITLE_WORDS:
        paint(cartridge, program, tiles)
    return tiles


def lifted(cells: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """A painted title's cells with the ways to play half a tile higher."""
    return [(x, y - FOUR_ROWS_LIFT if y >= MODES_ROW * 8 else y, tile) for x, y, tile in cells]


def free_ride(tiles: dict[int, int]) -> dict[int, int]:
    """The title's tiles with this game's fourth row written in under the three."""
    for step, letter in enumerate(FREE_RIDE):
        tiles[FREE_RIDE_AT + step] = FREE_RIDE_LETTERS[letter]
    return tiles


def mode_cursor(cartridge: Cartridge, mode: int) -> list[tuple[int, int, int]]:
    """Where the cursor beside the ways to play is: `(x, y, tile)`.

    A sprite, so it is drawn at `(x - 8, y - 16)` like every other one here, and
    its tile is a **sprite's** tile: not one the background can name at all.
    The fourth row, FREE RIDE, is a row further down at the original's pitch.
    """
    x, tile = cartridge.byte(MODE_SPRITE), cartridge.byte(MODE_SPRITE + 1)
    y = MODE_Y[mode] if mode < len(MODE_Y) else MODE_Y[-1] + (MODE_Y[1] - MODE_Y[0])
    return [(x - SPRITE_X, y - SPRITE_Y, tile)]


def four_rows_cursor(cartridge: Cartridge, mode: int) -> list[tuple[int, int, int]]:
    """`mode_cursor` on the title with the fourth row, lifted with the rows."""
    return [(x, y - FOUR_ROWS_LIFT, tile) for x, y, tile in mode_cursor(cartridge, mode)]


def clock(elapsed: int) -> list[int]:
    """A time in hundredths as the five digit tiles the original writes it in:
    a minute, two of seconds and two of hundredths."""
    minutes, rest = divmod(elapsed, MINUTE)
    seconds, hundredths = divmod(rest, 100)
    return [DIGITS + int(digit) for digit in "%d%02d%02d" % (minutes, seconds, hundredths)]


def results(cartridge: Cartridge, elapsed: int, rival: int | None = None,
            computer: bool = False, record: bool = False) -> dict[int, int]:
    """The screen a finished race ends on: the banner, the words, and the times.

    The computer's line is a program of its own and is only run when there was a
    computer in the race -- and **it gets a word rather than a time when it did
    not finish**, which is the usual way a race against it ends: the player
    crosses the line and the results go up with the other bike still riding.

    `record` adds the line that says the record fell. It is a program like the
    other two and lands where its own address says, so the caller only decides
    whether it runs.
    """
    tiles = paint(cartridge, RESULTS)
    _write(tiles, TIME_AT, clock(elapsed))
    if record:
        paint(cartridge, RECORD, tiles)
    if computer:
        paint(cartridge, RESULTS_RIVAL, tiles)
        if rival is None:
            paint(cartridge, NO_TIME, tiles, at=RIVAL_TIME_AT + 1)
        else:
            _write(tiles, RIVAL_TIME_AT, clock(rival))
    return tiles


def select(cartridge: Cartridge, course: int,
           picking_course: bool = True) -> dict[int, int]:
    """The screen the course and the level are chosen on.

    One screen and two steps. The eight numbers and the three letters are on it
    from the start; **choosing the course takes the other seven numbers away** --
    the original blanks that row with a program of its own and writes the chosen
    number back where it stood -- so the screen says what is settled as well as
    what is being settled.
    """
    tiles = paint(cartridge, SELECT)
    if not picking_course:
        paint(cartridge, SELECT_CHOSEN, tiles)
        tiles[NUMBERS_AT + _column(cartridge, course)] = NUMBER_DIGIT | course
    return tiles


def cursor(cartridge: Cartridge, course: int, level: int,
           picking_course: bool = True) -> list[tuple[int, int, int]]:
    """Where the cursor sprites are: `(x, y, tile)` each, on the screen.

    Two of them, one under the numbers and one under the letters, and the level's
    is there the whole time -- the course's is what goes away once the course is
    chosen. Their rows are in the pair of sprites the original starts them as,
    and their columns in a table each.
    """
    row = [cartridge.byte(CURSOR_SEED + n) for n in range(8)]
    tile = row[2]
    cells = [(cartridge.byte(LEVEL_CURSORS + level) - SPRITE_X, row[4] - SPRITE_Y, tile)]
    if picking_course:
        cells.append((cartridge.byte(COURSE_CURSORS + course - 1) - SPRITE_X,
                      row[0] - SPRITE_Y, tile))
    return cells


def _column(cartridge: Cartridge, course: int) -> int:
    """Which column of the numbers' row a course's number stands in, worked out
    from where its cursor goes: the original writes the number under the cursor
    and never keeps the two apart."""
    return ((cartridge.byte(COURSE_CURSORS + course - 1) - SPRITE_X) >> 3) & (WIDE - 1)


def card(cartridge: Cartridge, course: int, level: int, record: int,
         limit: int) -> dict[int, int]:
    """The card a race starts on: `COURSE 3B`, the record and the qualifying time.

    The course and the level are written a tile each into a program that leaves
    room for them, and the two times are written as digits the way the results'
    time is -- so the card is the same program every race and four numbers.
    """
    tiles = paint(cartridge, CARD)
    tiles[COURSE_AT] = COURSE_DIGIT | course
    tiles[LEVEL_AT] = LEVELS[level]
    _write(tiles, RECORD_AT, clock(record))
    _write(tiles, QUALIFYING_AT, clock(limit))
    return tiles


def screen(tiles: dict[int, int]) -> list[tuple[int, int, int]]:
    """A program's tiles as the twenty by eighteen on the screen: `(x, y, tile)`
    each, in the reading order, and the blank tile where nothing was written."""
    return [(col * 8, row * 8, tiles.get(MAP + row * WIDE + col, BLANK))
            for row in range(SCREEN_H) for col in range(SCREEN_W)]


def _write(tiles: dict[int, int], at: int, digits: list[int]) -> None:
    """Digits along a row, stepping over the columns the colons are painted in."""
    column = 0
    for step, digit in enumerate(digits):
        tiles[at + column] = digit
        column += 2 if step in COLONS else 1
