"""Every picture the game draws, on one sheet, each under its name.

    python tools/art_sheet.py [out.png]      # tools/art_sheet.png by default

The view an artist starts from. `tools/art_check.py --list` says what every
name is and where it appears, as text; this is the same set as a picture, and
in the places the pictures are *seen* together, which is the question a
drawing is judged by:

- **the terrain tiles**, each on its own;
- **the metatiles**, each four of them assembled -- a `-` quarter, which lets
  the tile underneath through, is hatched, since it has no picture of its own;
- **the pieces**, each assembled out of its metatiles at its own size, which is
  a tile seen beside its neighbours;
- **the glyphs, the logo and the bike**, the generated art -- or whatever
  `art/hand/` draws over it by name, because this draws what the game loads.

Written by the game's own loader into the game's own banks, so a drawing that
shows here is a drawing the game will show. Nothing is read from a cartridge:
with one, the bike is its sprites and the course its art, and neither is ours
to put on a sheet.
"""

import os
import sys
from collections.abc import Callable, Sequence

import pyxel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game.constants import CELL, TILE  # noqa: E402
from game.course import NOTHING, SKY_TILE, TRANSPARENT  # noqa: E402
from game.render import assets, headless  # noqa: E402
from game.render.style import EDGE, RIM, SKY  # noqa: E402
from maps import read  # noqa: E402

WIDTH = 320
MARGIN, GAP = 6, 6
#: Pyxel's built-in font: a character is four pixels across and six down.
CHAR_W, CHAR_H = 4, 6
HEADING_H = CHAR_H + 6
SCALE = 3

#: One thing to draw: its width and height, its name, and how to draw it at a
#: corner.
Entry = tuple[int, int, str, Callable[[int, int], None]]


def _tile(name: str) -> Callable[[int, int], None]:
    def draw(x: int, y: int) -> None:
        if name == SKY_TILE:
            return
        u, v = assets.terrain_uv(name)
        pyxel.blt(x, y, assets.TERRAIN_BANK, u, v, TILE, TILE)
    return draw


def _hatch(x: int, y: int) -> None:
    """A quarter that lets the one underneath through, which has no picture."""
    for d in range(0, TILE, 2):
        pyxel.pset(x + d, y + d, RIM)
        pyxel.pset(x + TILE - 1 - d, y + d, RIM)


def _metatile(quad: Sequence[str]) -> Callable[[int, int], None]:
    def draw(x: int, y: int) -> None:
        for at, name in enumerate(quad):
            tx, ty = x + (at % 2) * TILE, y + (at // 2) * TILE
            if name == TRANSPARENT:
                _hatch(tx, ty)
            else:
                _tile(name)(tx, ty)
    return draw


def _piece(grid: Sequence[Sequence[str]],
           metatiles: dict[str, Sequence[str]]) -> Callable[[int, int], None]:
    def draw(x: int, y: int) -> None:
        for row, line in enumerate(grid):
            for col, name in enumerate(line):
                if name != NOTHING:
                    _metatile(metatiles[name])(x + col * CELL, y + row * CELL)
    return draw


def _glyph(name: str) -> Callable[[int, int], None]:
    def draw(x: int, y: int) -> None:
        u, v = assets.uv(name)
        pyxel.blt(x, y, assets.BANK, u, v, CELL, CELL)
    return draw


def sections() -> list[tuple[str, list[Entry]]]:
    """What the sheet shows, in order, under a heading each."""
    metatiles: dict[str, Sequence[str]] = dict(read.metatiles())
    pieces = read.pieces()
    return [
        ("TERRAIN TILES  art/terrain/", [
            (TILE, TILE, name, _tile(name)) for name in assets.TERRAIN_TILES]),
        ("METATILES  maps/metatiles.json", [
            (CELL, CELL, name, _metatile(quad)) for name, quad in metatiles.items()]),
        ("PIECES  maps/pieces.json", [
            (max(len(line) for line in grid) * CELL, len(grid) * CELL, name,
             _piece(grid, metatiles)) for name, grid in pieces.items()]),
        ("GLYPHS AND LOGO  art/tiles/", [
            (CELL, CELL, name, _glyph(name))
            for name in assets.GLYPH_TILES + assets.SCREEN_TILES]),
        ("BIKE AND CRASH  art/moto/", [
            (CELL, CELL, name, _glyph(name))
            for name in assets.BIKE_TILES + assets.CRASH_TILES]),
    ]


#: Where a sheet puts things: the headings at their corners, and the entries.
Placed = tuple[list[tuple[int, int, str]], list[tuple[int, int, Entry]]]


def layout(parts: Sequence[tuple[str, Sequence[Entry]]]) -> tuple[int, Placed]:
    """Where everything goes: a heading a section, and its entries flowed left
    to right, each as wide as the wider of its picture and its name. Returns
    the sheet's height and what to draw where."""
    headings: list[tuple[int, int, str]] = []
    entries: list[tuple[int, int, Entry]] = []
    y = MARGIN
    for heading, section in parts:
        headings.append((MARGIN, y, heading))
        y += HEADING_H
        x, row_h = MARGIN, 0
        for entry in section:
            w, h, name, _ = entry
            box = max(w, len(name) * CHAR_W)
            if x + box > WIDTH - MARGIN and x > MARGIN:
                x, y, row_h = MARGIN, y + row_h + GAP, 0
            entries.append((x, y, entry))
            row_h = max(row_h, h + 2 + CHAR_H)
            x += box + GAP
        y += row_h + GAP + 2
    return y, (headings, entries)


def draw(placed: Placed) -> None:
    headings, entries = placed
    pyxel.cls(SKY)
    for x, y, heading in headings:
        pyxel.text(x, y, heading, EDGE)
    for x, y, (w, h, name, picture) in entries:
        pyxel.rectb(x - 1, y - 1, w + 2, h + 2, RIM)
        picture(x, y)
        pyxel.text(x, y + h + 2, name, EDGE)


def main() -> None:
    # Beside this file by default, which `.gitignore` keeps out of a commit.
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                          else os.path.join(ROOT, "tools", "art_sheet.png"))
    # The layout needs the lists and not the banks, so the size is known before
    # the window it decides.
    height, placed = layout(sections())
    headless.boot(WIDTH, height, chdir_to=__file__)
    draw(placed)
    pyxel.screenshot(out[:-4] if out.endswith(".png") else out, scale=SCALE)
    print(out if out.endswith(".png") else out + ".png")


if __name__ == "__main__":
    main()
