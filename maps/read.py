"""A course of this game's own, read off the disk.

Six files and a directory of drawings, and between them they are everything an
author decides:

- `art/terrain/<name>.png` -- a tile, eight by eight, four shades. A drawing.
- `tiles.json` -- `{"<name>": {"solid": true, "dir": 4}}`: what each tile
  **collides as**. `soft`, `no_wheelie` and `rock` default to false, `solid` to
  true, `dir` to 0, and `surface` to `"normal"` -- the others (`ice`, `spring`,
  `rush`) are for the enhanced layer only, the original having none. This is the original's collision byte with the byte taken
  off, and it is declared rather than read off the picture for the reason
  `game/course.py` gives.
- `metatiles.json` -- `{"<name>": ["TL", "TR", "BL", "BR"]}`: four tile names,
  in the order the engine indexes a metatile. `"-"` is a tile that lets whatever
  is underneath through when this metatile is stamped over another.
- `pieces.json` -- `{"<name>": [[".", "m1a"], ["m06", "m06"]]}`: a grid of
  metatile names, which is what an author actually puts down. `"."` stamps
  nothing.
- `tables.json` -- `{"probes": [[27, 26, 21], ...], "throw": [[256, -3], ...]}`:
  which cells of the engine's window the floor probes read, a row per direction,
  and the path a crash throws the rider along (`game/course.Tables`).
- `labels.json` -- `{"metatiles": {"m1a": {"name": "up 22 bottom", "kind":
  "slope up"}}, "pieces": {...}}`: a name a person can read and a kind to group
  by, for every metatile and piece -- the ids are the original's numbers and say
  nothing. For the editor only; the engine never reads it
  (`tools/label_vocab.py` drafts it).
- `courses/<name>.json` -- `{"pieces": [[row, col, "<name>"], ...], "items":
  [["n", row, col], ...], "limits": [...], "teleports": [[from, to, y], ...]}`.
  A stamping names a piece or, just as well, a metatile on its own
  (`game/course.vocabulary`). Written one entry to a line (`dump`).

**Nothing here validates anything of its own**, which is the rule the format
before this one had and the one worth keeping: a reader that second-guesses the
files is a second place for the format to live. What refuses a bad file is
`game/course.py` building one -- a tile name nothing declares, a metatile that
is not four tiles, a piece naming a metatile that does not exist.

The names are the author's and the integer ids the engine reads are assigned
here and never leave (`game/course.Tileset`).

**A vocabulary is layers.** The classic one is `maps/` alone -- the original's
-- and the enhanced one is `maps/` with `maps/enhanced/` over it, whose three
files add tiles, metatiles and pieces of this game's own and may redefine none
of the base's. Which a course is written in is said by where it is:
`maps/courses/` is classic and held to the original's 255 metatile ids,
`maps/enhanced/courses/` is enhanced and is not (`vocabulary_of`).
"""

import json
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from game.course import Course, Tables, Tileset

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE_DIR = os.path.join(HERE, "courses")
TILES, METATILES, PIECES, TABLES = "tiles.json", "metatiles.json", "pieces.json", "tables.json"
LABELS = "labels.json"

#: The enhanced vocabulary's own directory, and its courses.
ENHANCED = os.path.join(HERE, "enhanced")
ENHANCED_COURSE_DIR = os.path.join(ENHANCED, "courses")
#: A vocabulary is the directories it is read from, the base first.
Where = str | Sequence[str]
CLASSIC: tuple[str, ...] = (HERE,)
ENHANCED_VOCABULARY: tuple[str, ...] = (HERE, ENHANCED)


def _read(path: str) -> Any:
    with open(path) as handle:
        return json.load(handle)


def _layers(where: Where) -> tuple[str, ...]:
    return (where,) if isinstance(where, str) else tuple(where)


def _layered(where: Where, name: str) -> dict[str, Any]:
    """One of the three files, every layer's over the one below it -- **adding
    only**: a layer that names something the one below already has is refused,
    because a course written against the base has to mean the same thing in
    every vocabulary that holds the base."""
    merged: dict[str, Any] = {}
    for layer in _layers(where):
        path = os.path.join(layer, name)
        if not os.path.exists(path) and layer != _layers(where)[0]:
            continue
        for key, value in _read(path).items():
            if key in merged:
                raise ValueError("%s in %s redefines %r" % (name, layer, key))
            merged[key] = value
    return merged


def tileset(where: Where = HERE) -> Tileset:
    """The tiles and metatiles every course of the vocabulary is drawn out of.

    One set for all of them, as the cartridge has one: a course is a list of
    pieces and the pieces are a vocabulary, so two courses sharing a tile is the
    normal case and not a coincidence. **Capped at the original's 255
    metatile ids unless it is layered** -- the enhanced vocabulary is not.
    """
    return Tileset(_layered(where, TILES), _layered(where, METATILES),
                   capped=len(_layers(where)) == 1)


def metatiles(where: Where = HERE) -> dict[str, list[str]]:
    """The metatiles by name, as their four tile names -- which is what a
    picture of one needs and the ids in a `Tileset` are not."""
    return _layered(where, METATILES)


def tile_declarations(where: Where = HERE) -> dict[str, dict[str, Any]]:
    """What every tile collides as, by name, as the files declare it."""
    return _layered(where, TILES)


def labels(where: Where = HERE) -> dict[str, dict[str, dict[str, str]]]:
    """Every metatile's and piece's name and kind, each layer's over the one below
    it -- a layer without the file adds none. Adding only, as the vocabulary is."""
    out: dict[str, dict[str, dict[str, str]]] = {"metatiles": {}, "pieces": {}}
    for layer in _layers(where):
        path = os.path.join(layer, LABELS)
        if not os.path.exists(path):
            continue
        for section, entries in _read(path).items():
            for name, label in entries.items():
                if name in out.setdefault(section, {}):
                    raise ValueError("%s in %s relabels %r" % (LABELS, layer, name))
                out[section][name] = label
    return out


def pieces(where: Where = HERE) -> dict[str, list[list[str]]]:
    """The prefab pieces, by name."""
    return _layered(where, PIECES)


def tables(where: Where = HERE) -> Tables:
    """The probes and the throw every course of the vocabulary is ridden with:
    the base's, since they are about the bike and not about the ground."""
    data = _read(os.path.join(_layers(where)[0], TABLES))
    return Tables.of(data["probes"], data["throw"])


def own(where: Where, name: str) -> dict[str, Any]:
    """What the top layer alone adds to one of the three files: an enhanced
    vocabulary's own, which is what the editor shows in a tab of its own."""
    layers = _layers(where)
    path = os.path.join(layers[-1], name)
    return dict(_read(path)) if len(layers) > 1 and os.path.exists(path) else {}


def vocabulary_of(path: str) -> tuple[str, ...]:
    """The vocabulary a course file is written in, which is said by where it is:
    under an `enhanced` directory it is the enhanced one, and classic anywhere
    else."""
    parts = os.path.abspath(path).split(os.sep)
    return ENHANCED_VOCABULARY if "enhanced" in parts[:-1] else CLASSIC


#: The fields of a course file, in the order `dump` writes them.
FIELDS = ("pieces", "items", "limits", "teleports")


def course(path: str, tiles: Tileset | None = None,
           where: Where = HERE) -> Course:
    """One course, built. `tiles` is handed in where a caller has a set already,
    because building one reads every drawing's declaration and a menu of sixty
    courses should do that once."""
    return course_from(_read(path), tiles if tiles is not None else tileset(where),
                       pieces(where), tables(where))


def course_from(data: "dict[str, Any]", tiles: Tileset,
                vocabulary: "Mapping[str, Sequence[Sequence[str]]]",
                ridden: Tables) -> Course:
    """A course built from a file's contents already in hand -- which is what an
    editor has, between one edit and the next."""
    return Course(
        tiles,
        vocabulary,
        ridden,
        stampings=[(row, col, name) for row, col, name in data.get("pieces", ())],
        items=[(kind, row, col) for kind, row, col in data.get("items", ())],
        teleports=[tuple(one) for one in data.get("teleports", ())],
        limits=data.get("limits", ()),
    )


def dump(data: "dict[str, Any]") -> str:
    """A course file's text: **one entry to a line**, the fields in `FIELDS`'
    order and anything else after them as it came.

    One way to write a course, so that two courses are the same exactly when
    their files are -- which is what makes "would a save change anything" a
    comparison of text -- and a line per stamping, so that a diff of a course
    reads as the pieces that moved.
    """
    keys = [key for key in FIELDS if key in data] + [key for key in data if key not in FIELDS]
    fields = []
    for key in keys:
        value = data[key]
        if isinstance(value, list) and value and all(isinstance(v, list) for v in value):
            body = ",\n".join("  " + json.dumps(entry) for entry in value)
            fields.append(" %s: [\n%s\n ]" % (json.dumps(key), body))
        else:
            fields.append(" %s: %s" % (json.dumps(key), json.dumps(value)))
    return "{\n" + ",\n".join(fields) + "\n}\n"


def listed(where: str = COURSE_DIR,
           vocabulary: Where | None = None) -> list[tuple[str, Callable[[], Course]]]:
    """Every course in a directory, as the menu takes them: a name and a factory.

    A factory and not a course, for the reason the cartridge's list is one
    (`main.cartridge_courses`): only the one somebody chose is read, and it is
    read afresh each time so that a race never starts on a map the last race
    took a crate out of.

    `vocabulary` is where the tiles, metatiles and pieces live, and defaults to
    the directory above the courses -- a rig and a draft are written in the same
    vocabulary as a course, which is what makes one of them worth drawing.
    """
    if not os.path.isdir(where):
        return []
    above = vocabulary if vocabulary is not None else os.path.dirname(os.path.abspath(where))
    return [(name[:-5], _factory(os.path.join(where, name), above))
            for name in sorted(os.listdir(where)) if name.endswith(".json")]


def _factory(path: str, where: Where) -> Callable[[], Course]:
    return lambda: course(path, where=where)


def tile_names(where: Where = ENHANCED_VOCABULARY) -> Sequence[str]:
    """Every terrain tile a drawing has to exist for, in the order they are
    declared, the enhanced vocabulary's included. `game/render/assets.py` loads
    one PNG per name."""
    names: list[str] = []
    for layer in _layers(where):
        path = os.path.join(layer, TILES)
        if os.path.exists(path):
            names += [name for name in _read(path) if name not in names]
    return names
