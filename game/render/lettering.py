"""The game's lettering: a line of text centred, and a word in reverse video.

What the menu writes with, and what anything over the world will write with. Text
and panel are the same indices the art uses, so a style gets its lettering for
nothing -- no glyph is drawn per style for a word.
"""

import pyxel

from game.constants import SCREEN_W
from game.render.style import EDGE, SKY

#: One row of the built-in font, with a pixel of air: what a label is tall.
ROW_H = 7


def centred(y: float, text: str) -> None:
    """One line of text, centred across the screen."""
    pyxel.text((SCREEN_W - 4 * len(text)) // 2, y, text, EDGE)


def label(x: float, y: float, w: float, text: str) -> None:
    """A label: reverse video, the text in SKY on a box of EDGE."""
    pyxel.rect(x, y, w, ROW_H, EDGE)
    pyxel.text(x + 2, y + 1, text, SKY)
