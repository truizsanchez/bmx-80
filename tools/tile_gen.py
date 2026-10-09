"""Generate the glyphs and the logo: the pictures no curve describes.

The crates' letters, the nitro icon, the rock, and the title screen's banner --
all of them are **drawings**, written out here as text, sixteen rows of sixteen
characters. There is no geometry behind them and there never was: a glyph is a
glyph.

The terrain used to be here too, rastered from the kit's geometry. The kit is
gone and so is that half; a terrain tile is now a drawing like everything else,
loaded by name (`game/render/assets.py`).

The plumbing every generator shares -- rasters, styles, PNG encoding, the
`--check` machinery -- is `tools/pixels.py`.
"""

import argparse
import os
import sys
from collections.abc import Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.constants import CELL  # noqa: E402
from tools.pixels import (  # noqa: E402
    _INDICES,
    Raster,
    StyleLike,
    _style,
    from_text,
    generator_arguments,
    generator_main,
    to_text,
    write_art,
)

# Tiles that are not terrain, and so are not derived from anything.
#
# The nitro icon is a glyph, and a glyph is a drawing: there is no curve it could
# be a function of, so it is written out rather than computed. Blitted with
# colkey 3, so `.` is transparent rather than white.
GLYPHS = {
    # The pickups, and the reason they are a second drawing rather than the HUD
    # icon reused: on the HUD the icon means "you have one", and on the course the
    # box has to mean "there is one here" from a distance and at speed, against
    # dirt rather than against sky. So it is a letter inside a crate -- the crate
    # says *object*, the letter says which -- and it fills more of its cell than
    # the icon does, because the icon's job is to sit in a row of eight and this
    # one's is to be spotted. Hand-authored for the same reason as the bomb: no
    # curve describes any of them.
    #
    # Three of them: N, T and the "J" -- a kind is here when it has a mechanic
    # and not before. One crate with a letter in it, drawn at the same size on the same
    # dirt: the letter is the whole of the difference, and it is the only answer
    # that survives being seen at speed.
    "item_nitro": (
        "................",
        ".##############.",
        ".#------------#.",
        ".#-##########-#.",
        ".#-#........#-#.",
        ".#-#.#....#.#-#.",
        ".#-#.##...#.#-#.",
        ".#-#.#.#..#.#-#.",
        ".#-#.#..#.#.#-#.",
        ".#-#.#...##.#-#.",
        ".#-#.#....#.#-#.",
        ".#-#........#-#.",
        ".#-##########-#.",
        ".#------------#.",
        ".##############.",
        "................",
    ),
    "item_time": (
        "................",
        ".##############.",
        ".#------------#.",
        ".#-##########-#.",
        ".#-#........#-#.",
        ".#-#.######.#-#.",
        ".#-#...##...#-#.",
        ".#-#...##...#-#.",
        ".#-#...##...#-#.",
        ".#-#...##...#-#.",
        ".#-#...##...#-#.",
        ".#-#........#-#.",
        ".#-##########-#.",
        ".#------------#.",
        ".##############.",
        "................",
    ),
    # The letter that is not a quantity: a "J" buys the air game once and for
    # ever rather than four of anything. Same crate, same
    # size, same dirt -- the letter is the whole of the difference, which is the
    # original's own answer.
    "item_jet": (
        "................",
        ".##############.",
        ".#------------#.",
        ".#-##########-#.",
        ".#-#........#-#.",
        ".#-#...####.#-#.",
        ".#-#.....#..#-#.",
        ".#-#.....#..#-#.",
        ".#-#.....#..#-#.",
        ".#-#.#...#..#-#.",
        ".#-#..###...#-#.",
        ".#-#........#-#.",
        ".#-##########-#.",
        ".#------------#.",
        ".##############.",
        "................",
    ),
    # The secret that is a rider: what taking a mini-maniac leaves on the
    # screen, the crate saying *something was here* and the little bike which.
    "item_mini": (
        "................",
        ".##############.",
        ".#------------#.",
        ".#-##########-#.",
        ".#-#........#-#.",
        ".#-#.....#..#-#.",
        ".#-#....###.#-#.",
        ".#-#.######.#-#.",
        ".#-####..####-#.",
        ".#-##-#..#-##-#.",
        ".#-####..####-#.",
        ".#-#........#-#.",
        ".#-##########-#.",
        ".#------------#.",
        ".##############.",
        "................",
    ),
    # A mini-maniac itself, riding behind the player: a bike eight pixels square
    # in the top left of its cell -- the size the cartridge draws one at, and
    # blitted by that size, the way `nitro` is blitted by half.
    "mini": (
        "................",
        ".....#..........",
        "....###.........",
        ".######.........",
        "###..###........",
        "#-#..#-#........",
        "###..###........",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
    ),
    # The counter: one nitro in hand, and eight of them are the whole stock.
    #
    # It is 8x16 in a 16x16 cell, because the row sits in the right half of the
    # HUD band and `NITRO_PITCH` is 8 -- `draw_stock` blits half a tile. The other
    # half is empty on purpose rather than by accident: the glyph is addressed by
    # name and blitted by size, so a picture that is not eight wide is a picture
    # that does not fit the row.
    #
    # An aerial bomb -- fins, waist, a shaded cylinder -- which is the original's
    # own icon and not a round bomb with a fuse. Ours is drawn a little larger
    # than 4x7 because the fins are what make the silhouette read, and at four
    # pixels across they are one row of four.
    #
    # And a bomb rather than the pickup's own "N": the crate on the course has to
    # say *there is one here* and the counter has to say *you have one*, which are
    # two jobs, and the original draws them as two pictures too.
    "nitro": (
        "................",
        "................",
        "................",
        "................",
        "#....#..........",
        "######..........",
        "..##............",
        ".#-+#...........",
        ".#-+#...........",
        ".#-+#...........",
        ".#-+#...........",
        "..##............",
        "................",
        "................",
        "................",
        "................",
    ),
    # The rock, and it is the one thing in this table that is not a crate.
    # Everything else here is a letter in a box saying *there is one here*; a
    # rock has to say *this is in the way*, so it is drawn as the thing itself.
    #
    # **Rubble at ground level**. The first attempt was an outlined dome
    # in the middle of the cell, and the play-test said two true things about
    # it: it looked raised off the ground, and it did not look like a rock. It
    # was raised -- the bottom row was empty, and a rock's cell sits directly on
    # the surface, so row 15 is the last pixel before the road. And a smooth
    # outlined dome is a cartoon boulder where a rock in the road is a scatter
    # of stones: an irregular field of dark and mid pixels, sparse at the top and
    # near-solid along the bottom. This is that, tapered at both ends so a single
    # one reads as a cluster and two together read as a longer stretch of it.
    "rock": (
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        ".....####.......",
        "...##+--+##.....",
        "..#++---+#++#...",
        ".#+-+---##+-+##.",
        ".#+###++-+++--#.",
        "#+-+#+++#++++#+#",
        ".##############.",
    ),
}


# The title screen's own picture, and the third thing in this file that no curve
# describes -- after the glyphs, and for the same reason: there is no geometry a
# logo could be a function of, so it is written out.
#
# **One picture and not sixteen tiles.** The letters cross cell boundaries, so
# authoring it cell by cell would hand a person the seams for nothing: it is
# spelled here at its own size and `slice_banner` cuts it up. Which also means
# the way to redraw it is to edit these rows. `art/hand/logo_31.png` still wins
# over the cell it names, the same as for any other tile, but for one picture in
# sixteen parts this door is the better one.
BANNER_COLS, BANNER_ROWS = 8, 2

BANNERS = {
    "logo": (
        "................................................................................................................................",
        "................................................................................................................................",
        "..##############+-......#####+-.........#####+-...#####+-.....#####+-...................#############+-........###########+-....",
        "..##############+-+-....#####+-.........#####+-...#####+-.....#####+-..................###############+-......#############+-...",
        "..################+-....######+-.......######+-...+####+-.....####++-.................#################+-....###############+-..",
        "..################+-....######+-.......######+-...-+####+-...####++--.................#################+-...#################+-.",
        "..####++++++++++##+-....#######+-.....#######+-....-#####+-.#####+--..................####+++++++++####+-...####++++++#######+-.",
        "..####+---------##+-....#######+-.....#######+-.....#####+-.#####+-...................####+--------####+-...####+-----#######+-.",
        "..####+-........##+-....########+-...########+-.....+####+-.####++-...................####+-.......####+-...####+-....#######+-.",
        "..####+-........##+-....#########+-..########+-.....-+#########++--...................####+-.......####+-...####+-....#######+-.",
        "..####+-........##+-....#########+-.#########+-......-#########+--....................####+-.......####+-...####+-...########+-.",
        "..####+-........##+-....####++####+-#########+-.......#########+-.....................####+-.......####+-...####+-...########+-.",
        "..####+-........##+-....####+-###############+-.......+#######++-.....................####+-.......####+-...####+-...##++####+-.",
        "..################+-....####+-+########++####+-.......-+#####++--.......#########+-...#################+-...####+-..###+-####+-.",
        "..################+-....####+--########+-####+-........-#####+--........#########+-...#################+-...####+-..###+-####+-.",
        "..#################+-...####+-.+######++-####+-.........#####+-.........#########+-...#################+-...####+-..##++-####+-.",
        "..#################+-...####+-.-#####++--####+-.........#####+-.........#########+-...#################+-...####+-.###+--####+-.",
        "..#################+-...####+-..++++++--.####+-........#######+-........#########+-...#################+-...####+-.##++-.####+-.",
        "..####+++++++++####+-...####+-..-------..####+-.......#########+-.......++++++++++-...####+++++++++####+-...####+-###+--.####+-.",
        "..####+--------####+-...####+-...........####+-.......#########+-.......-----------...####+--------####+-...####+-###+-..####+-.",
        "..####+-.......####+-...####+-...........####+-.......#########+-.....................####+-.......####+-...####+-##++-..####+-.",
        "..####+-.......####+-...####+-...........####+-......####+++####+-....................####+-.......####+-...########+--..####+-.",
        "..####+-.......####+-...####+-...........####+-.....#####+--#####+-...................####+-.......####+-...#######++-...####+-.",
        "..####+-.......####+-...####+-...........####+-.....#####+-.#####+-...................####+-.......####+-...#######+--...####+-.",
        "..#################+-...####+-...........####+-.....####++-.+####+-...................#################+-...#################+-.",
        "..#################+-...####+-...........####+-....####++--.-+####+-..................#################+-...+###############++-.",
        "..###############+++-...####+-...........####+-...#####+--...-#####+-.................+###############++-...-+#############++--.",
        "..###############+-+-...####+-...........####+-...#####+-.....#####+-.................-+#############++--....-+###########++--..",
        "..++++++++++++++++---...+++++-...........+++++-...++++++-.....++++++-..................-++++++++++++++--......-++++++++++++--...",
        "..-----------------.....------...........------...-------.....-------...................---------------........-------------....",
        "................................................................................................................................",
        "................................................................................................................................",
    ),
}


def slice_banner(rows: Sequence[str], cols: int = BANNER_COLS, tall: int = BANNER_ROWS,
                 prefix: str = "logo") -> dict[str, Raster]:
    """`{name: art}` for one `cols` x `tall` picture, cut into cells.

    Named `prefix_colrow`, which is the catalogue's own convention. The size is
    checked rather than assumed, for `from_text`'s reason at banner scale: a row
    one character short would not fail, it would shift every cell after it.
    """
    if len(rows) != tall * CELL or any(len(row) != cols * CELL for row in rows):
        raise ValueError(
            "a %dx%d banner is %d rows of %d characters"
            % (cols, tall, tall * CELL, cols * CELL)
        )
    art: dict[str, Raster] = {}
    for col in range(cols):
        for row in range(tall):
            art["%s_%d%d" % (prefix, col, row)] = tuple(
                _INDICES[rows[row * CELL + y][col * CELL + x]]
                for y in range(CELL)
                for x in range(CELL)
            )
    return art


def authored() -> dict[str, Raster]:
    """Every picture in this file that no curve describes: the glyphs and the
    banner.

    Everything on the `CELL` grid is one of these: the terrain is the kit's, on
    `TILE`, and comes from `terrain()`.
    """
    art = {name: from_text(text) for name, text in GLYPHS.items()}
    for prefix, rows in BANNERS.items():
        art.update(slice_banner(rows, prefix=prefix))
    return art



# -- where each picture comes from -------------------------------------------


def provenance() -> dict[str, list[str]]:
    """{name: [where, ...]} for every picture on the `CELL` grid.

    All of them are drawn by hand, so the answer is where each one is used.
    `art_check.py` joins it to the kit's terrain and to the map census.
    """
    where: dict[str, list[str]] = {
        name: ["hand-authored glyph, no curve behind it"] for name in GLYPHS}
    for prefix, rows in BANNERS.items():
        for col in range(BANNER_COLS):
            for row in range(BANNER_ROWS):
                where["%s_%d%d" % (prefix, col, row)] = [
                    "the title screen's %s, cell (%d, %d) of %dx%d -- hand-authored"
                    % (prefix, col, row, BANNER_COLS, BANNER_ROWS)
                ]
    return where




def write(directory: str, style: StyleLike = None) -> list[str]:
    """Write every `CELL` picture into `directory`. Returns the names written."""
    return write_art(directory, authored(), _style(style))


DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "tiles"
)


def main() -> int:
    """The glyphs and the logo into `--out`, with one `--check` over the lot."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    generator_arguments(parser, DEFAULT_OUT, "tiles")
    args = parser.parse_args()
    art = authored()
    if args.show in art:
        print(to_text(art[args.show]))
        return 0
    return generator_main(parser, args, art, "tiles", "this file draws")


if __name__ == "__main__":
    sys.exit(main())
