"""Names a person can read, for the vocabulary's metatiles and pieces.

    python tools/label_vocab.py            # fill in maps/labels.json, keeping every entry it has
    python tools/label_vocab.py --check    # say what has no label; exit 1 if anything

The vocabulary is the original's, under the original's own numbers -- `m1a` is its
metatile 0x1A, `p57` its piece 0x57 -- which is what keeps it traceable against a
cartridge and what makes it unreadable in an editor. `maps/labels.json` is the
layer on top: for every metatile and piece, a **name** and a **kind** the editor
shows and groups the palette by. The ids stay what they are.

**What this writes is a first draft, and the file is content from then on.** A
metatile's kind is read off what its tiles collide as -- ground, a slope up or
down, a curve of a wall or a ceiling, sand, a rock, or scenery that collides
with nothing -- and a piece's off the profile of its top surface. The names say
the same in a few words. A person renames them; running this again only adds
what is missing and never overwrites an entry.
"""

import argparse
import collections
import json
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game.course import NOTHING, SKY_TILE, TRANSPARENT  # noqa: E402
from game.engine.original import DIRECTIONS, QUADRANT  # noqa: E402
from maps import read  # noqa: E402

#: A metatile's kinds, in the order the editor's palette shows them.
METATILE_KINDS = ("ground", "slope up", "slope down", "curve", "sand", "rock", "scenery",
                  "special")
#: ...and a piece's.
PIECE_KINDS = ("road", "ramp up", "ramp down", "hill", "dip", "loop", "sand", "rocks",
               "sign", "scenery", "mixed")

#: The metatiles that are not ground at all, by the prefix of their names:
#: the crates and the finish's sign are the course's furniture.
SPECIAL_PREFIXES = ("crate_", "goal_")

#: A quarter's place in a metatile, as the four tiles are listed.
QUARTERS = ("top left", "top right", "bottom left", "bottom right")
#: What a set of solid quarters is called, by which of the four they are.
SHAPES: dict[tuple[int, ...], str] = {(1, 1, 1, 1): "full", (0, 0, 1, 1): "bottom", (1, 1, 0, 0): "top",
          (1, 0, 1, 0): "left", (0, 1, 0, 1): "right"}


def _hit(tiles: Mapping[str, Mapping[str, Any]], name: str) -> Mapping[str, Any] | None:
    """What a tile collides as, or None where there is no tile to collide."""
    if name in (SKY_TILE, TRANSPARENT):
        return None
    return tiles.get(name, {})


def _solid(hit: Mapping[str, Any] | None) -> bool:
    return hit is not None and bool(hit.get("solid", True))


def _degrees(direction: int) -> int:
    """A direction's steepness, in whole degrees off the level."""
    steps = min(direction, DIRECTIONS - direction)
    return round(steps * 360 / DIRECTIONS)


def metatile_label(name: str, quad: Sequence[str],
                   tiles: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """A metatile's first draft: its kind and a short name, from its four tiles."""
    if name.startswith(SPECIAL_PREFIXES):
        return {"kind": "special", "name": name.replace("_", " ")}
    hits = [_hit(tiles, tile) for tile in quad]
    if all(hit is None for hit in hits):
        return {"kind": "special", "name": "transparent"}
    solid = [hit for hit in hits if hit is not None and _solid(hit)]
    shape = SHAPES.get(tuple(int(_solid(hit)) for hit in hits))
    kind, word = _ground_kind(solid)
    return {"kind": kind, "name": word + (" " + shape if shape and kind != "curve" else "")}


def _ground_kind(solid: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    """What the solid tiles of a metatile make it, and the word for it."""
    if not solid:
        return "scenery", "scenery"
    if any(hit.get("rock") for hit in solid):
        return "rock", "rock"
    if any(hit.get("soft") for hit in solid):
        return "sand", "sand"
    steepest = max((hit.get("dir", 0) for hit in solid), key=lambda d: min(d, DIRECTIONS - d))
    if steepest == 0:
        return "ground", "ground"
    if steepest < QUADRANT:
        return "slope up", "up %d" % _degrees(steepest)
    if steepest > DIRECTIONS - QUADRANT:
        return "slope down", "down %d" % _degrees(steepest)
    return "curve", "curve %d" % round(steepest * 360 / DIRECTIONS)


def _surface(grid: Sequence[Sequence[str]], metatiles: Mapping[str, Sequence[str]],
             tiles: Mapping[str, Mapping[str, Any]]) -> list[int]:
    """For each tile column of a piece, the direction of the first solid tile
    down it -- the surface a bike rides -- where there is one."""
    rows, cols = len(grid) * 2, max((len(row) for row in grid), default=0) * 2
    surface: list[int] = []
    for col in range(cols):
        for row in range(rows):
            cell = grid[row // 2][col // 2] if col // 2 < len(grid[row // 2]) else NOTHING
            if cell == NOTHING or cell not in metatiles:
                continue
            hit = _hit(tiles, metatiles[cell][(row % 2) * 2 + col % 2])
            if hit is not None and _solid(hit):
                surface.append(hit.get("dir", 0))
                break
    return surface


def _profile(surface: Sequence[int]) -> str:
    """The surface's shape, left to right: flat, rising, falling, both ways."""
    slopes = ["up" if 0 < d < QUADRANT else "down" for d in surface
              if 0 < d < QUADRANT or d > DIRECTIONS - QUADRANT]
    # A road with its ends bevelled is still a road: two thirds of it level.
    if not slopes or len(slopes) * 3 <= len(surface):
        return "road"
    if "down" not in slopes:
        return "ramp up"
    if "up" not in slopes:
        return "ramp down"
    turns = sum(1 for a, b in zip(slopes, slopes[1:]) if a != b)
    if turns == 1:
        return "hill" if slopes[0] == "up" else "dip"
    return "mixed"


def piece_label(name: str, grid: Sequence[Sequence[str]],
                metatiles: Mapping[str, Sequence[str]],
                tiles: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """A piece's first draft: its kind and a short name, from its surface."""
    cells = [cell for row in grid for cell in row if cell != NOTHING and cell in metatiles]
    drawn = [hit for cell in cells for hit in (_hit(tiles, t) for t in metatiles[cell])
             if hit is not None]
    solid = [hit for hit in drawn if _solid(hit)]
    kind = _piece_kind(drawn, solid) or _profile(_surface(grid, metatiles, tiles))
    size = "%dx%d" % (max((len(row) for row in grid), default=0), len(grid))
    return {"kind": kind, "name": "%s %s" % (kind, size)}


def _piece_kind(drawn: Sequence[Mapping[str, Any]],
                solid: Sequence[Mapping[str, Any]]) -> str | None:
    """A piece's kind where what it is made of decides it, before its shape
    does: scenery, a sign, rocks, a loop, sand -- or None."""
    if not solid:
        return "scenery"
    if len(drawn) - len(solid) >= max(4, len(drawn) // 2):
        return "sign"
    if any(hit.get("rock") for hit in solid):
        return "rocks"
    if any(QUADRANT <= hit.get("dir", 0) <= DIRECTIONS - QUADRANT for hit in solid):
        return "loop"
    if any(hit.get("soft") for hit in solid):
        return "sand"
    return None


def drafted(where: read.Where = read.CLASSIC) -> dict[str, dict[str, dict[str, str]]]:
    """A first draft for every metatile and piece of a vocabulary.

    Two passes. The first reads each on its own: what a metatile's tiles collide
    as, and the shape of a piece's surface. The second says what tells apart the
    ones the first left alike -- a piece's angle, the road before or after its
    ramp, where a loop's curve starts and ends, a ramp that is a thin strip; a
    metatile's part in the pieces it is stamped in, as their surface or their
    fill, and where a piece of scenery sits in the sign it belongs to. **Never a
    number or a letter that means nothing**: what is still alike is left alike.
    """
    tiles = read.tile_declarations(where)
    metatiles = read.metatiles(where)
    grids = read.pieces(where)
    pieces = {name: piece_label(name, grid, metatiles, tiles) for name, grid in grids.items()}
    first_of: dict[str, str] = {}
    for name, grid in grids.items():
        pieces[name]["name"] = _piece_name(pieces[name]["kind"], grid, metatiles, tiles)
        # A piece stamped exactly as an earlier one is that one again, and says so.
        same = first_of.setdefault(json.dumps(grid), name)
        if same != name:
            pieces[name]["name"] += " same as " + same
    labels = {name: metatile_label(name, quad, tiles) for name, quad in metatiles.items()}
    uses = _uses(grids, pieces, metatiles, tiles)
    for name, label in labels.items():
        if label["kind"] != "special":
            label["name"] = _metatile_name(label, uses.get(name, []))
    return {"metatiles": labels, "pieces": pieces}


#: A direction as the part of a loop it is, round the circle from the floor.
HEADINGS = ((0, "floor"), (1, "rise"), (QUADRANT, "wall"), (QUADRANT + 1, "overhang"),
            (2 * QUADRANT, "ceiling"), (2 * QUADRANT + 1, "overhang"),
            (3 * QUADRANT, "wall"), (3 * QUADRANT + 1, "fall"))


def _heading(direction: int) -> str:
    return [word for at, word in HEADINGS if direction >= at][-1]


def _piece_name(kind: str, grid: Sequence[Sequence[str]],
                metatiles: Mapping[str, Sequence[str]],
                tiles: Mapping[str, Mapping[str, Any]]) -> str:
    """A piece's kind, what tells it apart, and its size in metatiles."""
    surface = _surface(grid, metatiles, tiles)
    size = "%dx%d" % (max((len(row) for row in grid), default=0), len(grid))
    words = [kind] + _piece_details(kind, surface) + [size]
    if kind in ("ramp up", "ramp down") and _thin(grid, metatiles, tiles):
        words.insert(-1, "thin")
    return " ".join(words)


def _piece_details(kind: str, surface: Sequence[int]) -> list[str]:
    """What a piece's surface says about it beyond its kind."""
    if not surface:
        return []
    if kind == "loop":
        return ["%s to %s" % (_heading(surface[0]), _heading(surface[-1]))]
    if kind == "road":
        return (["in"] if surface[0] else []) + (["out"] if surface[-1] else [])
    slopes = [d for d in surface if d]
    if not slopes:
        return []
    words = ["%d" % max(_degrees(d) for d in slopes)] if kind in SLOPED else []
    return words + _road_around(surface)


#: The kinds whose steepest slope is part of their name.
SLOPED = ("ramp up", "ramp down", "hill", "dip")


def _road_around(surface: Sequence[int]) -> list[str]:
    """Whether a piece's slope has level road before it, after it, or both."""
    return (["road before"] if not surface[0] else []) + \
           (["road after"] if not surface[-1] else [])


def _thin(grid: Sequence[Sequence[str]], metatiles: Mapping[str, Sequence[str]],
          tiles: Mapping[str, Mapping[str, Any]]) -> bool:
    """Whether a ramp is a strip with sky under it, rather than solid to the bottom."""
    cells = [(row, col) for row, line in enumerate(grid) for col, cell in enumerate(line)
             if cell != NOTHING and cell in metatiles]
    solid = sum(1 for row, col in cells
                if any(_solid(_hit(tiles, t)) for t in metatiles[grid[row][col]]))
    width = max((len(line) for line in grid), default=0)
    return solid * 2 < width * len(grid)


#: Where a metatile is stamped: the piece's kind and name, where in it, and
#: whether it is the surface -- nothing solid above it.
Use = tuple[str, str, str, bool]


def _uses(grids: Mapping[str, Sequence[Sequence[str]]],
          pieces: Mapping[str, Mapping[str, str]],
          metatiles: Mapping[str, Sequence[str]],
          tiles: Mapping[str, Mapping[str, Any]]) -> dict[str, list[Use]]:
    """Where each metatile is stamped in the pieces."""
    uses: dict[str, list[Use]] = {}
    for name, grid in grids.items():
        for row, line in enumerate(grid):
            for col, cell in enumerate(line):
                if cell == NOTHING or cell not in metatiles:
                    continue
                above = grid[row - 1][col] if row and col < len(grid[row - 1]) else NOTHING
                open_above = above == NOTHING or above not in metatiles or not any(
                    _solid(_hit(tiles, t)) for t in metatiles[above][2:])
                where = _place(row, col, len(grid), len(line))
                uses.setdefault(cell, []).append((pieces[name]["kind"], name, where, open_above))
    return uses


def _place(row: int, col: int, rows: int, cols: int) -> str:
    """Where a cell sits in its piece, in words: top left, bottom, row 2..."""
    down = ("top" if row == 0 else "bottom" if row == rows - 1 else "row %d" % (row + 1)) \
        if rows > 1 else ""
    across = "left" if col == 0 and cols > 1 else "right" if col == cols - 1 and cols > 1 else ""
    return " ".join(word for word in (down, across) if word) or "middle"


def _metatile_name(label: Mapping[str, str], uses: Sequence[Use]) -> str:
    """A metatile's name from its tiles, and from the part it plays in pieces:
    scenery by the sign it is part of and where in it; ground as a surface or
    a fill, and in which kind of piece where that is not the obvious one."""
    if not uses:
        return label["name"] + " unused"
    kind = collections.Counter(use[0] for use in uses).most_common(1)[0][0]
    first = next(use for use in uses if use[0] == kind)
    if label["kind"] == "scenery":
        return "%s %s part %s" % (kind, first[1], first[2])
    surface = sum(1 for use in uses if use[3]) * 2 >= len(uses)
    words = [label["name"], "surface" if surface else "fill"]
    if kind == "sign":
        words.append("under sign " + first[1])
    elif kind in ("loop", "sand", "rocks") and kind not in label["name"]:
        words.append("in " + kind)
    return " ".join(words)


def missing(labels: Mapping[str, Mapping[str, Any]],
            where: read.Where = read.CLASSIC) -> list[str]:
    """What in the vocabulary has no label, as `metatiles/m1a` and `pieces/p57`."""
    return (["metatiles/" + name for name in read.metatiles(where)
             if name not in labels.get("metatiles", {})]
            + ["pieces/" + name for name in read.pieces(where)
               if name not in labels.get("pieces", {})])


def filled(labels: Mapping[str, Mapping[str, Any]],
           draft: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """`labels` with the draft's entries added where it has none -- and none of
    its own touched, since a label a person wrote is the file's point."""
    out: dict[str, dict[str, Any]] = {}
    for section in ("metatiles", "pieces"):
        mine = labels.get(section, {})
        # In the vocabulary's order, so the file reads as the vocabulary does.
        out[section] = {name: mine.get(name, label) for name, label in draft[section].items()}
        out[section].update({name: label for name, label in mine.items()
                             if name not in out[section]})
    return out


def dump(labels: Mapping[str, Mapping[str, Any]]) -> str:
    """One entry to a line, in the vocabulary's order, so a rename is a one-line diff."""
    lines = ["{"]
    sections = list(labels.items())
    for index, (section, entries) in enumerate(sections):
        lines.append('  "%s": {' % section)
        items = list(entries.items())
        for at, (name, label) in enumerate(items):
            comma = "," if at < len(items) - 1 else ""
            lines.append("    %s: %s%s" % (json.dumps(name), json.dumps(label), comma))
        lines.append("  }" + ("," if index < len(sections) - 1 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="say what has no label, and write nothing")
    args = parser.parse_args(argv)
    path = os.path.join(read.HERE, read.LABELS)
    labels = read.labels()
    if args.check:
        gaps = missing(labels)
        for gap in gaps:
            print("no label: %s" % gap)
        print("%d without a label" % len(gaps))
        return 1 if gaps else 0
    text = dump(filled(labels, drafted()))
    with open(path, "w") as handle:
        handle.write(text)
    print("labels -> %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
