"""What the art looks like, as data both the generator and the game can read.

One picture in this game is still *derived*: `tools/sprite_gen.py` rasters the
bike from its model. What that leaves over is everything the model does not
decide -- which four colours, how thick the line, what fills the mass. Left
alone those are constants scattered across the generators with a single flag as
the only dial; a style collects them in one place, so a change of look is a
regeneration rather than an edit. Everything else -- the glyphs, the logo, and
now the terrain -- is drawn, and a drawing carries its own colours.

**The active style is a property of `art/`, not of the source.** The generated
PNGs carry the style's colours verbatim, and `palette.apply` has to install the
same four values or `Image.load`'s nearest-colour mapping stops being exact --
which is the palette trap `tests/test_assets.py` guards. So the two
cannot be allowed to disagree, and the honest place to record which one is in
force is next to the pictures it produced: `art/STYLE`, one word, written by the
generator and read by the game.

This module imports nothing. It is read by `game/render/palette.py`, which needs
Pyxel, and by `tools/pixels.py`, which must not have it.
"""

import os
from typing import Iterable, Mapping

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART_ROOT = os.path.join(_ROOT, "art")
ACTIVE_FILE = os.path.join(ART_ROOT, "STYLE")

# Palette indices, by role. Not a style's to change: the art is addressed by
# index everywhere -- `draw_hud` writes in 0, every blit uses 3 as its colkey --
# so a style says what colour each index *is* and never which index means what.
SKY, EDGE, RIM, BULK = 3, 0, 2, 1

FLAT = ("." * 16,) * 16  # no speckle at all, for a style with no grain in it

# Sixteen rows of sixteen, `o` for a speckle -- and what a style keys by
# texture name: the pattern, the mass's shade and the speckle's.
Pattern = tuple[str, ...]
Texture = tuple[Pattern, int, int]


class Style:
    """One complete look: four colours, two thresholds and the textures.

    `shades` is indexed by *palette index*, so `shades[EDGE]` is the line's
    colour and `shades[SKY]` is the background. Reordering it would change what
    every index in the game means, which is why the roles are module constants
    above and not a style's business.

    `textures` maps a piece's `texture` name to `(pattern, mass, speckle)` -- the
    speckle and the two shades it alternates. The dirt is the dark shade with
    light dots and the sand is the light one with dark dots, and that inversion is
    what makes them tell apart at a glance; a difference in dot *count* is not
    something anybody sees in the eight pixels of a floor cell.

    `hollow` draws the outline and nothing else, and `shell` draws the outline and
    the rim under it. Neither is set by a shipped style: `hollow` has been the one
    thing a style can say that the four colours cannot, and `shell` is asked for
    per cell through `shelled()` to draw a piece's line in a cell outside its own
    box. The two are the same idea at different depths -- how far
    into the material this picture is allowed to go.
    """

    def __init__(self, name: str, shades: Iterable[int],
                 textures: Mapping[str, Texture] | None = None,
                 edge_t: float = 1.0, rim_t: float = 2.5, hollow: bool = False,
                 shell: bool = False) -> None:
        self.name = name
        self.shades = tuple(shades)
        self.textures = dict(textures or {})
        # A bike is a machine, not a material, so its mass is the flat shade
        # whatever the ground is made of. Named rather than special-cased, so a
        # style that wants a neon bike on dithered dirt can just say so.
        self.textures.setdefault("bike", (FLAT, BULK, BULK))
        # EDGE_T = 1.0 gives a one-pixel outline on a flat (pixel centres sit
        # 0.5 off it) *and* on a 45 (0.707), so the line has the same weight in
        # every direction the game has surfaces in. At 2.0 a flat would get two
        # rows and a diagonal still one. RIM_T lights a lip just under it.
        self.edge_t = edge_t
        self.rim_t = rim_t
        self.hollow = hollow
        # `shell` keeps the two bands the *curve* decides -- the line and the rim
        # under it -- and drops the bulk, which is the one the material decides.
        # A piece's spill is drawn with it: outside its own box a piece may say
        # where its surface is and may not say what is behind it.
        self.shell = shell

    def shelled(self) -> "Style":
        """The same look with the bulk taken out: the line, its rim, and sky.

        Not a second style and not a setting -- a view of this one, so a spill
        tile cannot drift away from the look the rest of the art was generated
        in. `tools/tile_gen.render` asks for it per cell.

        **The line drawn alone is not enough, and that was measured rather than
        reasoned.** `shade` has three bands and only two of them are the curve's: the
        line at `edge_t` and the rim at `rim_t` are a distance from the surface,
        while the bulk is the material's own speckle. Dropping the bulk is the
        honest cut -- outside its box a piece may say where its surface is and
        may not say what is behind it -- and dropping the rim as well left the
        black line continuous with a grey one broken beside it.
        """
        if self.shell:
            return self
        return Style(
            self.name,
            self.shades,
            self.textures,
            edge_t=self.edge_t,
            rim_t=self.rim_t,
            hollow=self.hollow,
            shell=True,
        )

    def shade(self, distance: float, x: int = 0, y: int = 0, texture: str = "dirt") -> int:
        """Palette index for a point `distance` inside the material (>= 0)."""
        if distance <= self.edge_t + 1e-9:
            return EDGE
        if self.hollow:
            return SKY
        if distance <= self.rim_t:
            return RIM
        if self.shell:
            return SKY
        pattern, mass, speckle = self.textures[texture]
        return speckle if pattern[y % 16][x % 16] == "o" else mass


# The four greys the whole project draws in: black, two greys and white, evenly enough spaced that a four-step ramp reads as depth.
#
# **One look, and it is called `mono` because that is what it is.** There were
# others and they went for a reason worth keeping: a look you cannot check
# against anything is a look with no argument.
#
# These four are also the whole of what is asked of a contributor's drawing.
# `Image.load` maps every source pixel to the *nearest* entry, so a fifth colour
# does not raise -- it becomes one of the four in silence and the picture on the
# screen is not the one that was drawn. Every check that reads them reads them
# from here, so raising the count one day is a change to this tuple and not a
# sweep through the tools.
MONO = Style(
    "mono",
    shades=(0x000000, 0x606060, 0xA8A8A8, 0xF8F8F8),
    # **No terrain textures any more.** They were the dirt's dither and the
    # sand's grain field, and they existed because the terrain was rastered from
    # geometry and had to be given a surface. A drawn tile brings its own, so the
    # only texture left is the bike's, and `Style` sets that itself.
)

STYLES = {style.name: style for style in (MONO,)}
DEFAULT = MONO.name


def active() -> Style:
    """Which style `art/` was generated in. `art/STYLE`, or the default."""
    try:
        with open(ACTIVE_FILE) as handle:
            name = handle.read().strip()
    except OSError:
        return STYLES[DEFAULT]
    if name not in STYLES:
        raise ValueError("%s names a style that does not exist: %r" % (ACTIVE_FILE, name))
    return STYLES[name]


def record(style: Style) -> None:
    """Write down which style the art in `art/` was generated in."""
    os.makedirs(ART_ROOT, exist_ok=True)
    with open(ACTIVE_FILE, "w") as handle:
        handle.write(style.name + "\n")
