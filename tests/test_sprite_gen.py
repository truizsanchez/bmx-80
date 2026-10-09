"""The bike is generated too, and these are what hold it to the game.

The bike is the one picture in this game still computed rather than drawn: the
model in `tools/sprite_gen.py` is authored, and what is testable is everything
the rest of the game then assumes about it:

* that `SPRITE_RADIUS` is the model's own ground line rather than a guess, which
  is the number a bike buried 3px in the dirt gets wrong;
* that no pose is quietly clipped by the cell it has to fit in;
* that the mirrored bike really is a flipped blit of another pose, which is what
  licenses not shipping 32 more PNGs;
* and the two `--check` claims, byte for byte, so the committed art is a cache
  with a proof rather than a second source of truth.
"""

import math
import os

import pytest

from game.constants import CELL, SPRITE_RADIUS
from game.render import assets
from tools import pixels, sprite_gen

SKY = sprite_gen.SKY


def _hflip(art, size=CELL):
    return tuple(
        art[y * size + (size - 1 - x)] for y in range(size) for x in range(size)
    )


def _mirrored_model():
    """The model reflected about its own vertical axis: a bike facing left."""
    return [part.moved(lambda point: (-point[0], point[1])) for part in sprite_gen.model()]


# -- the number the rest of the game reads ------------------------------------


def test_the_sprite_radius_is_the_models_own_ground_line():
    """The one value in `constants.py` that is a fact about the drawing.

    Written as a literal there because `game/` may not import from `tools/`, so
    the two are kept in step by this rather than by a shared import. Get it
    wrong in either direction and the bike floats or sinks on every surface in
    the game, which is a bug this repo has had.
    """
    assert SPRITE_RADIUS == sprite_gen.GROUND


def test_the_wheels_are_tangent_to_that_ground_line():
    """Tangent by construction, so the claim is about the model, not the raster.

    A wheel is an annulus about the axle, so its lowest point is the axle plus
    the tyre's outer radius, and AXLE is defined as GROUND minus exactly that.
    """
    lowest = sprite_gen.AXLE + sprite_gen.WHEEL_R + sprite_gen.TYRE
    assert lowest == pytest.approx(sprite_gen.GROUND)


def test_the_last_inked_row_is_the_one_the_ground_runs_through():
    """And no row entirely below the ground line has anything in it.

    The renderer centres the sprite SPRITE_RADIUS off the surface, so the ground
    line falls *inside* a row rather than on a cell edge -- the wheels reach it
    and stop. Which is the difference between the bike standing on the dirt and
    standing in it, checked here on the raster and again on the screen by
    `test_sprite.test_the_bike_stands_on_the_ground_rather_than_in_it`.
    """
    art = sprite_gen.raster(sprite_gen.posed(0.0))
    rows = [y for y in range(CELL) if any(art[y * CELL + x] != SKY for x in range(CELL))]
    ground_row = int(math.floor(sprite_gen.GROUND + CELL / 2.0))
    assert max(rows) == ground_row
    assert ground_row < CELL - 1, "the ground line is on the cell's own edge"


# -- the cell the pose has to fit in ------------------------------------------


def test_no_pose_is_clipped_by_its_own_cell():
    """Rastered on twice the canvas, so what a 16x16 would have lost is visible.

    Checked over all 32 because clipping appears in one rotation and not its
    neighbours, which reads as a wobble in the animation rather than as missing
    pixels -- the kind of thing nobody finds by looking.
    """
    assert sprite_gen.overflow() == 0


@pytest.mark.parametrize("style", pixels.STYLES)
def test_every_pose_draws_something(style):
    for index in range(sprite_gen.FRAMES):
        art = sprite_gen.raster(sprite_gen.posed(index * 360.0 / sprite_gen.FRAMES), style)
        assert set(art) != {SKY}, index


def test_the_wheels_have_holes_in_them():
    """Which is the whole reason a tyre is an annulus and not a disc.

    At six pixels across a filled wheel is a black blob; the sky inside it is
    what makes it read as a wheel, and it is also material the union must not
    swallow -- so this fails the moment a frame tube is authored through an axle.
    """
    art = sprite_gen.raster(sprite_gen.posed(0.0))
    hub = int(round(sprite_gen.AXLE + CELL / 2.0)) * CELL
    holes = [x for x in range(CELL) if art[hub + x] == SKY]
    # Sky either side of the bike, plus a hole in each wheel and the gap the
    # engine leaves between them: five runs of sky across the axle line.
    runs = 1 + sum(1 for a, b in zip(holes, holes[1:]) if b - a > 1)
    assert runs == 5, "".join("." if art[hub + x] == SKY else "#" for x in range(CELL))


# -- the mirror, which is a blit flag rather than more art --------------------


@pytest.mark.parametrize("index", range(sprite_gen.FRAMES))
def test_a_mirrored_pose_is_a_flipped_pose(index):
    """`M R(t) = R(-t) M`, checked on the pixels rather than argued about.

    This is what a renderer spends instead of 32 more PNGs: to draw the bike
    facing the other way at angle `a`, blit the pose at `-a` with a negative
    width. If it ever stopped holding -- an asymmetric canvas, an origin off
    centre -- the bike would face the right way and stand in the wrong place.
    """
    phi = index * 360.0 / sprite_gen.FRAMES
    turn = sprite_gen.rotation(phi)
    mirrored = sprite_gen.raster([part.moved(turn) for part in _mirrored_model()])
    assert mirrored == _hflip(sprite_gen.raster(sprite_gen.posed(-phi)))


# -- the committed art --------------------------------------------------------


def test_the_committed_art_is_what_the_model_says(pyxel_headless):
    """Through the PNG and the palette, so it is what the game draws.

    A pose in `art/hand/` is excluded, on the same rule the terrain follows: this
    is a claim about what *the generator* put in the bank, and a drawing is not
    that. What still holds a drawn pose to the model is
    `tests/test_sprite.py::test_the_bike_stands_on_the_ground_rather_than_in_it`,
    which reads the loaded bank and so measures a drawing exactly as it measures
    a generated one -- the bike's own version of "the road is where the curve
    says".
    """
    wanted = sprite_gen.collect()
    assert sorted(wanted) == sorted(assets.BIKE_TILES + assets.CRASH_TILES)
    drawn = assets.hand_drawn()
    for name, art in wanted.items():
        if name in drawn:
            continue
        assert assets.read_tile(name) == art, name


def test_the_committed_pose_bytes_are_the_ones_the_tool_writes():
    """`tools/sprite_gen.py --check` as a test. Determinism is the claim.

    The tile half is
    `tests/test_tile_gen.py::test_the_committed_tile_bytes_are_the_ones_the_tool_writes`,
    and since the two generators share `stale_against` the claim is now one
    piece of code asked about two directories -- so the tests are named apart
    to say which directory went stale.
    """
    for name, art in sprite_gen.collect().items():
        path = os.path.join(assets.MOTO_DIR, name + ".png")
        assert os.path.exists(path), name
        with open(path, "rb") as handle:
            assert handle.read() == sprite_gen.encode_png(art), name
