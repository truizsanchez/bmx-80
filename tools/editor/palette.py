"""Two palettes at once: the editor's chrome, and the game's four shades.

Adapted from `pyxel/editor/app.py` and its `extensions._user_pal`, which is the
trick this file exists to borrow. Pyxel is MIT-licensed, (c) 2018-2026 Takashi
Kitao; the licence text is `tools/editor/widgets/LICENSE-pyxel`, which covers
this file as well as the directory it sits in.

The game's art is loaded by *nearest colour* (`pyxel.Image.load`), so the four
shades of the active style have to be in the palette verbatim while it loads or
every tile silently maps onto whatever is closest -- the palette trap, which fails by
looking wrong rather than by raising. The vendored widgets, meanwhile, are
written against Pyxel's own sixteen colours and would need re-colouring line by
line to live in four.

Upstream holds both: the system palette in slots 0-15 and the user's above
`pyxel.NUM_COLORS`, with `user_pal()` remapping the drawing colours for the
moment art is blitted. The order below is the whole of it -- the art is loaded
while the *game's* palette is installed, so its pixels carry indices 0-3 exactly
as they do in the game and `style.SKY` still means sky; only then is the chrome
put back underneath them.
"""

import pyxel

from game.render import assets, palette as game_palette, style

SHADE_BASE = pyxel.NUM_COLORS
#: The sky among the game's four shades: every blit's colour key, and the map's ground.
SKY_INDEX = style.SKY

# Pyxel's own sixteen, which the vendored widgets are written against.
CHROME_BACK = 1
CHROME_TEXT = 7
CURVE = 8  # the rideable curve: red, as everywhere else in this repo
NORMAL = 11
GHOST = 12  # the piece the magnet is offering
LOOSE = 14  # ...and the same piece when the magnet has let go legally
MARK = 10
# What `check` is pointing at, and deliberately the same red the curve is drawn
# in: red is the one thing this palette already means "wrong" with, and the two
# cannot be confused because a curve is a line *through* cells and this is a box
# *around* them. It is transient -- the mark dies at the next edit -- so it never
# has to share the screen with itself.
WARN = 8
ERROR = 5  # ...and greyed out where letting go means the click is refused
# Where the computer's bike is put back: orange, which nothing else here is.
RESPAWN = 9


def install() -> list[int]:
    """Load the art in the game's palette, then put the chrome back under it."""
    system = list(pyxel.colors[: pyxel.NUM_COLORS])
    game_palette.apply()
    assets.load_all()
    pyxel.colors[:] = system + list(style.active().shades)
    return system


def user_pal() -> None:
    """Draw the next thing in the game's colours instead of the chrome's.

    **The shades are counted in the palette, not asked of the style.** `install`
    put them above `SHADE_BASE`, so what is there is exactly what to remap to.
    `style.active()` reads `art/STYLE` off the disk, and this runs once per tile
    blitted: asking it here opened that file 562 times a frame on a whole course, which
    was two thirds of the editor's whole frame.
    """
    for i in range(len(pyxel.colors) - SHADE_BASE):
        pyxel.pal(i, SHADE_BASE + i)
