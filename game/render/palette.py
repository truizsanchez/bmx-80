"""Pyxel palette setup.

The tile art uses exactly four colors (verified across the whole tileset):
#000000, #606060, #a8a8a8, #f8f8f8. `pyxel.images[n].load()` maps every source
pixel to the *nearest* entry of the 16-color palette, so putting those four
values in slots 0-3 verbatim makes the mapping exact (distance 0 always wins)
regardless of what the other twelve slots hold. Getting this wrong is not
subtle: with the stock palette the grays land on pinks and greens.
"""

import pyxel

from game.render import style

# Debug/HUD colors, in slots the art never maps to. Index 0 = darkest ..
# index 3 = lightest is the art's own range and is never reordered: tile pixels
# are compared by index in tests/test_assets.py and in the reference-art test.
DEBUG_RED = 4
DEBUG_GREEN = 5
DEBUG_MAGENTA = 7
_DEBUG = (0xFF0000, 0x00FF00, 0x0080FF, 0xFF00FF, 0xFFFF00, 0x00FFFF, 0xFF8000, 0x8000FF)

#: What the four shades can be shown as, darkest first: the art's own greys, and
#: the green of the original hardware's screen. `None` is the style's own four.
#:
#: **The green is SameBoy's DMG palette** (`Core/display.c`, `GB_PALETTE_DMG`),
#: an emulator's reading of the original screen, and not the four-colour set
#: that circulates as "the Game Boy palette": that one leans yellow, and its two
#: light shades are so close that the sky and the lightest fill read as one.
LOOKS: dict[str, tuple[int, int, int, int] | None] = {
    "grey": None,
    "green": (0x081810, 0x396139, 0x84A563, 0xC6DE8C),
}
DEFAULT_LOOK = "grey"


def apply() -> None:
    """Install the palette. Must be called after pyxel.init and before assets load.

    Whatever style `art/` was generated in, because the two are one fact: the
    PNGs carry that style's colours verbatim, and it is only exact distance-0
    matching that keeps `Image.load` from mapping them onto whatever happens to
    be nearest. A palette from one style over art from another is the oldest
    trap in this repo with a new coat of paint.
    """
    shades = style.active().shades
    for i, color in enumerate(shades):
        pyxel.colors[i] = color
    for i, color in enumerate(_DEBUG):
        pyxel.colors[len(shades) + i] = color


def show(look: str) -> None:
    """Show the four shades as `look` (`LOOKS`). **After the art is loaded**, and
    never before it.

    Every picture is in the banks by index by then -- loaded against the style's
    own four by `apply`, or written by index straight out of a cartridge -- so a
    look is only what the screen shows those indices as, and nothing is re-read.
    Swapped before the load, the nearest-colour mapping would put the greys of
    the PNGs on whichever green happens to be closest.
    """
    shades = LOOKS[look] or style.active().shades
    for i, color in enumerate(shades):
        pyxel.colors[i] = color
