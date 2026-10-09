"""FREE RIDE: the picture of `game/menu.py`.

Its own file because nothing else draws with it: the screen you choose from has
its own positions and its own helpers. What it shares with the rest is the
lettering, `lettering.label` and `lettering.centred`, imported rather than drawn
twice.
"""

from typing import Sequence

import pyxel

from game import records
from game.constants import SCREEN_W
from game.course import LEVEL_NAMES, LEVELS
from game.menu import PICKING_COURSE, PICKING_LEVEL, PICKING_MODE, WINDOW, Menu
from game.mode import MODES
from game.render.lettering import ROW_H, centred, label
from game.render.style import EDGE, RIM, SKY


# FREE RIDE, top to bottom. Positions rather than tunables -- with one number
# that is neither and lives in the model: `menu.WINDOW`, how many rows fit,
# which the cursor has to be kept inside.
#
# **No logo**: the screen's name instead. With a cartridge in, a BMX-80 banner
# over the cartridge's own courses said the wrong thing about whose game the
# screen was; the logo is on this game's own opening screen and title.
MENU_HEADING_Y = 6
MENU_TAB_Y = 20
MENU_LIST_Y = 34
MENU_ROW_H = 10
MENU_X = 20
# Three things across a 160-pixel screen, and the widths are what decides the
# places: a name is cut at ten characters (40px, ending at 60), a time is six
# (`1:04.3`, ending at 88) and a score is right-aligned so that its digits grow
# leftwards into the gap instead of pushing the marks off the edge. Five digits
# reach back to 112, which leaves the column clear of the clock.
MENU_NAME_CHARS = 10
MENU_TIME_X = 64
MENU_SCORE_RIGHT = 132
MENU_MARK_X = 136  # clear of the score column, which ends at 132
MENU_LEVEL_Y = 98
MENU_MODE_Y = 110
# Two rows, and the second is what moved the first up: at 128 alone there was no
# room under it. 135 plus the font's six pixels lands on 141, three clear of the
# bottom edge.
MENU_PROMPT_Y = 126
MENU_PROMPT2_Y = 135


def draw_menu(menu: Menu) -> None:
    """The one screen you choose from: a course, a level, and what to beat.

    The record beside each course is the record *at the level in hand*, and it
    changes as the level does -- three levels are three races over the same
    ground, and one number across all of them would be the easy level's number
    for ever. `--:--` is a course nobody has finished yet, which is a truer thing
    to draw than a blank.
    """
    pyxel.cls(SKY)
    heading = "FREE RIDE"
    label((SCREEN_W - 4 * len(heading) - 4) // 2, MENU_HEADING_Y, 4 * len(heading) + 4, heading)

    # The section names. The row is there whether there are one or two of them,
    # so the screen does not shift the day a draft appears in `maps/drafts/` --
    # but with one it is drawn as a heading and not as a chooser. Reverse video
    # on a lone tab would say there is another one to reach.
    if len(menu.sections) > 1:
        _choices(MENU_TAB_Y, [title for title, _ in menu.sections], menu.tab)
    else:
        centred(MENU_TAB_Y, menu.label)

    # Two things are chosen here and there is one pair of arrows, so the picture
    # has to say which of them the arrows are on: the live one is filled and the
    # other is outlined, both of them on screen the whole time. A mode nobody can
    # see is the bill the editor has paid four times.
    on_course = menu.focus is PICKING_COURSE
    for index, name in menu.visible:
        y = MENU_LIST_Y + (index - menu.top) * MENU_ROW_H
        chosen = index == menu.course
        if chosen:
            pyxel.text(MENU_X - 10, y, ">" if on_course else "-", EDGE if on_course else RIM)
        colour = EDGE if chosen else RIM
        pyxel.text(MENU_X, y, name[:MENU_NAME_CHARS], colour)
        best, score = _record(menu, name)
        pyxel.text(MENU_TIME_X, y, best, colour)
        pyxel.text(MENU_SCORE_RIGHT - 4 * len(score), y, score, colour)

    if not menu.tracks:
        # The drafts' tab with no drafts in it, which is every fresh clone and
        # every build: what the tab is for, and how to fill it.
        centred(MENU_LIST_Y + MENU_ROW_H // 2, "no custom courses yet")
        centred(MENU_LIST_Y + 2 * MENU_ROW_H, "draw one: --edit <name>")

    _scroll_marks(menu)
    _choices(MENU_LEVEL_Y, [LEVEL_NAMES[level] for level in LEVELS], menu.level,
             live=menu.focus is PICKING_LEVEL)
    names = list(MODES)
    _choices(MENU_MODE_Y, names, names.index(menu.mode), live=menu.focus is PICKING_MODE)

    # The only instructions the game has, and they are about this screen.
    centred(MENU_PROMPT_Y, "arrows  tab  -  enter to ride")
    mode = "vs computer" if menu.rival else "solo"
    centred(MENU_PROMPT2_Y, "space: %s  -  esc back" % mode)


def _scroll_marks(menu: Menu) -> None:
    """A triangle where the list runs on past the window.

    A shape rather than a character: the built-in font has no arrow, and a
    lowercase `v` under a list of names reads as one more name.
    """
    if menu.more_above:
        y = MENU_LIST_Y + 1
        pyxel.tri(MENU_MARK_X, y + 3, MENU_MARK_X + 4, y + 3,
                  MENU_MARK_X + 2, y, RIM)
    if menu.more_below:
        y = MENU_LIST_Y + (WINDOW - 1) * MENU_ROW_H + 2
        pyxel.tri(MENU_MARK_X, y, MENU_MARK_X + 4, y,
                  MENU_MARK_X + 2, y + 3, RIM)


def _choices(y: int, words: Sequence[str], chosen: int, live: bool = True) -> None:
    """A row of words with one of them marked, centred.

    The tabs and the levels are the same picture, and were the same eight lines
    of `4 * len(word)` arithmetic written twice.

    `live` is whether the arrows are on this row: filled if they are, outlined if
    they are not. Same box either way, so nothing moves when the focus does --
    what changes is whether the selection reads as *here* or as *chosen earlier*.
    """
    width = sum(4 * len(word) + 4 for word in words) - 4
    x = (SCREEN_W - width) // 2
    for index, word in enumerate(words):
        if index == chosen:
            mark = label if live else _outline
            mark(x - 2, y - 1, 4 * len(word) + 3, word)
            x += 4 * len(word) + 5
        else:
            pyxel.text(x, y, word, RIM)
            x += 4 * len(word) + 4


def _outline(x: int, y: int, w: int, text: str) -> None:
    """`lettering.label`'s other half: the same box drawn as a border, with the text the
    way round it always is. What a selection the arrows are not on looks like."""
    pyxel.rectb(x, y, w, ROW_H, RIM)
    pyxel.text(x + 2, y + 1, text, EDGE)


def _record(menu: Menu, name: str) -> tuple[str, str]:
    """What there is to beat on this course at the level in hand: the clock and
    the score, both of them at that level, because three levels are three races.

    `--:--` for a course nobody has finished and `0` for one nobody has flipped
    on -- a truer pair of things to draw than a blank, and they are not the same
    absence: a time nobody has set does not exist, and a score nobody has earned
    is nought.
    """
    return (
        records.clock(records.best(menu.records, name, menu.level)),
        "%d" % records.best_score(menu.records, name, menu.level),
    )
