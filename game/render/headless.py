"""Opening a window nobody is looking at.

Several things do it -- `main.py --selftest`, `tools/menu_shot.py`,
`tools/art_check.py`, `tools/art_sheet.py` and the suite's own session fixture
-- and they share this rather than each writing the same three lines out.

The three lines are one act: a window, the palette that window's art expects,
and the bank that art lives in. `assets.load_all` treats a missing tile as
fatal, so a boot that returns has proved the art is there as well.
"""

import os

import pyxel

from game import paths
from game.constants import SCREEN_H, SCREEN_W, UNTHROTTLED
from game.render import assets, palette


def boot(width: int = SCREEN_W, height: int = SCREEN_H,
         chdir_to: str | None = None) -> None:
    """Headless Pyxel, the palette and the image bank, in that order.

    **`UNTHROTTLED`, not the window's rate.** `pyxel.flip` sleeps until the next
    frame is due, and a headless window has no frame anybody sees -- so pacing it
    is time spent asleep waiting for nothing. Nothing downstream reads a wall
    clock, so the pacing is the only thing that moves.

    `width` and `height` are the screen's unless a caller is drawing a sheet
    rather than a game, which `tools/art_sheet.py` is.

    **`chdir_to` is the caller's `__file__`, and it is not optional bookkeeping.**
    `pyxel.init` ends by moving the process into the directory of whichever file
    called it -- so sharing the boot would silently move every tool's output from
    its own directory into this one. Passing `__file__` keeps
    a caller landing exactly where calling `pyxel.init` itself would have put it.
    See `paths.make_chdir_target` for why the directory may have to be created.
    """
    target = os.path.dirname(os.path.abspath(chdir_to or __file__))
    paths.make_chdir_target(__file__)
    paths.make_chdir_target(chdir_to or __file__)
    pyxel.init(width, height, headless=True, fps=UNTHROTTLED)
    palette.apply()
    assets.load_all()
    os.chdir(target)
