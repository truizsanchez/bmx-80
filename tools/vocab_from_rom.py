"""The original's vocabulary and its eight courses, written as this game's own.

    python tools/vocab_from_rom.py --rom <file.gb>          # write maps/ and art/terrain/
    python tools/vocab_from_rom.py --rom <file.gb> --check  # ...or say they still match

**The vocabulary in `maps/` is the original's**: the same tiles, colliding as
the cartridge's own byte says, the same 168 metatiles and the same prefab
pieces, under the original's own numbers in hex -- `t45` is tile 0x45, `m1a`
metatile 0x1a, `p57` piece 0x57. The six metatiles the engine knows by id keep
the names `game/course.RESERVED` gives them, which are the original's ids too.
The eight courses are its courses, each a list of those pieces stamped in
order, in `maps/courses/course1.json` to `course8.json`.

**The art is this game's, over the original's shapes.** A tile with no drawing
in `art/terrain/` is given one: of the original's picture only its silhouette
is read -- which pixels are something and which are sky -- and that is painted
in this game's own way, by what the tile collides as: ground dark and flecked,
sand light and dotted, scenery light grey, each outlined in black where it
meets the sky. The shapes are the original's because the courses are, and the
collision is; everything else about the picture is this game's. A drawing is
never overwritten once it is there, so a tile drawn over by hand stays drawn.

`--check` builds every course as the game builds it (`maps/read.py`) and
compares it, cell by cell, with the course as the cartridge builds it
(`game/rom/course.py`). One difference is expected and allowed: a transparent
tile stamped on an empty cell is sky here and tile 0x7F there, and 0x7F
collides as nothing. Then it **rides** each both ways, with the same buttons
pressed at random, and says whether the bike is in the same place, attitude
and state at every iteration -- which is what the probe table and the throw in
`maps/tables.json` are there for.
"""

import argparse
import json
import os
import random
import sys
from collections.abc import Sequence
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.constants import TILE  # noqa: E402
from game.course import (ATTITUDES, CRATES, METATILE_TILES, NOTHING,  # noqa: E402
                         ORIGINAL_TILE, RESERVED, TRANSPARENT)
from game.engine.original import LEFT, RIGHT, THROTTLE, UP
from game.engine.run import Run  # noqa: E402
from game.engine.original import THROW_STEPS
from game.render.style import BULK, EDGE, RIM, SKY  # noqa: E402
from game.rom import course as rom, graphics  # noqa: E402
from game.rom.cartridge import Cartridge, NotTheCartridge  # noqa: E402
from maps import read  # noqa: E402
from tools.pixels import encode_png  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERRAIN = os.path.join(ROOT, "art", "terrain")
LEVELS = 3


def tile_name(tile: int) -> str:
    return ORIGINAL_TILE % tile


def metatile_name(metatile: int) -> str:
    return RESERVED[metatile] if metatile < len(RESERVED) else "m%02x" % metatile


def piece_name(piece: int) -> str:
    return "p%02x" % piece


def quad(cartridge: Cartridge, metatile: int) -> list[int]:
    at = rom.METATILES + 4 * metatile
    return list(cartridge.data[at:at + 4])


def stampings(cartridge: Cartridge, course: int) -> list[tuple[int, int, int]]:
    """A course's pieces as `(row, col, piece)`, in the order they are stamped."""
    at = cartridge.word(rom.COURSES + 2 * (course - 1))
    out = []
    while cartridge.byte(at) != rom.EMPTY:
        out.append((cartridge.byte(at), cartridge.byte(at + 1), cartridge.byte(at + 2)))
        at += 3
    return out


def piece(cartridge: Cartridge, number: int) -> list[list[str]]:
    """A prefab piece as a grid of metatile names, `.` where it stamps nothing."""
    at = cartridge.word(rom.PIECES + 2 * number)
    rows, cols = cartridge.byte(at), cartridge.byte(at + 1)
    at += 2
    return [[NOTHING if value == rom.EMPTY else metatile_name(value)
             for value in cartridge.data[at + r * cols:at + (r + 1) * cols]]
            for r in range(rows)]


def vocabulary(cartridge: Cartridge) -> dict[str, Any]:
    """Everything `maps/` holds, as the files' contents."""
    metatiles = {metatile_name(m): [TRANSPARENT if t == rom.TRANSPARENT else tile_name(t)
                                    for t in quad(cartridge, m)]
                 for m in range(rom.FIRST_MADE)}
    used = _used_tiles(cartridge)
    numbers = sorted({p for n in range(1, rom.COUNT + 1) for _, _, p in stampings(cartridge, n)})
    tables = {"probes": [list(cartridge.probes(a)) for a in range(ATTITUDES)],
              "throw": [list(cartridge.throw(step)) for step in range(THROW_STEPS)]}
    return {"tiles": {tile_name(t): _tile(cartridge, t) for t in used},
            "metatiles": metatiles,
            "pieces": {piece_name(p): piece(cartridge, p) for p in numbers},
            "tables": tables,
            "courses": {"course%d" % n: _course(cartridge, n) for n in range(1, rom.COUNT + 1)}}


def _used_tiles(cartridge: Cartridge) -> list[int]:
    """Every tile the original's metatiles put down, in order."""
    return sorted({t for m in range(rom.FIRST_MADE) for t in quad(cartridge, m)
                   if t != rom.TRANSPARENT})


def _tile(cartridge: Cartridge, tile: int) -> dict[str, Any]:
    """What a tile collides as, saying only what differs from solid level ground."""
    hit = cartridge.hit(tile)
    what: dict[str, Any] = {}
    if not hit.solid:
        what["solid"] = False
    if hit.soft:
        what["soft"] = True
    if hit.no_wheelie:
        what["no_wheelie"] = True
    if hit.direction:
        what["dir"] = hit.direction
    if tile == rom.ROCK:
        what["rock"] = True
    return what


def _course(cartridge: Cartridge, number: int) -> dict[str, Any]:
    """One course's file: its pieces, its crates, its clocks and its teleports."""
    kinds = {value: kind for kind, value in CRATES.items()}
    built = rom.Course(cartridge, number)
    return {
        "pieces": [[row, col, piece_name(p)] for row, col, p in stampings(cartridge, number)],
        "items": [[kinds[kind], row, col] for kind, row, col in built.items()],
        "limits": [cartridge.limit(number, level) / 100 for level in range(LEVELS)],
        "teleports": [list(one) for one in built.teleports()],
    }


# -- the art -------------------------------------------------------------------


#: The fewest pixels a patch of sky has to have to be sky and not a speck of the
#: original's drawing showing through: the gap under a sign is far wider, and a
#: letter's counter is narrower.
SKY_PATCH = 6


def _patch(shape: list[bool], seen: list[bool], start: int) -> tuple[list[int], bool]:
    """The patch of sky `start` is in, marked seen, and whether it reaches the
    edge of the tile."""
    patch, todo, edge = [], [start], False
    while todo:
        at = todo.pop()
        if seen[at] or shape[at]:
            continue
        seen[at] = True
        patch.append(at)
        x, y = at % TILE, at // TILE
        edge = edge or x in (0, TILE - 1) or y in (0, TILE - 1)
        todo += [y * TILE + x + dx for dx in (-1, 1) if 0 <= x + dx < TILE]
        todo += [(y + dy) * TILE + x for dy in (-1, 1) if 0 <= y + dy < TILE]
    return patch, edge


def silhouette(video: bytes | bytearray, tile: int) -> list[bool]:
    """Which pixels of the original's tile are something, and not sky -- the
    one thing read off its picture.

    **With its holes filled**: sky is a patch of at least `SKY_PATCH` pixels
    that reaches the edge of the tile. Anything less is part of the original's
    drawing -- a stripe in the road, the letters on a sign, a gap in a figure --
    and not of its outline, so it is not read."""
    shape = [colour != 0 for colour in graphics.pixels(video, tile)]
    seen = [False] * (TILE * TILE)
    for start in range(TILE * TILE):
        if shape[start] or seen[start]:
            continue
        patch, edge = _patch(shape, seen, start)
        if not edge or len(patch) < SKY_PATCH:
            for at in patch:
                shape[at] = True
    return shape


def fleck(x: int, y: int, tile: int) -> bool:
    """One pixel in eleven, placed by the pixel and the tile, so that a row of
    the same ground does not repeat one pattern at every tile."""
    return (x * 7 + y * 13 + tile * 5) % 11 == 0


def drawing(shape: Sequence[bool], hit: dict[str, Any], tile: int) -> list[int]:
    """A tile in this game's own art over a silhouette: black where the shape
    meets the sky inside the tile, and inside it, by what the tile is -- ground
    dark with light flecks, sand light with dark dots, scenery plain light grey."""
    solid, soft = hit.get("solid", True), hit.get("soft", False)
    art = []
    for y in range(TILE):
        for x in range(TILE):
            if not shape[y * TILE + x]:
                art.append(SKY)
                continue
            edge = any(0 <= x + dx < TILE and 0 <= y + dy < TILE
                       and not shape[(y + dy) * TILE + x + dx]
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if edge:
                art.append(EDGE)
            elif not solid:
                art.append(RIM)
            elif soft:
                art.append(EDGE if fleck(x, y, tile) else RIM)
            else:
                art.append(RIM if fleck(x, y, tile) else BULK)
    return art


def write_art(tiles: dict[str, dict[str, Any]], video: bytes | bytearray) -> list[str]:
    """A drawing for every tile that has none, and nothing else touched."""
    written = []
    for name, hit in tiles.items():
        path = os.path.join(TERRAIN, name + ".png")
        if not os.path.exists(path):
            tile = int(name[1:], 16)
            with open(path, "wb") as handle:
                handle.write(encode_png(drawing(silhouette(video, tile), hit, tile), TILE, TILE))
            written.append(name)
    return written


# -- writing and checking ------------------------------------------------------


def _json(value: Any) -> str:
    return json.dumps(value, indent=1) + "\n"


def write(found: dict[str, Any], video: bytes | bytearray) -> None:
    for key, name in (("tiles", read.TILES), ("metatiles", read.METATILES)):
        with open(os.path.join(read.HERE, name), "w") as handle:
            handle.write(_json(found[key]))
    with open(os.path.join(read.HERE, read.TABLES), "w") as handle:
        handle.write("{\n" + ",\n".join(
            " %s: [\n%s\n ]" % (json.dumps(key), ",\n".join("  " + json.dumps(row) for row in rows))
            for key, rows in found["tables"].items()) + "\n}\n")
    with open(os.path.join(read.HERE, read.PIECES), "w") as handle:
        handle.write("{\n" + ",\n".join(" %s: %s" % (json.dumps(name), json.dumps(grid))
                                        for name, grid in found["pieces"].items()) + "\n}\n")
    os.makedirs(read.COURSE_DIR, exist_ok=True)
    for name, data in found["courses"].items():
        with open(os.path.join(read.COURSE_DIR, name + ".json"), "w") as handle:
            handle.write(read.dump(data))
    print("wrote %d tiles, %d metatiles, %d pieces, %d courses; %d drawings new"
          % (len(found["tiles"]), len(found["metatiles"]), len(found["pieces"]),
             len(found["courses"]), len(write_art(found["tiles"], video))))


def differences(cartridge: Cartridge, number: int) -> int:
    """Cells of the 8 px grid where the course in `maps/` is not the cartridge's."""
    original = rom.Course(cartridge, number)
    ours = read.course(os.path.join(read.COURSE_DIR, "course%d.json" % number))
    names = ours.tiles_of.names
    wrong = 0
    for row in range(rom.ROWS * METATILE_TILES):
        for col in range(rom.COLS * METATILE_TILES):
            theirs = original.tile(col, row)
            metatile = ours.metatile(row // METATILE_TILES, col // METATILE_TILES)
            mine = (None if metatile == rom.EMPTY else
                    ours.tiles(metatile)[(row % METATILE_TILES) * METATILE_TILES
                                         + col % METATILE_TILES])
            if theirs == rom.TRANSPARENT and not mine:
                continue
            if (None if theirs is None else tile_name(theirs)) != names.get(mine or 0):
                wrong += 1
            elif mine and ours.collision(mine) != original.collision(theirs or 0):
                wrong += 1
    return wrong


#: How long each course is ridden both ways, and the buttons a rider picks from.
RIDE_ITERATIONS = 3000
BUTTONS = (THROTTLE, THROTTLE | LEFT, THROTTLE | RIGHT, THROTTLE | UP, LEFT, RIGHT, 0)


def rides_apart(cartridge: Cartridge, number: int) -> int | None:
    """The first iteration the course in `maps/` rides differently from the
    cartridge's, with the same buttons held; None when it never does."""
    rng = random.Random(number)
    held = [rng.choice(BUTTONS) for _ in range(RIDE_ITERATIONS)]
    runs = (Run(rom.Course(cartridge, number), limit=60000),
            Run(read.course(os.path.join(read.COURSE_DIR, "course%d.json" % number)), limit=60000))
    for step, buttons in enumerate(held):
        for run in runs:
            run.step(buttons)
        theirs, ours = (run.bike for run in runs)
        if (theirs.px, theirs.attitude, theirs.state) != (ours.px, ours.attitude, ours.state):
            return step
    return None


def check(cartridge: Cartridge) -> int:
    found = vocabulary(cartridge)
    stale = [name for key, name in (("tiles", read.TILES), ("metatiles", read.METATILES),
                                    ("pieces", read.PIECES), ("tables", read.TABLES))
             if json.load(open(os.path.join(read.HERE, name))) != found[key]]
    bad = 0
    for number in range(1, rom.COUNT + 1):
        wrong = differences(cartridge, number)
        apart = rides_apart(cartridge, number)
        print("course%d: %s, %s" % (
            number, "the original's" if not wrong else "%d cells differ" % wrong,
            "rides as the original's" if apart is None else "rides apart at %d" % apart))
        bad += wrong + (apart is not None)
    for name in stale:
        print("%s is not the cartridge's" % name)
    return 1 if bad or stale else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", required=True, help="your Motocross Maniacs cartridge file")
    parser.add_argument("--check", action="store_true",
                        help="say whether maps/ is still the cartridge's, and write nothing")
    args = parser.parse_args()
    try:
        cartridge = Cartridge.from_file(args.rom)
    except (OSError, NotTheCartridge) as refused:
        print("cannot read %s: %s" % (args.rom, refused))
        return 1
    if args.check:
        return check(cartridge)
    write(vocabulary(cartridge), graphics.video(cartridge))
    return 0


if __name__ == "__main__":
    sys.exit(main())
