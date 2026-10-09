"""A course of the original, read from your cartridge, drawn as the collision sees it.

    python tools/rom_shot.py --rom <file.gb> [course ...] [--out DIR]

One pixel per pixel of the lap, 4096 x 256, a tile at a time: sky is white,
solid ground black where it is level and grey where it slopes, and sand light
grey. What it draws is what the engine will ride, which is why this is the
picture to look at before trusting a reading of the cartridge -- the art is not
read yet, and would say less about the ground than this does.

The cartridge is yours: nothing is written but the PNGs, `rom_<n>.png` in `--out`.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.constants import TILE  # noqa: E402
from game.rom.cartridge import Cartridge, NotTheCartridge  # noqa: E402
from game.rom.course import COLS, COUNT, METATILE_TILES, ROWS, Course  # noqa: E402
from tools.pixels import encode_rgb  # noqa: E402

SKY = (255, 255, 255)
LEVEL = (0, 0, 0)
SLOPE = (110, 110, 110)
SAND = (200, 200, 200)


def picture(course: Course) -> bytes:
    """The PNG of one course's collision."""
    cols, rows = COLS * METATILE_TILES, ROWS * METATILE_TILES
    width = cols * TILE
    rgb = bytearray()
    for row in range(rows):
        line = bytearray()
        for col in range(cols):
            hit = course.hit(col, row)
            colour = (SKY if not hit.solid else SAND if hit.soft
                      else LEVEL if hit.direction == 0 else SLOPE)
            line += bytes(colour) * TILE
        rgb += bytes(line) * TILE
    return encode_rgb(width, rows * TILE, bytes(rgb))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("courses", nargs="*", type=int, help="1-8; none draws them all")
    parser.add_argument("--rom", required=True, help="your Motocross Maniacs cartridge file")
    parser.add_argument("--out", default=".", help="directory for the PNGs")
    args = parser.parse_args()
    try:
        cartridge = Cartridge.from_file(args.rom)
    except (OSError, NotTheCartridge) as refused:
        print("cannot read %s: %s" % (args.rom, refused))
        return 1
    for number in args.courses or range(1, COUNT + 1):
        path = os.path.join(os.path.abspath(args.out), "rom_%d.png" % number)
        with open(path, "wb") as handle:
            handle.write(picture(Course(cartridge, number)))
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
