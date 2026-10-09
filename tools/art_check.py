"""What a hand-drawn tile has to be, said in sentences rather than in a traceback.

    python tools/art_check.py                 # every drawing in art/hand/
    python tools/art_check.py art/hand/x.png  # just these
    python tools/art_check.py --list          # every tile name, and what uses it
    python tools/art_check.py -v              # + the rejected tiles as ASCII

`art/tiles/` and `art/moto/` are a cache with a proof -- `tools/tile_gen.py
--check` and `tools/sprite_gen.py --check` say they are byte for byte what the
geometry and the bike model currently produce -- and a drawing is by definition
not that, so neither of those tools has anything to say about one. This is what
a drawing answers to instead, and it is deliberately short: **a name something
loads, and the four colours.** Both are facts about the file. What the picture
looks like -- the texture, the shading, the weight of the line, and where the
contour of the road goes -- is the designer's, because the bike collides with
the curve and never with the art.

**A new tool rather than a flag on `tile_gen.py`, and the reason is what
`--check` means.** That flag makes exactly one claim, that `art/tiles/` is the
generator's own output, and a hand-drawn tile is precisely what it must not be
allowed to cover; blunting the sharpest assertion in the repo to make room for
drawings is the wrong trade. This tool also spans both groups of art, reads
`maps/` for the census and needs a Pyxel bank for the surface rule, none of which
`tile_gen` imports.

Everything it checks is checked again by `tests/`, on purpose. The difference is
that this says which pixels and why.
"""

import argparse
import difflib
import os
import sys
from collections.abc import Sequence
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.constants import CELL, TILE  # noqa: E402
from game.render import style as styles  # noqa: E402
from tools import pixels, sprite_gen, tile_gen  # noqa: E402

#: One row of `--list`: `(name, hand-drawn?, uses, cells, maps)`.
ManifestRow = tuple[str, bool, list[str], int, list[str]]


# -- what a drawing may be named ----------------------------------------------


def known_names() -> list[str]:
    """Every name a drawing may answer to, in the order the game loads them."""
    from game.render import assets

    return (
        list(assets.GLYPH_TILES)
        + list(assets.SCREEN_TILES)
        + list(assets.BIKE_TILES)
        + list(assets.CRASH_TILES)
        + list(assets.TERRAIN_TILES)
    )


def size_of(stem: str) -> int:
    """How big a drawing of this name is: TILE for a terrain tile, CELL for the rest."""
    from game.render import assets

    return TILE if stem in set(assets.TERRAIN_TILES) else CELL


def drawings(directory: str | None = None) -> list[tuple[str, str]]:
    """`[(path, stem)]` for every PNG in `art/hand/`, sorted."""
    from game.render import assets

    directory = assets.HAND_DIR if directory is None else directory
    if not os.path.isdir(directory):
        return []
    return [
        (os.path.join(directory, name), name[:-4])
        for name in sorted(os.listdir(directory))
        if name.endswith(".png")
    ]


# -- the checks that need no bank ---------------------------------------------
#
# Kept free of Pyxel and of the filesystem so they can be tested against bytes
# built in the test rather than against fixture files nobody can see the point
# of. Each returns a list of sentences; empty is a pass.


def check_name(stem: str, names: Sequence[str]) -> list[str]:
    """Is this a name something loads? The typo trap, and it is the loud one."""
    if stem in names:
        return []
    near = difflib.get_close_matches(stem, names, n=1)
    said = "Nothing loads this file; the game does not see it at all."
    if near:
        said += " Did you mean %s.png?" % near[0]
    else:
        said += " Run --list for every name there is."
    return [said]


def check_picture(data: bytes, look: styles.Style | None = None,
                  size: int = CELL) -> list[str]:
    """Decodable, `size` square, and in the four colours. `[]` is a pass.

    `size` is CELL for every tile but the kit's terrain, which is TILE --
    `size_of` says which a name is.
    """
    look = styles.active() if look is None else look
    try:
        width, height, rgb = pixels.decode_rgb(data)
    except ValueError as problem:
        return ["This is not a PNG this project can read: %s." % problem]

    if (width, height) != (size, size):
        return ["This tile is %dx%d. This one is %dx%d." % (size, size, width, height)]

    shades = look.shades
    wanted = {((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF) for c in shades}
    tally: dict[tuple[int, int, int], int] = {}
    for i in range(0, len(rgb), 3):
        pixel = (rgb[i], rgb[i + 1], rgb[i + 2])
        if pixel not in wanted:
            tally[pixel] = tally.get(pixel, 0) + 1
    if not tally:
        return []

    said: list[str] = []
    for pixel, count in sorted(tally.items(), key=lambda pair: -pair[1]):
        near = min(shades, key=lambda c: _distance(pixel, c))
        said.append(
            "%d pixel%s %s #%02X%02X%02X. Not one of the four, so Pyxel draws "
            "%s as #%06X (shade %d, %s). The picture in the game is not the "
            "picture you drew."
            % (
                count,
                "" if count == 1 else "s",
                "is" if count == 1 else "are",
                pixel[0],
                pixel[1],
                pixel[2],
                "it" if count == 1 else "them",
                near,
                shades.index(near),
                _role(shades.index(near)),
            )
        )
    return said


def _distance(pixel: tuple[int, int, int], colour: int) -> int:
    """The metric `pyxel.Image.load` picks the nearest entry with."""
    other = ((colour >> 16) & 0xFF, (colour >> 8) & 0xFF, colour & 0xFF)
    return sum((a - b) ** 2 for a, b in zip(pixel, other))


def _role(index: int) -> str:
    return {styles.SKY: "sky", styles.EDGE: "the line", styles.RIM: "the rim",
            styles.BULK: "bulk"}.get(index, "shade %d" % index)


# -- what the bank can say that is not a rule ---------------------------------
#
# There was a third check here and it is deliberately gone. It held the drawn
# surface to 0.75px of the curve -- the argument being that it is what
# keeps the road under the bike -- and the author's answer was that where the
# surface goes is the designer's job and not the suite's. The measurement backed
# him up twice over: the bike collides with the **curve** and never with the art,
# so a contour two pixels off is a cosmetic decision; and the rule bounded the
# *maximum* excursion, which cannot tell a notched edge (bias 0.25px, max 2px)
# from a tile shifted bodily down a pixel (bias 1px, max 1px). It rejected both.
#
# So nothing here measures a picture. What is left is the census, which is
# information rather than judgement: how many cells of which map a name is drawn
# in, because a mechanical name does not say that a tile is used four hundred
# times and a contributor has no other way to find out.


# -- the manifest -------------------------------------------------------------


def census(courses: Sequence[tuple[str, Any]] | None = None
           ) -> dict[str, tuple[int, list[str]]]:
    """`{tile: (cells, [course, ...])}` over the project's courses.

    The bug this exists for shipped once: an early census walked one kind of
    tile and stopped, and reported the rest as **"not drawn by any committed
    map"**. A confident zero is worse than silence -- a contributor reading "no
    map draws this" would reasonably conclude the tile was dead and redraw it
    last, or not at all. So this counts a tile per *cell of the ring* a course
    puts it in, minted metatiles included, and says nothing at all about a name
    it never met.

    `courses` is `[(name, factory)]` and stays a parameter for the reason it
    always was: a census proved against whatever the courses happen to contain
    today is a census whose proof moves when somebody redraws one.
    """
    from game.course import COLS, EMPTY, ROWS
    from maps import COMMITTED

    counted: dict[str, tuple[int, set[str]]] = {}
    for name, build in (COMMITTED if courses is None else courses):
        course: Any = build()
        named = {at: tile for tile, at in course.tiles_of.tile_id.items()}
        for row in range(ROWS):
            for col in range(COLS):
                metatile = course.metatile(row, col)
                if metatile == EMPTY:
                    continue
                for tile in course.tiles(metatile):
                    if tile not in named:          # the transparent one
                        continue
                    if named[tile] == "sky":
                        continue
                    cells, seen = counted.get(named[tile], (0, set()))
                    counted[named[tile]] = (cells + 1, seen | {name})
    return {tile: (cells, sorted(seen)) for tile, (cells, seen) in counted.items()}


def _declared() -> dict[str, Any]:
    """Every terrain tile and the `Hit` it declares, out of `maps/tiles.json`
    and the enhanced vocabulary's over it.

    The declaration is the only account a terrain tile has of itself: it is a
    drawing, so there is no curve to point at, and what it is *for* is what it
    collides as.
    """
    from game.course import Tileset
    from maps import read

    try:
        tiles = Tileset(read._layered(read.ENHANCED_VOCABULARY, read.TILES), {}, capped=False)
    except FileNotFoundError:
        return {}
    return {name: tiles.hits[at] for name, at in tiles.tile_id.items() if name != "sky"}


def manifest() -> list[ManifestRow]:
    """`[(name, hand, uses, cells, maps)]` in the order the game loads them."""
    from game.render import assets

    where = tile_gen.provenance()
    for index, name in enumerate(assets.BIKE_TILES):
        where[name] = ["bike pose %d of %d" % (index, sprite_gen.FRAMES)]
    for name in assets.CRASH_TILES:
        what = "the bike, on its back" if name == "wreck" else (
            "the rider, %s" % name[len("rider_"):].replace("_", " "))
        where[name] = ["the crash: %s" % what]
    for name, hit in _declared().items():
        where[name] = ["a course's terrain: %s, direction %d%s%s"
                       % ("solid" if hit.solid else "sky", hit.direction,
                          ", soft" if hit.soft else "",
                          ", no wheelie" if hit.no_wheelie else "")]
    counts = census()
    drawn = {stem for _, stem in drawings()}
    rows: list[ManifestRow] = []
    for name in known_names():
        cells, maps = counts.get(name, (0, []))
        rows.append((name, name in drawn, where.get(name, []), cells, maps))
    return rows


def print_manifest(rows: Sequence[ManifestRow]) -> None:
    width = max(len(name) for name, _, _, _, _ in rows)
    print("%d tiles. A name is one picture; several shapes may share it." % len(rows))
    print()
    from game.render import assets

    terrain = set(assets.TERRAIN_TILES)
    for name, hand, uses, cells, maps in rows:
        # A terrain tile is a drawing wherever the file sits: `art/terrain/` is
        # where they are drawn and `art/hand/` only overrides one. Saying
        # "derived" of it would be saying the thing that stopped being true.
        source = "HAND" if hand else ("drawn" if name in terrain else "derived")
        print(
            "%-*s  %-8s %-5s %s"
            % (width, name, source, "%d" % cells if cells else "-", "; ".join(uses))
        )
        if maps:
            print("%s  %-8s %s" % (" " * width, "", "in " + ", ".join(maps)))


# -- the run ------------------------------------------------------------------


def report(paths: Sequence[str] | None = None, verbose: bool = False) -> int:
    """Check the drawings and print. Returns the number rejected.

    Two rules and no more: a name something loads, and the four colours. Both are
    about the *file* rather than about the picture, and that is the whole of it --
    what a drawing looks like is the designer's, including where the contour
    goes, because the bike collides with the curve and never with the art.

    The census afterwards needs the whole set in a bank, so it only runs once
    every file has passed. It reports and never rejects.
    """
    names = known_names()
    found = _chosen(drawings(), paths)

    from game.render import assets

    if not found:
        print("Nothing is hand-drawn: %s holds no PNGs." % _short(assets.HAND_DIR))
        print("All %d tiles come from the generators, which is the default state." % len(names))
        return 0

    look = styles.active()
    print("%s   %d file%s, against the %s style's four colours"
          % (_short(assets.HAND_DIR), len(found), "" if len(found) == 1 else "s", look.name))
    print()

    said = {stem: _problems(path, stem, names, look) for path, stem in sorted(found)}

    notes: list[str] = []
    if not any(said.values()):
        notes = _measure(sorted(said))

    rejected = _verdicts(found, said, look, verbose)

    if notes:
        print()
        for line in notes:
            print("  %s" % line)

    print()
    print(
        "%d of %d rejected." % (rejected, len(found))
        if rejected
        else "All %d accepted." % len(found)
    )
    return rejected


def _chosen(found: "list[tuple[str, str]]",
            paths: "Sequence[str] | None") -> "list[tuple[str, str]]":
    """The drawings to check: all of them, or the files named -- a named file
    that is not a drawing is checked all the same, so its name is refused."""
    if not paths:
        return found
    wanted = {os.path.abspath(p) for p in paths}
    chosen = [(p, s) for p, s in found if os.path.abspath(p) in wanted]
    for path in sorted(wanted - {os.path.abspath(p) for p, _ in chosen}):
        chosen.append((path, os.path.basename(path)[:-4]))
    return sorted(chosen)


def _problems(path: str, stem: str, names: Sequence[str], look: styles.Style) -> list[str]:
    """What is wrong with one drawing: its name, then its picture."""
    problems = check_name(stem, names)
    if problems:
        return problems
    try:
        return check_picture(open(path, "rb").read(), look, size_of(stem))
    except OSError as gone:
        return ["Cannot be read: %s." % gone]


def _verdicts(found: "list[tuple[str, str]]", said: "dict[str, list[str]]", look: styles.Style,
              verbose: bool) -> int:
    """A line a drawing, and what is wrong under it. Returns how many were rejected."""
    width = max(len(os.path.basename(p)) for p, _ in found)
    rejected = 0
    for path, stem in sorted(found):
        problems = said[stem]
        rejected += 1 if problems else 0
        print("  %-*s  %s" % (width, os.path.basename(path), "REJECTED" if problems else "ok"))
        for line in problems:
            print("      %s" % line)
        if problems and verbose:
            _dump(path, look)
    return rejected


def _measure(good: Sequence[str]) -> list[str]:
    """What the bank can say about a set of drawings. Returns the notes.

    Only reached when every file passed the checks above, so the bank can be
    loaded with the drawings in it. Nothing here can reject anything: the two
    rules that can are about the *file* -- its name and its four colours -- and
    they ran before this did.
    """
    from game.render import assets, headless

    headless.boot(chdir_to=__file__)

    notes: list[str] = []
    counts = census()
    poses = sorted(n for n in good if n in set(assets.BIKE_TILES))
    for name in good:
        if name in set(assets.BIKE_TILES):
            continue
        cells, maps = counts.get(name, (0, []))
        if maps:
            notes.append(
                "%s is drawn %d time%s, in %s -- one drawing, every one of them."
                % (name, cells, "" if cells == 1 else "s", ", ".join(maps))
            )
        elif name == "nitro":
            notes.append(
                "nitro is the HUD's counter, not a course object: it is drawn every "
                "frame of every race and no map places it."
            )
        elif name in set(assets.SCREEN_TILES):
            notes.append(
                "%s is one of the %d cells of the title logo: the menu draws it "
                "every frame it is showing and no map places it. The other %d are "
                "still the ones in tools/tile_gen.BANNERS, which is where a whole "
                "logo is easier to redraw than in sixteen files."
                % (name, len(assets.SCREEN_TILES), len(assets.SCREEN_TILES) - 1)
            )
        elif name in tile_gen.GLYPHS:
            notes.append(
                "%s is a course object, and no committed map places one yet." % name
            )
        else:
            notes.append(
                "%s is drawn by the generator but no committed map draws it yet." % name
            )

    if poses:
        notes.append(
            "%d of the %d bike poses %s drawn by hand."
            % (len(poses), sprite_gen.FRAMES, "is" if len(poses) == 1 else "are")
        )
        if len(poses) < sprite_gen.FRAMES:
            notes.append(
                "The other %d come from the model, so the bike will change style as "
                "it rotates. The sheet is one picture at %d angles and wants doing "
                "all at once -- or, far more likely, by editing the eleven shapes in "
                "tools/sprite_gen.py:model() and letting all %d fall out."
                % (sprite_gen.FRAMES - len(poses), sprite_gen.FRAMES, sprite_gen.FRAMES)
            )
    return notes


def _dump(path: str, look: styles.Style) -> None:
    try:
        width, height, rgb = pixels.decode_rgb(open(path, "rb").read())
    except (OSError, ValueError):
        return
    if width != height or width not in (CELL, TILE):
        return
    chars = {styles.EDGE: "#", styles.BULK: "+", styles.RIM: "-", styles.SKY: "."}
    print()
    for y in range(height):
        row = ""
        for x in range(width):
            i = (y * width + x) * 3
            pixel = (rgb[i], rgb[i + 1], rgb[i + 2])
            near = min(look.shades, key=lambda c: _distance(pixel, c))
            exact = pixel == ((near >> 16) & 0xFF, (near >> 8) & 0xFF, near & 0xFF)
            row += chars[look.shades.index(near)] if exact else "?"
        print("      %s" % row)
    print("      (? is a colour that is not one of the four)")
    print()


def _short(path: str) -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.relpath(path, root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="PNGs to check (default: all of art/hand/)")
    parser.add_argument("--list", action="store_true", help="every tile name and what uses it")
    parser.add_argument("-v", "--verbose", action="store_true", help="dump rejected tiles")
    args = parser.parse_args()

    if args.list:
        print_manifest(manifest())
        return 0
    return 1 if report(args.paths, args.verbose) else 0


if __name__ == "__main__":
    sys.exit(main())
