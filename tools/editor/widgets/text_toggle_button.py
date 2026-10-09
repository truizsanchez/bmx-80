"""A `ToggleButton` that draws itself as a label. Ours, not Pyxel's.

Upstream's toggle is `ImageToggleButton`, which blits from the editor's own
`editor_220x160.png` -- an asset this repo does not have and is not in the
business of borrowing. The drawing is `TextButton`'s, which is why this
is short: the state comes from `ToggleButton` and the picture from a label.

Which is also the right shape for what the editor toggles. `reverse` cannot be
an icon at any price -- a wall ridden the other way is the same picture -- and
the whole palette is settled on exactly that question, so the modifiers were
always going to be words.
"""

import pyxel

from .settings import BUTTON_TEXT_COLOR
from .toggle_button import ToggleButton


class TextToggleButton(ToggleButton):
    def __init__(self, parent, x, y, *, text, is_checked=False, **kwargs):
        super().__init__(
            parent,
            x,
            y,
            len(text) * pyxel.FONT_WIDTH + 3,
            pyxel.FONT_HEIGHT + 1,
            is_checked=is_checked,
            **kwargs,
        )
        self._text = text
        self.add_event_listener("draw", self.__on_draw)

    def __on_draw(self):
        x, y, w, h = self.x, self.y, self.width, self.height
        col = self.button_color
        pyxel.line(x + 1, y, x + w - 2, y, col)
        pyxel.rect(x, y + 1, w, h - 2, col)
        pyxel.line(x + 1, y + h - 1, x + w - 2, y + h - 1, col)
        pyxel.text(x + 2, y + 1, self._text, BUTTON_TEXT_COLOR)
