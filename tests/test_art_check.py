"""What `tools/art_check.py` says to a contributor, and that it says it correctly.

The tool exists because a pytest traceback is not an answer to "is my drawing
acceptable". That makes it a piece of user interface, and the thing worth pinning
about a piece of user interface is that it names the right problem -- so these
measure the *sentences*, not just the exit code.

The predicates take bytes and a name rather than a path, which is what lets a
five-colour PNG or a 15x16 one be built here instead of committed as a fixture
nobody can see the point of. The last test is the other kind: it walks
`art/hand/` exactly as committed, so a contribution that would fail the tool
fails the suite too.
"""

import struct
import zlib

from game.constants import CELL
from game.render import assets, style
from tools import art_check, pixels, tile_gen


def _png(width, height, rgb, colour=2):
    """A PNG of `rgb` (three bytes a pixel), by hand. Mirrors `pixels.encode_png`."""
    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    samples = 4 if colour == 6 else 3
    stride = width * samples
    body = bytearray()
    for y in range(height):
        body.append(0)
        for x in range(width):
            at = (y * width + x) * 3
            body += bytes(rgb[at:at + 3])
            if colour == 6:
                body.append(255)
    assert len(body) == height * (stride + 1)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(body), 9))
        + chunk(b"IEND", b"")
    )


def _flat(colour, width=CELL, height=CELL, kind=2):
    return _png(width, height, bytes(colour) * (width * height), kind)


def _rgb(shade):
    return ((shade >> 16) & 0xFF, (shade >> 8) & 0xFF, shade & 0xFF)


# -- the name -----------------------------------------------------------------


def test_a_known_name_is_accepted():
    assert art_check.check_name("item_nitro", art_check.known_names()) == []


def test_a_typo_is_told_which_name_it_nearly_is():
    """The failure mode is a misremembered name, not an invented one.

    Which is why this offers a correction rather than the list: `item_nitr0` is
    a zero for an O, and a contributor staring at it will not see that in three
    hundred alphabetical names.
    """
    said = art_check.check_name("item_nitr0", art_check.known_names())
    assert len(said) == 1
    assert "item_nitro.png" in said[0]
    assert "the game does not see it at all" in said[0]


def test_a_name_with_no_near_match_is_pointed_at_the_list():
    said = art_check.check_name("zzzzzzzz", art_check.known_names())
    assert len(said) == 1
    assert "--list" in said[0]


def test_every_name_the_game_loads_is_a_name_a_drawing_may_have():
    """The two lists are one list, and this is what keeps them so.

    `known_names` is what the tool checks against, and `_GROUPS` followed by the
    kit's terrain is what `load_all` walks. A name in one and not the other is a
    tile the game draws that nobody may redraw, or a file the tool waves through
    and the game then refuses.
    """
    assert art_check.known_names() == [
        name for group, _ in assets._GROUPS for name in group
    ] + list(assets.TERRAIN_TILES)


# -- the picture --------------------------------------------------------------


def test_a_tile_in_the_four_colours_is_accepted():
    assert art_check.check_picture(_flat(_rgb(style.MONO.shades[0]))) == []


def test_rgba_is_accepted_because_that_is_what_the_editors_export():
    """Measured against Pyxel itself, not assumed: RGBA loads and maps correctly.

    Aseprite and Piskel export type 6 by default, and demanding a flatten step
    that nothing actually needs is a rule that only costs a contributor time.
    """
    assert art_check.check_picture(_flat(_rgb(style.MONO.shades[1]), kind=6)) == []


def test_a_fifth_colour_is_rejected_by_naming_what_it_becomes():
    """The palette trap, and the reason this is the loudest message in the tool.

    A fifth colour does not raise anywhere: `Image.load` maps every source pixel
    to the *nearest* entry, so #4C4C4C silently becomes #606060 and the picture
    in the game is not the picture that was drawn. So the sentence has to name
    the consequence rather than restate the rule -- a contributor who is told
    "only four colours" will go looking for the fifth, and one who is told "these
    37 pixels will be drawn as bulk" already knows where it is.
    """
    rgb = bytearray(_rgb(style.MONO.shades[0]) * (CELL * CELL))
    for i in range(10):
        rgb[i * 3:i * 3 + 3] = bytes((0x4C, 0x4C, 0x4C))
    said = art_check.check_picture(bytes(_png(CELL, CELL, bytes(rgb))))
    assert len(said) == 1
    assert "10 pixels are #4C4C4C" in said[0]
    assert "#606060" in said[0]
    assert "not the picture you drew" in said[0]


def test_the_substitute_named_is_the_one_pyxel_would_pick(pyxel_headless):
    """Not a plausible nearest -- the actual one, checked through the bank.

    The tool computes the substitute with its own metric, and a message that
    named the wrong shade would be worse than no message: it would send somebody
    to look at the wrong part of their own drawing.

    Touches nothing: the Pyxel session is shared across the whole suite, so a
    test that wrote into the bank to prove a point would quietly change what
    every later test is measuring -- and slot 0 is `fill`.
    """
    import pyxel

    odd = (0x90, 0x20, 0x20)
    said = art_check.check_picture(_png(CELL, CELL, bytes(odd) * (CELL * CELL)))
    assert len(said) == 1

    claimed = min(style.MONO.shades, key=lambda c: art_check._distance(odd, c))
    index = style.MONO.shades.index(claimed)
    assert ("#%06X" % claimed) in said[0]
    # And the palette really does hold that colour at that index, so the shade
    # the message names is the one on the screen rather than a plausible guess.
    assert pyxel.colors[index] == claimed


def test_the_wrong_size_is_rejected_before_the_colours_are_counted():
    """One problem at a time, and the first one is the one to fix.

    A 8x8 drawing is very likely off-palette as well, and reporting both is a
    tool telling somebody about a consequence of the thing it just told them.
    """
    said = art_check.check_picture(_flat((0x4C, 0x4C, 0x4C), width=8, height=8))
    assert len(said) == 1
    assert "16x16" in said[0] and "8x8" in said[0]


def test_something_that_is_not_a_png_at_all_says_so():
    said = art_check.check_picture(b"not a png")
    assert len(said) == 1
    assert "not a PNG" in said[0]


def test_a_derived_tile_passes_its_own_check():
    """Whatever the tool demands, the generator has to already satisfy it.

    Over every glyph, because a rule the committed art fails is a rule that is
    wrong rather than a repo that is broken -- and because this is the one way the
    tool's idea of "the four colours" and `encode_png`'s can be caught disagreeing.
    """
    for name, art in tile_gen.authored().items():
        assert art_check.check_picture(pixels.encode_png(art)) == [], name


# -- the manifest -------------------------------------------------------------


def test_every_tile_the_game_loads_has_a_line_in_the_manifest():
    """Derived, so it cannot drift -- and this is what says the derivation is total.

    A future `_SIDE_FACES` or `_FAR_FACES` entry that `provenance` did not walk
    would show up here as a tile with no answer to "what is this and where does
    it appear", which is the whole question the manifest exists to answer.
    """
    rows = art_check.manifest()
    assert [name for name, _, _, _, _ in rows] == art_check.known_names()
    for name, _hand, uses, _cells, _maps in rows:
        assert uses, name


def test_the_manifest_accounts_for_a_name_no_map_draws():
    """Why this test: the manifest's job is to answer "what is this picture and
    where does it turn up", and a picture no map draws is the case that reads as
    a hole rather than as an answer. **Every name is that case right now** --
    this game has no maps of its own while the format is rebuilt -- so what the
    manifest has to keep doing is say where a picture *comes from* even when the
    census can say nothing about where it is used.

    The claim the census used to make here, that redrawing a shared tile is not
    a local edit, comes back with the maps.
    """
    rows = {name: row for name, *row in art_check.manifest()}
    _hand, uses, cells, maps = rows["bike00"]
    assert uses, "a picture with no account of itself"
    assert (cells, maps) == (0, []), "nothing draws a map yet"


def test_the_census_says_nothing_rather_than_a_confident_zero(tmp_path):
    """Why this test, and it is the bug this file exists for: an early census
    walked one kind of tile and stopped, so it reported the rest as **"not drawn
    by any committed map"**. A confident zero is worse than silence -- a
    contributor reading "no map draws this" would reasonably conclude the tile
    was dead and redraw it last, or not at all.

    So: a name the courses never put down gets **no entry**, not a zero; and a
    name they do gets the cells of the ring it is in, counted per course. Over a
    course this test writes, so the numbers are exact rather than "more than
    none" -- a proof read from whatever the courses happen to contain is a proof
    that moves when somebody redraws one.
    """
    import json
    import os

    from maps import read

    (tmp_path / read.TILES).write_text(json.dumps(
        {"floor": {"dir": 0}, "unused": {"dir": 0}}))
    (tmp_path / read.METATILES).write_text(json.dumps(
        {"road": ["sky", "sky", "floor", "floor"]}))
    (tmp_path / read.PIECES).write_text(json.dumps({"bit": [["road", "road"]]}))
    with open(os.path.join(read.HERE, read.TABLES)) as tables:
        (tmp_path / read.TABLES).write_text(tables.read())
    courses = tmp_path / "courses"
    courses.mkdir()
    (courses / "one.json").write_text(json.dumps({"pieces": [[15, 0, "bit"]]}))

    counts = art_check.census(read.listed(str(courses)))
    assert counts["floor"] == (4, ["one"]), "two cells, two floor tiles each"
    assert "unused" not in counts, "a name no course draws gets no entry at all"
    assert "sky" not in counts, "and sky is not a picture anybody draws"


def test_a_bike_pose_is_not_reported_as_an_unused_tile():
    """A pose has no cell count, and the manifest must not imply it has zero.

    Kept separate from the census test because the fix is in two places: the
    census does not count poses at all, and the caller has to say something true
    instead of falling through to the terrain wording.
    """
    counts = art_check.census()
    for name in assets.BIKE_TILES:
        assert name not in counts, name

    rows = {name: row for name, *row in art_check.manifest()}
    _hand, uses, cells, maps = rows["bike07"]
    assert cells == 0 and maps == []
    assert uses == ["bike pose 7 of 32"]


# -- what is actually committed -----------------------------------------------


def test_the_committed_drawings_pass_the_tool(pyxel_headless):
    """So a bad contribution fails `pytest`, and not only the tool.

    It is the assertion that stops a drawing arriving with nobody having run
    the tool on it. Each at its own size: the kit's terrain at TILE, the rest at
    CELL.
    """
    look = style.active()
    names = art_check.known_names()
    for path, stem in art_check.drawings():
        assert art_check.check_name(stem, names) == [], path
        with open(path, "rb") as handle:
            assert art_check.check_picture(handle.read(), look,
                                           art_check.size_of(stem)) == [], path


def test_a_title_tile_is_not_reported_as_an_unused_piece():
    """A logo cell is in no map and that is not a gap in any map.

    The same shape of claim as the bike pose above: the census cannot count it,
    so the caller has to say something true rather than falling through to the
    terrain wording, which would read as *somebody forgot to place this*.
    """
    counts = art_check.census()
    for name in assets.SCREEN_TILES:
        assert name not in counts, name

    rows = {name: row for name, *row in art_check.manifest()}
    _hand, uses, cells, maps = rows["logo_31"]
    assert cells == 0 and maps == []
    assert uses == [
        "the title screen's logo, cell (3, 1) of 8x2 -- hand-authored"
    ]
