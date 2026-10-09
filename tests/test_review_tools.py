"""The review tool, run end to end, and the question it was written to answer.

`tools/menu_shot.py` and `tools/art_sheet.py` write a picture for a person to
look at, so what the picture *says* is not the suite's to judge. What is the
suite's is that each still starts: they are run rarely and import half the
renderer, so a split in there breaks them silently, and the break is found on
the day somebody needs the picture.

**The sheet was here once before**, drawing a catalogue of pieces that went
with the vocabulary it drew. The one there is now reads the vocabulary rather
than knowing it, so a tile added to `maps/tiles.json` is on it with no change
here.

Each runs in a subprocess because it opens a headless window of its own, and
`conftest.py` has already opened this process's one.

And the question `menu_shot.py` was written to answer -- whether a third tab
label still fits across the screen -- is a question about pixels, so it is asked
here as one, with every tab on: the case only an author with drafts sees,
which is exactly why nobody else would see it go wrong.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(*args: str) -> str:
    done = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_menu_shot_writes_a_picture_of_every_tab(tmp_path):
    """One PNG for every line it prints, and the courses tab is always one.

    Not a count of tabs: `maps/drafts/` is gitignored, so how many there are
    depends on the clone, and a number here would be green on one machine only.
    """
    out = _run(os.path.join("tools", "menu_shot.py"), str(tmp_path / "menu"))
    written = [line for line in out.splitlines() if line.endswith(".png")]
    assert written, out
    assert all(os.path.exists(path) for path in written), written
    assert str(tmp_path / "menu_courses.png") in written


def test_every_tab_label_fits_across_the_screen(pyxel_headless):
    """The tab row, drawn with each tab chosen in turn, never reaches either edge.

    `_choices` centres the row by `4 * len(word)` arithmetic, so a row that is
    too wide does not wrap or shrink -- it is cut off by the screen on both
    sides, and the first thing lost is the first and last letters. Ink in
    column 0 or in the last column is that, and nothing else puts ink there.

    The chosen tab is a box a few pixels wider than its word, which is why each
    tab is drawn chosen: the row is widest when the longest word is the one in
    the box.
    """
    from game.constants import SCREEN_W
    from game.menu import Menu
    from game.render import menu_draw
    from game.render.lettering import ROW_H
    from game.render.style import SKY

    menu = Menu([("a", lambda: None)], drafts=[("b", lambda: None)], records={}, path=None)
    assert len(menu.sections) == 2, "every tab on is the case this is about"
    top = menu_draw.MENU_TAB_Y - 1
    for _ in menu.sections:
        menu_draw.draw_menu(menu)
        inked = [x for x in range(SCREEN_W) for y in range(top, top + ROW_H)
                 if pyxel_headless.screen.pget(x, y) != SKY]
        assert inked, "the %s tab drew nothing" % menu.label
        assert min(inked) > 0 and max(inked) < SCREEN_W - 1, (
            "with %s chosen the tab row runs off the screen" % menu.label)
        menu.move_section(1)


def test_art_sheet_writes_one_picture_of_everything_the_game_loads(tmp_path):
    """One PNG, where it was asked for, and as wide as the sheet says.

    Its height is not asserted: it grows with the vocabulary, which is content.
    """
    from tools import art_sheet
    from tools.pixels import decode_rgb

    path = str(tmp_path / "sheet.png")
    out = _run(os.path.join("tools", "art_sheet.py"), path)
    # Only the lines that are paths: Pyxel says on stdout when a machine has no
    # audio device, which is every CI runner.
    assert [line for line in out.splitlines() if line.endswith(".png")] == [path], out
    with open(path, "rb") as handle:
        width, height, _ = decode_rgb(handle.read())
    assert width == art_sheet.WIDTH * art_sheet.SCALE
    assert height > 0


def test_the_sheet_leaves_nothing_the_game_loads_off_it():
    """Why this test: the sheet is for somebody deciding what to redraw, and a
    tile missing from it is a tile they never know is there. Every terrain name,
    every glyph, the logo and the bike are on it, and every metatile and piece
    the vocabulary declares -- each under its own name."""
    from game.render import assets
    from maps import read
    from tools import art_sheet

    named = {name for _, entries in art_sheet.sections() for _, _, name, _ in entries}
    wanted = (set(assets.TERRAIN_TILES) | set(assets.GLYPH_TILES) | set(assets.SCREEN_TILES)
              | set(assets.BIKE_TILES) | set(assets.CRASH_TILES)
              | set(read.metatiles()) | set(read.pieces()))
    assert wanted, "the game loads nothing and this would pass on nothing"
    assert wanted <= named, sorted(wanted - named)
