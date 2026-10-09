"""Vendored from Pyxel 2.9.5: `pyxel/editor/widgets/settings.py`.

Pyxel is MIT-licensed, (c) 2018 Takashi Kitao; see LICENSE-pyxel beside this
file. Kept as close to the original as possible so it can be diffed against
upstream again.

The colour indices are upstream's and they work unchanged, because the editor
follows `pyxel/editor/app.py` in keeping the system palette in slots 0-15 and
putting the game's four shades in the user half above `pyxel.NUM_COLORS`.
"""
WIDGET_HOLD_TIME = 16
WIDGET_REPEAT_TIME = 2
WIDGET_CLICK_TIME = 5
WIDGET_CLICK_DIST = 3
WIDGET_PANEL_COLOR = 1
WIDGET_BACKGROUND_COLOR = 7
WIDGET_SHADOW_COLOR = 13

BUTTON_ENABLED_COLOR = 12
BUTTON_DISABLED_COLOR = 5
BUTTON_PRESSED_COLOR = 7
BUTTON_TEXT_COLOR = 1
BUTTON_PRESSING_TIME = 4

INPUT_TEXT_COLOR = 1
INPUT_FIELD_COLOR = 10


def clamp(value, low, high):
    """`pyxel/editor/settings.py`'s, moved here so the widgets stand alone."""
    return max(min(value, high), low)
