"""The vocabulary drawn in a cartridge's own art: found by name, painted into the bank.

No cartridge ships with the repository, so the tile memory is written by the
test.
"""

from game.rom.cartridge import SIZE, Cartridge


def test_a_tile_is_named_for_its_number_in_the_original():
    """Why this test: the name is the whole of how a cartridge's picture of a
    tile is found, so a name that reads as a number when it is not one would
    paint a drawing over with some other tile of the original's."""
    from game.course import ORIGINAL_TILE, original_tile

    assert original_tile(ORIGINAL_TILE % 0xC9) == 0xC9
    assert original_tile(ORIGINAL_TILE % 0x00) == 0
    for name in ("sky", "tzz", "t123", "c9", ""):
        assert original_tile(name) is None, name


def test_with_a_cartridge_the_terrain_is_painted_in_its_own_art(pyxel_headless, monkeypatch):
    """Why this test: `--rom` on the editor, and on the race it rides, draws the
    vocabulary in the cartridge's own pictures by painting over the terrain
    bank -- the drawings on the disk are untouched, so the bank is the only
    place it can be seen to have happened.

    The tile memory is written here: every byte set, which is colour 3, the
    darkest, in every pixel of every tile. The real art is loaded again after,
    because the Pyxel session is the whole suite's."""
    from game.course import original_tile
    from game.render import assets, rom_art

    names = [name for name in assets.terrain_names() if original_tile(name) is not None]
    assert names, "no tile of the vocabulary is named for the original's number"
    monkeypatch.setattr(rom_art.graphics, "video", lambda cartridge: bytearray(b"\xff" * 0x1800))
    try:
        assert rom_art.paint_terrain(Cartridge(bytes(SIZE), check=False)) == len(names)
        for name in names:
            assert set(assets.read_terrain(name)) == {0}, name
    finally:
        monkeypatch.undo()
        assets.load_all()
