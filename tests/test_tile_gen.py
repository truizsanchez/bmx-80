"""The glyphs, the logo and the committed bytes: what `tools/tile_gen.py` draws on
the `CELL` grid, and what says the files on disk are its output.

Everything here is hand-authored as text -- that is now the only kind of picture
this file makes, the terrain having stopped being a function of anything -- and
what is checked is that each one is what its job needs and that the PNGs in
`art/tiles/` are byte for byte what this code writes.
"""

import os

import pytest

from game.constants import CELL, NITRO_PITCH
from game.render import assets
from tools import pixels, tile_gen

SKY = pixels.SKY
RIM = pixels.RIM



def test_the_committed_art_is_what_this_file_draws(pyxel_headless):
    """Regenerate in memory and compare to what was loaded.

    This is what makes committing the PNGs safe: they are a cache with a proof,
    not a second source of truth. Catches a stale commit, a hand-edit and a wrong
    hex value in one assertion, because it goes the whole way through the file
    and the palette rather than comparing rasters to rasters.

    A tile in `art/hand/` is exempt, and that is the whole point of the
    directory: it is where a drawing goes so that making one does not have to
    mean giving this test up for all of them.

    **Excluded from the loop, never `pytest.skip`ped.** The suite's claim is that
    it has no skips, and that has to go on being true the first time somebody
    draws a tile.
    """
    wanted = tile_gen.authored()
    assert sorted(wanted) == sorted(list(assets.GLYPH_TILES) + list(assets.SCREEN_TILES))
    drawn = assets.hand_drawn()
    for name, art in wanted.items():
        if name in drawn:
            continue
        assert assets.read_tile(name) == art, name


def test_the_committed_tile_bytes_are_the_ones_the_tool_writes():
    """Byte for byte, so a regeneration is never a no-op diff.

    Determinism is the claim underneath: fixed zlib level, no timestamps, no
    text chunks. This is `tools/tile_gen.py --check` as a test.
    """
    for name, art in tile_gen.authored().items():
        path = os.path.join(assets.ART_DIR, name + ".png")
        assert os.path.exists(path), name
        with open(path, "rb") as handle:
            assert handle.read() == pixels.encode_png(art), name


CRATES = ("item_nitro", "item_time", "item_jet")


def test_a_pickup_and_its_counter_are_two_pictures():
    """The box on the course and the icon in the bar do different jobs.

    The icon sits in a row of eight and means "you have one"; the box sits on
    dirt at racing speed and means "there is one here". So the box is the bigger
    drawing -- it fills 14 of its 16 columns against the icon's 12 -- and the
    obvious economy of blitting one glyph twice is the sand's own mistake in
    another costume: a thing whose job is to be spotted has to be drawn for that.

    Both are hand-authored and both are in `GLYPHS`, which is the honest place:
    no curve describes either, and this is the boundary the generator has always
    stated rather than hidden.
    """
    box, icon = tile_gen.GLYPHS["item_nitro"], tile_gen.GLYPHS["nitro"]
    assert box != icon
    assert len(box) == CELL and all(len(row) == CELL for row in box)
    # Every character has to be one the four shades know, or `from_text` raises;
    # calling it is the check.
    raster = pixels.from_text(box)
    assert set(raster) <= {0, 1, 2, 3}
    assert sum(1 for value in raster if value != 3) > sum(
        1 for value in pixels.from_text(icon) if value != 3
    ), "the box on the course does not read louder than the icon in the bar"


def test_the_crates_are_one_box_and_a_letter_each():
    """Same crate, different letter, which is the whole of what tells them apart.

    Three of them. The frame has to be identical (or
    they read as three different objects) and the middle has to differ (or the
    player cannot tell a time boost from a nitro). Both halves are asserted,
    because getting either wrong is a picture that still looks fine on its own.
    """
    rasters = {name: pixels.from_text(tile_gen.GLYPHS[name]) for name in CRATES}
    for raster in rasters.values():
        assert set(raster) <= {0, 1, 2, 3}

    # The crate is everything outside the 8x6 window the letter is drawn in.
    def frame(raster):
        return tuple(
            value
            for index, value in enumerate(raster)
            if not (4 <= index % CELL < 12 and 5 <= index // CELL < 11)
        )

    frames = {name: frame(raster) for name, raster in rasters.items()}
    assert len(set(frames.values())) == 1, "the crates are not one crate"
    assert len(set(rasters.values())) == len(CRATES), "two pickups draw the same"


def test_the_counter_is_drawn_at_the_width_of_its_own_row():
    """The bomb lives in the left `NITRO_PITCH` columns of its cell.

    `draw_stock` blits half a tile, because the row of eight sits in the right
    half of the HUD band at 8px to a bomb -- so a glyph that put ink past column
    8 would draw the next bomb's cell as well as its own, and the row would be a
    smear rather than a count. The empty half is the deliberate part.
    """
    raster = pixels.from_text(tile_gen.GLYPHS["nitro"])
    drawn = [raster[y * CELL + x] for y in range(CELL) for x in range(NITRO_PITCH)]
    spilt = [raster[y * CELL + x] for y in range(CELL) for x in range(NITRO_PITCH, CELL)]
    assert any(value != pixels.SKY for value in drawn), "the counter is not drawn"
    assert all(value == pixels.SKY for value in spilt), "the counter is wider than its row"


def test_every_picture_has_an_account_of_where_it_comes_from():
    """A tile the generator draws and `provenance` cannot account for is a tile
    with no answer to the only question a contributor has about it."""
    art = tile_gen.authored()
    where = tile_gen.provenance()
    assert set(where) == set(art)
    for name, uses in where.items():
        assert uses, name


def test_no_picture_in_the_bank_is_drawn_twice():
    """One picture is one name: two files and two bank slots of the same pixels
    are a picture drawn twice by accident."""
    art = tile_gen.authored()
    seen = {}
    for name, raster in art.items():
        seen.setdefault(raster, set()).add(name)
    duplicates = {frozenset(names) for names in seen.values() if len(names) > 1}
    assert duplicates == set()


# -- the banner ---------------------------------------------------------------


def test_the_banner_slices_into_the_names_the_bank_expects():
    """The logo is one 128x32 picture and sixteen tiles, and the two have to be
    the same thing: a name in the bank that the slicer does not produce is a tile
    the game loads from a file nothing writes."""
    cells = tile_gen.slice_banner(tile_gen.BANNERS["logo"])
    assert sorted(cells) == sorted(assets.SCREEN_TILES)
    for name, art in cells.items():
        assert len(art) == CELL * CELL, name
        assert set(art) <= {pixels.EDGE, pixels.BULK, pixels.RIM, SKY}, name


def test_the_cells_reassemble_into_the_banner():
    """The round trip, which is what catches an off-by-one in the slicer.

    A slicer that reads a column or a row across is not an error anywhere -- it
    produces sixteen legal tiles, and the picture is merely wrong. Only putting
    them back together says so.
    """
    rows = tile_gen.BANNERS["logo"]
    cells = tile_gen.slice_banner(rows)
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            art = cells["logo_%d%d" % (x // CELL, y // CELL)]
            assert art[(y % CELL) * CELL + (x % CELL)] == tile_gen._INDICES[char], (x, y)


def test_a_banner_that_is_not_its_declared_size_is_refused():
    """`from_text`'s rule at banner scale, and it matters more here: a tile one
    character short is obviously broken, where a banner one character short
    silently shifts every cell after it."""
    rows = list(tile_gen.BANNERS["logo"])
    with pytest.raises(ValueError):
        tile_gen.slice_banner(tuple(rows[:-1]))
    rows[3] = rows[3][:-1]
    with pytest.raises(ValueError):
        tile_gen.slice_banner(tuple(rows))


def test_the_authored_pictures_are_the_glyphs_and_the_banner():
    """Everything on the `CELL` grid, and every one of them accounted for."""
    authored = tile_gen.authored()
    assert set(authored) == set(tile_gen.GLYPHS) | set(assets.SCREEN_TILES)
    where = tile_gen.provenance()
    for name in authored:
        assert where[name], name
