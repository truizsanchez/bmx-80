"""The screens between one race and the next, drawn.

The original's front end is screens, not a menu: the course is chosen on one,
the level on the same one a step later, a card names both and shows two times,
and the results end a race. Each is a **program of tile numbers in the
cartridge** (`game/rom/screen.py`), so each is cloned by running its program --
and what moves on top of one is a sprite or two, which is all a cursor is.

`game/front.py` is what these draw: it says which screen is up and where its
cursor is, and knows nothing about a window.

Every one of them is drawn twice over: **the cartridge's, and this game's own**,
for a game with no cartridge to read. The lettering they are written in shares
`rom_art`'s bank with a course's art -- see there for why that is one or the
other and never both.
"""

import pyxel

from game.constants import CELL, SCREEN_W, TILE
from game.engine.run import Run
from game.front import COURSE, MODES, Front
from game.render import assets, lettering, rom_art
from game.render.lettering import label
from game.render.style import BULK, SKY
from game.rom import graphics, panel, screen
from game.rom.cartridge import Cartridge

#: The three levels, named as the original names them on its card.
LEVELS = "ABC"
#: The art each screen is written in, by name. The lettering does for most of
#: them; the title brings a drawing of its own, and the logo a drawing the
#: cartridge keeps as bytes rather than as a list of loads.
LETTERING, TITLE_ART, LOGO_ART = "lettering", "title", "logo"
#: This game's own cursor, where the cartridge's is a tile: a bar under the
#: thing in hand, as wide as the thing is.
CURSOR_H = 2


#: This game's logo: eight cells by two, drawn on its own opening screen and
#: title -- the screens that are this game's -- and nowhere a cartridge's are.
LOGO_COLS, LOGO_ROWS = 8, 2
LOGO_W = LOGO_COLS * CELL


def draw_logo(x: int, y: int) -> None:
    """The title, as sixteen cells of art like everything else on the screen.

    Which is the whole point of it being art: `art/hand/logo_31.png` wins over
    the cell it names the way it would over any tile, and nothing here knows or
    cares which of the two it got.

    Blitted with `SKY` as the colour key, not opaquely, for the reason every
    other blit in `render/` is: a tile's sky is not paint, and an opaque logo
    would be unusable the day it sits on anything but `cls(SKY)`.
    """
    for col in range(LOGO_COLS):
        for row in range(LOGO_ROWS):
            u, v = assets.uv("logo_%d%d" % (col, row))
            pyxel.blt(x + col * CELL, y + row * CELL, assets.BANK, u, v,
                      CELL, CELL, SKY)


def _lettering(cartridge: Cartridge) -> bytearray:
    return graphics.video(cartridge, graphics.LETTERING)


def _title_art(cartridge: Cartridge) -> bytearray:
    """The lettering and the title's own drawing -- and the cursor, which is one
    tile the cartridge copies rather than loads."""
    video = graphics.video(cartridge, graphics.LETTERING, graphics.TITLE)
    graphics.copy(cartridge, video, graphics.CURSOR_ART, graphics.CURSOR_AT,
                  graphics.TILE_BYTES)
    return video


def _logo_art(cartridge: Cartridge) -> bytearray:
    video = graphics.video(cartridge, graphics.LETTERING)
    graphics.copy(cartridge, video, graphics.LOGO_ART, graphics.LOGO_AT,
                  graphics.LOGO_BYTES)
    return video


def draw_splash() -> None:
    """The screen the game opens on: the drawing, and whose game it is.

    The cartridge keeps its drawing as bytes rather than as a list of loads, so
    the art it is written in is its own. Without a cartridge this game says the
    same thing about itself instead.
    """
    cartridge = rom_art.rom()
    if cartridge is not None:
        rom_art.use(LOGO_ART, _logo_art)
        rom_art.tiles(screen.screen(screen.logo(cartridge)))
        return
    pyxel.cls(SKY)
    draw_logo((SCREEN_W - LOGO_W) // 2, 5 * TILE)
    lettering.centred(11 * TILE, "A REIMPLEMENTATION")
    lettering.centred(13 * TILE, "OF A GAME OF 1991")


def draw_title(front: Front) -> None:
    """The title: the drawing, the name, whose it is, and the three ways to play.

    The cursor beside them is a sprite of a tile no background id names, drawn
    by hand for that reason. Without a cartridge the same three lines are
    written here under this game's own name.
    """
    cartridge = rom_art.rom()
    if cartridge is not None:
        rom_art.use(TITLE_ART, _title_art)
        if len(front.rows) > len(MODES):
            pyxel.cls(SKY)
            rom_art.tiles(screen.lifted(screen.screen(screen.free_ride(screen.title(cartridge)))))
            cursor = screen.four_rows_cursor(cartridge, front.mode)
        else:
            rom_art.tiles(screen.screen(screen.title(cartridge)))
            cursor = screen.mode_cursor(cartridge, front.mode)
        for x, y, tile in cursor:
            rom_art.sprite_tile(tile, x, y)
        return
    pyxel.cls(SKY)
    draw_logo((SCREEN_W - LOGO_W) // 2, 2 * TILE)
    for index, words in enumerate(front.rows):
        y = (9 + 2 * index) * TILE
        label(4 * TILE, y, 4 * len(words) + 4, words)
        if index == front.mode:
            pyxel.rect(2 * TILE, y + 2, TILE // 2, TILE // 2, BULK)


def draw_select(front: Front) -> None:
    """The screen the course and then the level are chosen on.

    One screen and two steps, which is the original's: the eight numbers and the
    three letters are both on it from the start, and what changes is which
    cursor is up. Choosing the course takes the other seven numbers away -- the
    original blanks that row and writes the chosen one back where it was -- so
    the screen says what you have chosen so far and what you are choosing now.
    """
    cartridge = rom_art.rom()
    if cartridge is not None:
        rom_art.use(LETTERING, _lettering)
        rom_art.tiles(screen.screen(screen.select(cartridge, front.course,
                                                  picking_course=front.step is COURSE)))
        rom_art.tiles(screen.cursor(cartridge, front.course, front.level,
                                    picking_course=front.step is COURSE), SKY)
        return
    pyxel.cls(SKY)
    lettering.centred(3 * TILE, "SELECT COURSE")
    _row(7 * TILE, [str(number) for number in front.numbers],
         front.course - 1 if front.step is COURSE else None,
         chosen=None if front.step is COURSE else front.course - 1)
    lettering.centred(11 * TILE, "SELECT LEVEL")
    _row(15 * TILE, list(LEVELS[:front.levels]),
         None if front.step is COURSE else front.level, chosen=None)


def draw_card(front: Front, limit: int) -> None:
    """The card a race starts on: the course, the level, the record, the time to
    qualify.

    The cartridge's is its own program with four numbers written into it. Without
    one it is the same card written here -- and the course may have no record yet, which the original cannot: it ships a
    table of times and shows one of those until a race beats it.
    """
    cartridge = rom_art.rom()
    record = front.record
    if cartridge is not None:
        rom_art.use(LETTERING, _lettering)
        rom_art.tiles(screen.screen(screen.card(
            cartridge, front.course, front.level,
            cartridge.record(front.course) if record is None else record, limit)))
        return
    pyxel.cls(SKY)
    title = "COURSE %d %s" % (front.course, LEVELS[front.level])
    label((SCREEN_W - 4 * len(title) - 4) // 2, 3 * TILE, 4 * len(title) + 4, title)
    lettering.centred(9 * TILE, "COURSE RECORD")
    lettering.centred(11 * TILE, "-:--.--" if record is None else _clock(record))
    lettering.centred(13 * TILE, "QUALIFYING TIME")
    lettering.centred(15 * TILE, _clock(limit))


def draw_results(run: Run, record: bool = False, frames: int = 0) -> None:
    """The screen a finished race ends on, over the whole of the window.

    The cartridge's is a program of its own tiles with the time written into it
    in digits; without one it is the same words written here. Either way the
    course and the band are gone: this is a screen and not something over the
    race.

    With the computer's bike in the race its line is under the player's, and it
    carries a word rather than a time until that bike has reached the line --
    which it usually has not, the race ending when the player gets there.

    `record` is whether the record fell, and it adds a line saying so -- the
    cartridge's own, in its own words, and this game's own where there is no
    cartridge to read. It **blinks**, on the same count of displayed frames and
    the same bit of it the `TIME UP` box blinks on, which is what the original
    does: it paints the line with the screen and then draws and erases it.
    """
    cartridge = rom_art.rom()
    computer = run.rival is not None
    record = record and not frames & panel.BLINK
    if cartridge is not None:
        rom_art.use(LETTERING, _lettering)
        rom_art.tiles(screen.screen(screen.results(
            cartridge, run.elapsed, rival=run.rival_time, computer=computer,
            record=record)))
        return
    pyxel.cls(SKY)
    banner = "YOU QUALIFIED!"
    label((SCREEN_W - 4 * len(banner) - 4) // 2, 3 * TILE, 4 * len(banner) + 4, banner)
    lettering.centred(7 * TILE, "RESULTS")
    lettering.centred(9 * TILE, "YOU   " + _clock(run.elapsed))
    if record:
        lettering.centred(14 * TILE, "IT'S A RECORD!")
    if computer:
        rival = run.rival_time
        # `LOST` is the cartridge's own word for a bike that never got there,
        # so it is the word here as well.
        lettering.centred(11 * TILE,
                          "COM   " + ("LOST" if rival is None else _clock(rival)))


def draw_gameover() -> None:
    """The screen a race the clock ran out on ends on: two words on nothing.

    The cartridge's is a program of its own words in the lettering every screen
    between races is written in; without one the same two words are written
    here. There is nothing else on it either way -- no time, no course, no
    banner -- because the original puts nothing else on it.
    """
    cartridge = rom_art.rom()
    if cartridge is not None:
        rom_art.use(LETTERING, _lettering)
        rom_art.tiles(screen.screen(screen.gameover(cartridge)))
        return
    pyxel.cls(SKY)
    lettering.centred(8 * TILE, "GAME OVER")


def _row(y: float, words: list[str], cursor: int | None, chosen: int | None) -> None:
    """A row of short words, evenly spread, with a bar under one of them.

    `chosen` is the one already picked, and the rest are gone with it: the row
    says what is settled as well as what is being settled.
    """
    step = SCREEN_W // (len(words) + 1)
    for index, word in enumerate(words):
        if chosen is not None and index != chosen:
            continue
        x = step * (index + 1) - 2 * len(word)
        label(x, y, 4 * len(word) + 4, word)
        if index == cursor:
            pyxel.rect(x, y + 2 * CURSOR_H + 4, 4 * len(word) + 4, CURSOR_H, BULK)


def _clock(hundredths: int) -> str:
    """`M:SS.hh`, the way this game's own screens write a time."""
    seconds, rest = divmod(max(0, hundredths), 100)
    return "%d:%02d.%02d" % (seconds // 60, seconds % 60, rest)
