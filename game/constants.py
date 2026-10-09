"""The screen, the grids and the window's rates. No magic numbers anywhere else.

Deliberately free of Pyxel imports: the model reads this module, and it must stay
testable without a window.

The engine's own numbers are not here. They are the original game's rules rather
than tunables, and they live beside the engine that applies them.
"""

# Screen.
SCREEN_W = 160
SCREEN_H = 144
DISPLAY_SCALE = 4

# The window's rate, which is not an engine's. An engine steps at a rate of its
# own -- the original game's is about 41 steps for every 60 frames -- and
# `game/cadence.py` says which displayed frames step.
DISPLAY_FPS = 60

# What a **headless** window is paced at, and it is not a frame rate: `pyxel.flip`
# sleeps until the next frame is due, so a driven session would spend most of its
# time waiting for a window nobody is looking at. Every number the game computes
# is in frames, so pacing and logic are separate and only the pacing moves here.
#
# Not "as fast as possible": a number, so the sleep is a rounding error rather
# than a special case in Pyxel nobody has read.
UNTHROTTLED = 1000

# The glyphs' grid: the logo, the crates' icons and the bike are drawn on 16x16.
CELL = 16

# The terrain's own grid, which is half of CELL: the kit (`game/kit.py`) is drawn
# in tiles of eight, so a 45-degree girder can step one tile at a time and a
# stroke can start on any of them. It is the original's tile, and the grid the
# engine reads the terrain on.
TILE = 8

# The bike's art: the distance from the centre of a moto tile to the wheels.
#
# It is `tools/sprite_gen.GROUND`, our own model's ground line, the value the
# tyres are tangent to by construction -- `tests/test_sprite_gen.py` fails if the
# two drift apart. It is under half a cell because a bike that must not clip its
# own cell in any of 32 rotations cannot reach 8 from the centre.
SPRITE_RADIUS = 6.6

# How wide one bomb of the nitro stock is: the glyph lives in the left
# `NITRO_PITCH` columns of its cell, so a row of them packs at this pitch.
NITRO_PITCH = 8
