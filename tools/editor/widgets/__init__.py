"""Pyxel's editor widgets, vendored and pruned. MIT, (c) 2018 Takashi Kitao.

We cannot *use* Pyxel's Tilemap Editor -- it edits a grid of (u,v) tile
references and a bmx-80 map is an ordered list of positioned `Placement`s with
six flags and multi-cell pieces, so a tile grid loses the order, the piece
identity and every flag. What it is, though, is a small widget toolkit with the
one thing worth not reinventing: mouse capture, and with it the difference
between a click and a drag, the hold-and-repeat of a scrollbar arrow, and the
hover that feeds a help line.

`LICENSE-pyxel` sits beside this file. What was dropped: the image-backed
buttons and the radio button (they blit from `editor_220x160.png`, which is
Pyxel's art), the canvas and field-cursor machinery, and the image, sound and
music editors.
"""

from .button import Button  # noqa: F401
from .number_picker import NumberPicker  # noqa: F401
from .scroll_bar import ScrollBar  # noqa: F401
from .text_button import TextButton  # noqa: F401
from .text_toggle_button import TextToggleButton  # noqa: F401
from .toggle_button import ToggleButton  # noqa: F401
from .widget import Widget  # noqa: F401

__all__ = [
    "Button",
    "NumberPicker",
    "ScrollBar",
    "TextButton",
    "TextToggleButton",
    "ToggleButton",
    "Widget",
]
