"""Drive the editor's real window headless, and print what happened as one JSON line.

    python tests/editor_session.py <scratch dir>

Run in a subprocess by `tests/test_editor_ui.py`, because a process gets one Pyxel
window and `tests/conftest.py` already has it. Everything goes through the mouse
and the keys -- `pyxel.set_mouse_pos` and `pyxel.set_btn` -- and through the
editor's own `update` and `draw`, so it is the only thing that exercises the
vendored widgets' mouse capture and the palette's hit boxes.

**The vocabulary is written here**, into the scratch directory, out of whatever
tile names the repo draws -- walked, not named -- so that nothing in this file
depends on what a map or a piece of the project is called.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel  # noqa: E402

from game import paths  # noqa: E402

SCRATCH = sys.argv[1]
paths.make_chdir_target(__file__)
pyxel.init(640, 480, headless=True, fps=1000, quit_key=pyxel.KEY_NONE)
os.chdir(ROOT)

from maps import read  # noqa: E402
from tools.editor import palette, ui, view  # noqa: E402

palette.install()

first, second = read.tile_names()[:2]
vocabulary = {
    "tiles.json": {first: {"dir": 0}, second: {"dir": 0}},
    "metatiles.json": {"full": [first] * 4, "top": ["sky", "sky", second, second]},
    "pieces.json": {"two": [["full", "full"]], "tall": [["top"], ["full"]]},
}
for name, content in vocabulary.items():
    with open(os.path.join(SCRATCH, name), "w") as handle:
        json.dump(content, handle)
# The probes and the throw are the vocabulary's, as they are for any course.
with open(os.path.join(read.HERE, read.TABLES)) as source, \
        open(os.path.join(SCRATCH, read.TABLES), "w") as handle:
    handle.write(source.read())

editor = ui.Editor("session", log=os.path.join(SCRATCH, "editor.log"), where=SCRATCH)
editor.file.path = os.path.join(SCRATCH, "session.json")

LEFT, RIGHT = pyxel.MOUSE_BUTTON_LEFT, pyxel.MOUSE_BUTTON_RIGHT


def frame(count=1):
    for _ in range(count):
        editor.update_all()
        editor.draw_all()
        pyxel.flip()


def cell(row, col):
    x, y = editor.view.screen_of(row, col)
    return x + 3, y + 3


def click(button, xy, *held):
    for key in held:
        pyxel.set_btn(key, True)
    pyxel.set_mouse_pos(*xy)
    pyxel.set_btn(button, True)
    frame(2)
    pyxel.set_btn(button, False)
    frame(2)
    for key in held:
        pyxel.set_btn(key, False)
    frame()


def drag(button, start, *points):
    pyxel.set_mouse_pos(*start)
    pyxel.set_btn(button, True)
    frame(2)
    for point in points:
        pyxel.set_mouse_pos(*point)
        frame()
    pyxel.set_btn(button, False)
    frame(2)


def keys(*pressed):
    for key in pressed:
        pyxel.set_btn(key, True)
    frame()
    for key in pressed:
        pyxel.set_btn(key, False)
    frame()


def pick(tab, name):
    """Turn the palette to `tab` and click the entry called `name`, by mouse."""
    strip = view.tab_rect(view.TAB_NAMES.index(tab))
    click(LEFT, (strip.x + 3, strip.y + 3))
    rect = editor.palette_panel.slot_rect(tab, name)
    if rect is None:
        raise KeyError(name)
    click(LEFT, (rect.x + 2, rect.y + 2))


def stampings():
    return json.loads(json.dumps(editor.doc.stampings))


found = {}
frame()
# Every bar where the layout says it is: the toolkit places a child relative to
# its parent, and a bar given the window's coordinates lands somewhere else.
found["bars"] = [[bar.x, bar.y, bar.width, bar.height] for bar in (
    editor.map_panel.h_bar, editor.map_panel.v_bar, editor.palette_panel.bar)]
# The tabs answer a click on their label, each of them.
tabs = []
for index, tab in enumerate(view.TAB_NAMES):
    strip = view.tab_rect(index)
    click(LEFT, (strip.x + strip.w // 2, strip.y + 4))
    tabs.append(editor.tab)
found["tabs"] = tabs

# The scrollbars are where the view is: an arrow steps it, the thumb drags it,
# the wheel moves it across -- and each of those is the view moving.
bar = editor.map_panel.h_bar
click(LEFT, (bar.x + bar.width - 3, bar.y + 3))
found["arrow"] = editor.view.col
thumb = bar.x + 7 + round((bar.width - 14) * bar.value_var / bar.scroll_amount) + 2
drag(LEFT, (thumb, bar.y + 3), (thumb + 40, bar.y + 3), (thumb + 80, bar.y + 3))
found["thumb"] = editor.view.col
pyxel.set_mouse_pos(*cell(5, 2))
pyxel.mouse_wheel = 0
editor.map_panel.h_bar.value_var = 0
frame()
found["home"] = editor.view.col
pick("pieces", "two")
found["hand"] = list(editor.hand)
drag(LEFT, cell(10, 2), cell(10, 4), cell(10, 6), cell(10, 8))
found["run"] = stampings()
keys(pyxel.KEY_CTRL, pyxel.KEY_Z)
found["run_undone"] = stampings()

pick("metatiles", "top")
click(LEFT, cell(10, 2))
click(LEFT, cell(10, 2))
found["stacked"] = editor.doc.stack(10, 2)
click(RIGHT, cell(10, 2))
found["after_right"] = stampings()

pick("pieces", "tall")
click(LEFT, cell(10, 2), pyxel.KEY_ALT)
found["eyedropped"] = list(editor.hand)

keys(pyxel.KEY_Z)
found["zoom"] = editor.view.zoom
keys(pyxel.KEY_Z)

# The order under the pointer: TAB chooses from the top down, `[` lowers.
pick("metatiles", "full")
click(LEFT, cell(10, 2))
keys(pyxel.KEY_TAB)
keys(pyxel.KEY_TAB)
found["chosen"] = editor.chosen
pyxel.set_mouse_pos(*cell(10, 2))
keys(pyxel.KEY_RIGHTBRACKET)
found["raised"] = [name for _, _, name in stampings()]

pick("things", "n")
click(LEFT, cell(9, 20))
found["items"] = json.loads(json.dumps(editor.doc.items))
pick("things", "respawn")
drag(LEFT, cell(10, 12), cell(10, 16), cell(10, 22))
found["teleports"] = json.loads(json.dumps(editor.doc.teleports))
click(RIGHT, cell(10, 17))
found["teleports_after_right"] = json.loads(json.dumps(editor.doc.teleports))

plus = editor.clocks[0].inc_button
click(LEFT, (plus.x + 2, plus.y + 2))
found["clock_a"] = editor.doc.data["limits"][0]

for key in (pyxel.KEY_C, pyxel.KEY_G, pyxel.KEY_O):
    keys(key)
found["views"] = [editor.collision, editor.game_frame, editor.overview]
keys(pyxel.KEY_O)

ui.RIDE_FILE = os.path.join(SCRATCH, "ride.json")
launched = []
ui.subprocess.Popen = lambda command, **kw: launched.append(command)
keys(pyxel.KEY_R)
found["ride"] = launched[-1][-2:] if launched else None
with open(ui.RIDE_FILE) as handle:
    found["ride_file"] = json.load(handle)

keys(pyxel.KEY_CTRL, pyxel.KEY_S)
with open(editor.file.path) as handle:
    found["saved"] = json.load(handle)
found["dirty"] = editor.file.dirty(editor.doc.text())
print(json.dumps(found))
