"""The cartridge's tiles in Pyxel's bank, lent to a screen and given back.

No cartridge ships with the repository, so the tile memory here is written by
the test: one sprite tile, solid, where the bike's first tile is.
"""

from game.rom.cartridge import OBJECT_PALETTES, SIZE, Cartridge
from game.rom.graphics import pixels


def test_a_sprite_is_drawn_out_of_the_course_after_a_screen_had_the_bank(pyxel_headless):
    """**The race after the card had no bike.** The card before a race is drawn
    after the race's art is installed, and borrows the bank for its lettering;
    `course()` put the course's tiles back but left the card's tile memory in
    hand, and the bike's sprites are read out of that memory -- where the
    lettering has nothing at tile 0, so the bike was drawn clear. Everything
    else on the screen was right, which is why it took a play-test to see."""
    pyxel = pyxel_headless
    from game.render import rom_art

    raw = bytearray(SIZE)
    raw[OBJECT_PALETTES[False]] = rom_art.IDENTITY
    course = bytearray(0x1800)
    course[0:16] = b"\xff" * 16  # sprite tile 0: colour 3, the darkest
    try:
        rom_art.install_cartridge(Cartridge(bytes(raw), check=False))
        rom_art.install_art(lambda tile: pixels(course, tile), course)
        rom_art.use("a screen", lambda cartridge: bytearray(0x1800))
        rom_art.course()
        pyxel.cls(3)
        rom_art.sprites([(0, 0, 0, 0)], 3)
        assert pyxel.pget(4, 4) == 0
    finally:
        rom_art.install_art(None)
        rom_art.install_cartridge(None)
