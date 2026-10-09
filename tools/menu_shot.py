"""Screenshot the title screen without a window.

    python tools/menu_shot.py [out_prefix]

The one screen you actually see first, drawn with no window. This runs the real
`menu_draw.draw_menu` over the
real `Menu`, built out of the maps on disk, and writes a PNG per state worth
looking at: the courses tab, the same list scrolled, and a frame for every other
tab there is.
"""

import os
import sys

import pyxel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game.menu import Menu, WINDOW  # noqa: E402
from game.render import headless, menu_draw  # noqa: E402
from maps import DRAFTS, LISTED  # noqa: E402


def shot(menu: Menu, prefix: str, suffix: str) -> None:
    menu_draw.draw_menu(menu)
    path = os.path.abspath("%s_%s" % (prefix, suffix))
    pyxel.screenshot(path, scale=4)
    print("%s.png" % path)


def main() -> None:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "menu"

    headless.boot(chdir_to=__file__)

    menu = Menu(list(LISTED), drafts=list(DRAFTS), records={}, path=None)
    shot(menu, prefix, menu.label)

    # The window only moves when there are more courses than rows, so this state
    # is worth a frame of its own: it is the only one where `_scroll_marks` draws
    # anything at all.
    if len(menu.tracks) > WINDOW:
        menu.course = len(menu.tracks) - 1
        shot(menu, prefix, "scrolled")

    # ...and then one per remaining tab, named by the label it is drawn under, so
    # adding a fourth directory one day adds a frame without touching this file.
    for _ in range(len(menu.sections) - 1):
        menu.move_section(1)
        shot(menu, prefix, menu.label)


if __name__ == "__main__":
    main()
