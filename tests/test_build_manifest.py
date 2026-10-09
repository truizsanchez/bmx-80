"""What the shared executable carries, and what it must not.

`tools/build_exe.py` freezes the game for somebody who has no Python, and its
manifest is two tuples: `DATA`, the directories that ride along, and `EXCLUDE`,
the ones held out. Both are claims about the *repo*, not about the build tool,
and the repo moves -- a new committed map directory that nobody adds to `DATA`
is a course that is on the menu here and missing in the zip, and it fails on the
player's machine and nowhere else.

`--selftest` catches that too, but only after a build somebody has to run.
This asks the same question in a second.

The `EXCLUDE` half is rule 2 of `AGENTS.md` said in the packaging: `tests/` has
no business in a download. It is a guard rather than a fix -- `main.py` does not
import it -- and it stays one.
"""

import os

from tools import build_exe


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_authors_drafts_never_ship():
    """Why this test: `maps/drafts/` is gitignored, does not exist on a clone,
    and in a build belongs beside the executable where the player can write.
    Naming it in `DATA` would make the build fail on any machine but the
    author's -- and would ship somebody's unfinished maps if it did not.

    **The committed map directories are not asserted here at the moment**: this
    game has no maps of its own while the format is rebuilt
    (`maps/__init__.py`). When they come back they go in `DATA`, and
    `test_every_named_entry_is_really_there` below is what notices if a name is
    put there and the directory is not.
    """
    assert os.path.join("maps", "drafts") not in build_exe.DATA


def test_the_art_ships_whole():
    """`art/` and not `art/tiles/`, so `STYLE`, `moto/` and `hand/` come too.

    `palette.apply` reads `art/STYLE` and refuses to guess, and a drawing in
    `art/hand/` wins by name -- a build carrying only the generated tiles would
    quietly hand the player a different-looking game.
    """
    assert "art" in build_exe.DATA


def test_nothing_ships_that_is_not_on_disk():
    """Why this test: PyInstaller only follows imports, so every piece of data
    beside the code has to be named in `DATA` by hand -- and a name left there
    after the file went is a build that dies on a path that does not exist.

    This is the guard that the deletion of `game/kit.json` and the map
    directories had to pass, and the one a new map format has to pass again.
    """
    for entry in build_exe.DATA:
        assert os.path.exists(os.path.join(REPO, entry)), entry


def test_every_named_entry_is_really_there():
    """A manifest entry that names nothing is a typo nobody would ever see.

    A directory or a single file: `build_exe.build` gives each the destination
    PyInstaller wants.
    """
    for source in build_exe.DATA:
        assert os.path.exists(os.path.join(REPO, source)), source


def test_the_tests_stay_out_of_the_players_download():
    assert "tests" in build_exe.EXCLUDE


def test_the_extras_in_the_zip_exist():
    for extra in build_exe.EXTRAS:
        assert os.path.isfile(os.path.join(REPO, extra)), extra


def test_every_file_a_course_is_read_from_ships():
    """Why this test: `maps/tables.json` was added to what a course is built from
    and not to `DATA`, and every test stayed green -- they run from the repo,
    where the file is. A build would have died building its first course.

    Walked from `maps/read.py`'s own names, so the next file a vocabulary grows
    is owed a line here without anybody remembering to write one."""
    from maps import read

    def relative(path):
        return os.path.relpath(path, REPO)

    owed = [relative(os.path.join(layer, name)) for layer in read.ENHANCED_VOCABULARY
            for name in (read.TILES, read.METATILES, read.PIECES)]
    owed += [relative(os.path.join(read.HERE, read.TABLES)),
             relative(read.COURSE_DIR), relative(read.ENHANCED_COURSE_DIR)]
    missing = [path for path in owed if path not in build_exe.DATA]
    assert not missing, "read by maps/read.py and not shipped: %s" % missing
    assert os.path.join("maps", "enhanced", "drafts") not in build_exe.DATA
