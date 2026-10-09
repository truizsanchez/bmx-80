"""The files a course is written in, read off a disk this test lays out itself.

`maps/read.py` is deliberately thin -- it reads JSON and hands it to
`game/course.py` -- so what is worth pinning is the small number of decisions it
does make: which file is which, that a course is a *factory* and not a course,
that a listing is a directory listing, and that a bad file is refused by the
thing that builds a course rather than by a second opinion here.

Written into `tmp_path` rather than read out of `maps/`, for the reason the rule
in `AGENTS.md` gives: a map is content, and a test that named one would be a
test that moves when somebody redraws a course.
"""

import json
import os

import pytest

from maps import read

TILES = {"floor": {"solid": True, "dir": 0}, "ramp": {"solid": True, "dir": 4}}
METATILES = {"flat": ["sky", "sky", "floor", "floor"], "slope": ["-", "ramp", "ramp", "floor"]}
PIECES = {"ledge": [["flat", "flat"]], "hill": [["slope"]]}


def _where(tmp_path, tiles=None, metatiles=None, pieces=None):
    (tmp_path / read.TILES).write_text(json.dumps(TILES if tiles is None else tiles))
    (tmp_path / read.METATILES).write_text(
        json.dumps(METATILES if metatiles is None else metatiles))
    (tmp_path / read.PIECES).write_text(json.dumps(PIECES if pieces is None else pieces))
    with open(os.path.join(read.HERE, read.TABLES)) as tables:
        (tmp_path / read.TABLES).write_text(tables.read())
    return str(tmp_path)


def _course_file(tmp_path, name="one", **body):
    directory = tmp_path / "courses"
    directory.mkdir(exist_ok=True)
    path = directory / (name + ".json")
    path.write_text(json.dumps(body))
    return str(path)


def test_a_course_is_its_pieces_stamped_and_its_items_placed(tmp_path):
    where = _where(tmp_path)
    path = _course_file(tmp_path, pieces=[[4, 2, "ledge"]], items=[["n", 3, 2]],
                        limits=[90.0, 75.0, 60.0])
    course = read.course(path, where=where)
    flat = course.tiles_of.metatile_id["flat"]
    assert [course.metatile(4, c) for c in (2, 3)] == [flat, flat]
    assert course.items() == [(4, 3, 2)]
    assert course.limits == (90.0, 75.0, 60.0)


def test_a_course_with_nothing_in_it_still_builds(tmp_path):
    """Why this test: an author starts every course as an empty file, and a
    reader that needed every key would make the first save of a new course a
    crash rather than an empty ring."""
    where = _where(tmp_path)
    course = read.course(_course_file(tmp_path), where=where)
    assert course.metatile(0, 0) == 0xFF, "an empty ring, and every cell of it sky"
    assert course.items() == [] and course.limits == (0.0, 0.0, 0.0)
    assert course.teleports(), "a course with none declared still has somewhere to put a bike"


def test_a_listing_is_a_directory_and_a_course_is_a_factory(tmp_path):
    """Why a factory: only the map somebody chose is read, and it is read afresh
    each time -- so a race never starts on a map the last race took a crate out
    of. The same reason the cartridge's list is one (`main.cartridge_courses`).
    """
    where = _where(tmp_path)
    _course_file(tmp_path, "beta", pieces=[[4, 0, "ledge"]])
    _course_file(tmp_path, "alpha")
    (tmp_path / "courses" / "notes.txt").write_text("not a course")

    listed = read.listed(os.path.join(where, "courses"))
    assert [name for name, _ in listed] == ["alpha", "beta"], "sorted, and only the JSON"
    build = dict(listed)["beta"]
    assert build() is not build(), "a factory, so every race gets its own"


def test_a_directory_that_is_not_there_lists_nothing(tmp_path):
    """A clone has no `maps/drafts/`; a menu that raised over it would be a game
    nobody but the author could start."""
    assert read.listed(str(tmp_path / "nowhere")) == []


def test_a_piece_naming_a_metatile_nothing_declares_is_refused(tmp_path):
    """And refused **where a course is built**, not by a second opinion in the
    reader: one place for the format to live."""
    where = _where(tmp_path, pieces={"bad": [["nosuch"]]})
    path = _course_file(tmp_path, pieces=[[0, 0, "bad"]])
    with pytest.raises(KeyError):
        read.course(path, where=where)


def test_a_course_naming_a_piece_nothing_declares_is_refused(tmp_path):
    where = _where(tmp_path)
    path = _course_file(tmp_path, pieces=[[0, 0, "nosuch"]])
    with pytest.raises(KeyError):
        read.course(path, where=where)


def test_the_tiles_a_drawing_is_owed_are_the_ones_declared(tmp_path):
    """`game/render/assets.py` loads one PNG per name in this list, so the list
    and the directory are one claim: a name here with no drawing is a missing
    file at boot, which is what `assets.load_all` is for."""
    where = _where(tmp_path)
    assert list(read.tile_names(where)) == ["floor", "ramp"]
    assert read.tile_names(str(tmp_path / "nowhere")) == []


# -- the enhanced vocabulary --------------------------------------------------


def _enhanced(tmp_path, tiles=None, metatiles=None, pieces=None):
    """A base vocabulary and an enhanced layer over it, both written here."""
    base = _where(tmp_path)
    layer = tmp_path / "enhanced"
    layer.mkdir()
    (layer / read.TILES).write_text(json.dumps({"flag": {"solid": False}} if tiles is None else tiles))
    (layer / read.METATILES).write_text(json.dumps(
        {"banner": ["flag", "-", "-", "-"]} if metatiles is None else metatiles))
    (layer / read.PIECES).write_text(json.dumps({"flagged": [["banner"], ["flat"]]}
                                                if pieces is None else pieces))
    return (base, str(layer))


def test_an_enhanced_vocabulary_is_the_base_with_its_own_over_it(tmp_path):
    """Why this test: an enhanced course is written in the original's pieces and
    this game's own at once, and a piece of one has to merge into a piece of the
    other as if they had always been one vocabulary."""
    where = _enhanced(tmp_path)
    assert set(read.pieces(where)) == {"ledge", "hill", "flagged"}
    assert set(read.own(where, read.PIECES)) == {"flagged"}, "the layer's own, alone"
    assert read.own(where[:1], read.PIECES) == {}, "a classic vocabulary has nothing of its own"
    assert list(read.tile_names(where)) == ["floor", "ramp", "flag"]
    course = read.course(_course_file(tmp_path, pieces=[[14, 3, "ledge"], [13, 3, "flagged"]]),
                         where=where)
    tiles = course.tiles(course.metatile(14, 3))
    assert [course.tile_name(tile) for tile in tiles] == [None, None, "floor", "floor"]


@pytest.mark.parametrize("what", ["tiles", "metatiles", "pieces"])
def test_an_enhanced_layer_that_redefines_the_base_is_refused(tmp_path, what):
    """Why this test: a course written against the base has to mean the same in
    every vocabulary that holds it. A layer that quietly redrew `floor` would
    change every classic course ridden through it, and nothing would say so."""
    clash = {"tiles": {"tiles": {"floor": {"dir": 4}}},
             "metatiles": {"metatiles": {"flat": ["floor"] * 4, "banner": ["floor"] * 4}},
             "pieces": {"pieces": {"ledge": [["flat"]]}}}[what]
    where = _enhanced(tmp_path, **clash)
    with pytest.raises(ValueError):
        {"tiles": read.tileset, "metatiles": read.tileset, "pieces": read.pieces}[what](where)


def test_where_a_course_is_says_what_it_is_written_in(tmp_path):
    """Why this test: nothing in a course file says which vocabulary it is in --
    the directory is the statement -- so the one rule that reads the directory
    has to read it right, for the project's courses and an author's drafts."""
    assert read.vocabulary_of(str(tmp_path / "enhanced" / "courses" / "a.json")) == \
        read.ENHANCED_VOCABULARY
    assert read.vocabulary_of(str(tmp_path / "enhanced" / "drafts" / "a.json")) == \
        read.ENHANCED_VOCABULARY
    assert read.vocabulary_of(str(tmp_path / "courses" / "a.json")) == read.CLASSIC
    assert read.vocabulary_of(str(tmp_path / "drafts" / "enhanced.json")) == read.CLASSIC, \
        "a file's own name is not a directory"
