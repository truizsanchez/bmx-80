"""The palette gate: the art survives the trip into Pyxel's image bank unchanged.

Every tile the game draws is ours -- generated from the piece geometry and the
bike model, committed under `art/`, and required. A second, optional collection
brings a whole family of skips with it; a clean clone is green because there is
nothing else to load.
"""

import os

import pytest

from game.constants import CELL, TILE
from game.render import assets, style


def test_every_piece_tile_is_loaded(pyxel_headless):
    """The art the game cannot draw without."""
    for name in list(assets.GLYPH_TILES) + list(assets.SCREEN_TILES):
        assert name in assets.names(), name


def test_the_groups_load_in_order(pyxel_headless):
    """Names appear in group order.

    Pinning the order rather than the slots, because slots were never the
    address: `uv(name)` is the only lookup there has ever been, which is exactly
    what let a whole collection be removed without a diff anywhere else.
    """
    expected = [
        name
        for group, directory in assets._GROUPS
        for name in group
        if os.path.exists(os.path.join(directory, name + ".png"))
    ]
    assert assets.names() == expected


def test_tiles_use_only_the_four_art_shades(pyxel_headless):
    """No pixel of *our* art may map outside indices 0-3.

    This is the check that catches the palette trap: with a stock palette the
    art's grays get mapped to whatever pink or green happens to be nearest, and
    the failure is invisible until you look at the screen.

    Our tiles are written in the active style's four colours, so they match at
    distance 0 whatever the style is -- which is what `art/STYLE` buys and what
    makes a restyle reversible.

    **This one covers a hand-drawn tile too, and it is the reason it has to.**
    `Image.load` maps every source pixel to the *nearest* palette entry, so a
    fifth colour does not fail -- it silently becomes one of the four and the
    picture in the game is not the picture that was drawn. That is the palette
    trap,
    and a file drawn by hand is exactly what walks into it.
    """
    art_indices = set(range(len(style.active().shades)))
    ours = set(assets.GLYPH_TILES) | set(assets.SCREEN_TILES) | set(assets.BIKE_TILES)
    for name in sorted(ours):
        assert set(assets.read_tile(name)) <= art_indices, name


def test_the_palette_is_the_one_the_art_was_generated_in(pyxel_headless):
    """One fact, recorded once, and the two halves of it cannot drift.

    The generated PNGs carry the style's four colours verbatim; `palette.apply`
    installs them so `Image.load` matches at distance 0. A palette from one style
    over art from another is the same trap with a new coat of paint -- the picture
    survives, every shade lands on the wrong index, and nothing says so until you
    look at the screen. `art/STYLE` is what keeps them together.
    """
    import pyxel

    shades = style.active().shades
    assert tuple(pyxel.colors[i] for i in range(len(shades))) == shades


def test_a_hand_drawn_tile_is_a_tile(pyxel_headless):
    """What a drawing still has to be, which is not much and is not nothing.

    Sixteen by sixteen, and in the four colours the active style installs.
    Everything else about it is deliberately unchecked here: whether it keeps the
    road where the geometry says is nobody's rule: the engine never reads a picture,
    which reads the loaded bank and so covers drawn and generated alike. Texture,
    shading, the weight of the line, whether there is a line at all: the
    contributor's.

    `art/hand/` is empty as committed, so today this asserts over nothing. It is
    a guard armed for the first contribution rather than a test of current state,
    and `tools/art_check.py` is what says the same thing before a commit exists.
    """
    art_indices = set(range(len(style.active().shades)))
    for name in sorted(assets.hand_drawn()):
        art = assets.read_tile(name)
        assert len(art) == CELL * CELL, name
        assert set(art) <= art_indices, "%s uses a colour outside the palette" % name


def test_every_terrain_tile_is_loaded_into_its_own_bank(pyxel_headless):
    """Why this test: the terrain is at TILE and everything else at CELL, so it
    needs a bank of its own -- every `blt` on BANK steps in CELL -- and a lookup
    of its own, because a name has to say which bank it is in. `names()` stays
    the CELL tiles alone, which the order test above pins.

    **There are no terrain tiles at the moment**, the format being rebuilt
    (`maps/__init__.py`), so what this can still say is that the bank is loaded
    from the list and lands every name on the grid -- which is the whole of what
    it will say again when the list is full.
    """
    for name in assets.TERRAIN_TILES:
        u, v = assets.terrain_uv(name)
        assert u % TILE == 0 and v % TILE == 0, name
    assert set(assets.terrain_names()) == set(assets.TERRAIN_TILES)


def test_a_hand_drawn_terrain_tile_is_a_tile(pyxel_headless):
    """The terrain half of the test above it: eight by eight, and the four colours.

    Excluded from nothing and asserted over whatever `art/hand/` holds. That is
    empty of terrain today and this says nothing; it is the rule a drawn tile
    has to pass the moment somebody draws one, which is the point of leaving it
    standing.
    """
    art_indices = set(range(len(style.active().shades)))
    for name in sorted(assets.hand_drawn_terrain()):
        art = assets.read_terrain(name)
        assert len(art) == TILE * TILE, name
        assert set(art) <= art_indices, "%s uses a colour outside the palette" % name


def test_a_drawing_nothing_would_load_is_refused(pyxel_headless, tmp_path, monkeypatch):
    """The one failure this mechanism can have with no other symptom.

    A file in `art/hand/` whose stem is not a tile name is loaded by nothing, so
    without this it is a typo that draws nothing and is reported by nobody -- in
    the one directory whose whole purpose is that what you put in it appears on
    the screen. The message names the nearest tile, because the failure mode is a
    misremembered name and not an invented one.

    Reloads the real art afterwards: the Pyxel session is shared across the whole
    suite, so a test that left the bank half-loaded would change what every later
    test is measuring.
    """
    monkeypatch.setattr(assets, "HAND_DIR", str(tmp_path))
    (tmp_path / "item_nitr0.png").write_bytes(b"")
    try:
        with pytest.raises(ValueError) as caught:
            assets.load_all()
        assert "item_nitr0.png" in str(caught.value)
        assert "item_nitro" in str(caught.value)
    finally:
        monkeypatch.undo()
        assets.load_all()


def test_every_crate_a_course_can_hold_is_drawn_and_rides_through(pyxel_headless):
    """Why this test: the four crates are metatiles the engine names for itself
    (`game/course.RESERVED`), so no author draws them and nothing else looks at
    them. They were four quarters of sky once, and a crate of ours was then a
    pickup nobody could see -- in the game, not only in the editor -- with every
    test green.

    So: each is four drawn tiles, none of them solid, because a crate is picked
    up by being reached and never ridden on. And **one box and a letter each**,
    the rule the glyphs in `tools/tile_gen.py` keep: the frame the same on all
    four or they read as four objects, the middle different or the player
    cannot tell them apart.
    """
    from game.course import RESERVED
    from maps import read

    tiles = read.tileset()
    crates = [name for name in RESERVED if name.startswith("crate_")]
    assert crates, "the engine names no crates and this would pass on nothing"
    boxes = {}
    for crate in crates:
        quad = tiles.quads[tiles.metatile_id[crate]]
        names = [tiles.names.get(tile) for tile in quad]
        assert None not in names, "%s has a quarter nothing draws" % crate
        assert not any(tiles.hits[tile].solid for tile in quad), "%s can be ridden on" % crate
        drawn = [assets.read_terrain(name) for name in names]
        boxes[crate] = tuple(drawn[(y // TILE) * 2 + x // TILE][(y % TILE) * TILE + x % TILE]
                             for y in range(2 * TILE) for x in range(2 * TILE))

    def frame(box):
        return tuple(value for at, value in enumerate(box)
                     if not (4 <= at % CELL < 12 and 4 <= at // CELL < 12))

    assert len({frame(box) for box in boxes.values()}) == 1, "the crates are not one crate"
    assert len(set(boxes.values())) == len(crates), "two crates draw the same"


def test_the_sign_over_the_finish_is_drawn_and_rides_through(pyxel_headless):
    """Why this test: the two metatiles of the sign are the engine's own names
    (`game/course.RESERVED`), written in when the last lap starts, so no author
    draws them and nothing else looks at them -- they were sky, like the crates
    before them, and the last lap began with nothing to say so.

    Every quarter of both that is a tile at all is a drawing -- the original's
    sign is the lower half of its two cells, and the upper half lets the sky
    through -- and none of it is solid: the sign is scenery over the finish and
    cannot be ridden into, as the original's is."""
    from game.course import GOAL, RESERVED
    from maps import read

    tiles = read.tileset()
    for name in (RESERVED[at] for at in GOAL):
        quad = [tile for tile in tiles.quads[tiles.metatile_id[name]] if tile in tiles.names]
        assert quad, "%s is not drawn at all" % name
        assert not any(tiles.hits[tile].solid for tile in quad), "%s can be ridden into" % name
        for tile in quad:
            assert set(assets.read_terrain(tiles.names[tile])) - {style.SKY}, (
                "%s is drawn in sky and nothing else" % tiles.names[tile])
