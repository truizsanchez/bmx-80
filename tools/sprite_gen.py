"""Generate the bike art from a geometric model of the bike.

Sibling of `tools/tile_gen.py`, and deliberately its same shape: a model, two
questions per pixel, and a PNG encoder that has to be deterministic. What it
generates is the 32 poses of the bike, so `git clone && pyxel run main.py` draws
nothing the repo does not own.

## What is derived here, and what is authored

The terrain tiles are derived from the kit's geometry, so art and geometry
cannot disagree. There is no such geometry for a bike: nothing in `game/`
describes its shape. So the model below is **authored**, in the
same sense `tile_gen.DITHER` and `tile_gen.GLYPHS` are, and what is derived from
it is everything after: the 32 rotations, the shading, and -- the part that
actually matters -- *where the wheels are*. `SPRITE_RADIUS` is the model's own
ground offset rather than a guess at where the wheels are, and
`tests/test_sprite_gen.py` pins the two together. A sprite buried 3px in the
dirt is what a guessed number buys.

## One model, 32 poses, and no mirrored art

A rotation set contains no reflection, so a bike that faces left is not in it.
The tempting fix is to emit 32 more PNGs. It is not needed: mirroring commutes
with rotation as `M R(t) = R(-t) M`, so the mirrored bike at angle `phi` is the
*unmirrored* pose at `-phi` blitted with a negative width.

## Shapes, not curves, and the union is the silhouette

`tile_gen` intersects half-spaces because a piece of terrain is one solid region
bounded by its surface. A bike is an assembly, so this unions signed distance
functions instead -- `min` over the parts. That is what makes the joins
invisible: an internal boundary is not on the union's boundary, so the frame
tube that runs into a wheel gets no outline where it enters, without anything
having to say so. The tyres are annuli rather than discs for the same reason in
reverse: at this size a filled wheel is a black blob, and the hole is what makes
it read as a wheel.

Shading is then exactly `tile_gen`'s: EDGE within EDGE_T of the silhouette, RIM
within RIM_T, BULK inside. No dither -- it exists for cell-sized fills of dirt,
and on a 12px bike it would be noise.
"""

import argparse
import math
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import NamedTuple, Protocol

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from game.constants import CELL  # noqa: E402
from tools.pixels import (  # noqa: E402
    EPS,
    SKY,
    Point,
    Raster,
    StyleLike,
    _style,
    encode_png,
    generator_arguments,
    generator_main,
    write_art,
)

# 32 poses, 11.25 degrees apart: the original's 32 directions, one pose each.
FRAMES = 32
NAMES = ["bike%02d" % index for index in range(FRAMES)]


# -- shapes -------------------------------------------------------------------
#
# Each is a signed distance function -- negative inside -- plus the two things
# the generator needs of it: how to move it, and how far it reaches from the
# origin. The reach is not decoration. A pose that puts material outside the
# 16x16 cell loses it, silently, in one rotation and not in the others, so the
# bound is checked over all 32 (`overflow`, and a test).

#: How a shape is moved: a point in, a point out.
Turn = Callable[[Point], Point]


class Part(Protocol):
    """One shape of the model: a signed distance, and how to move and bound it."""

    def sdf(self, point: Point) -> float: ...
    def moved(self, turn: Turn) -> "Part": ...
    def reach(self) -> float: ...
    def bottom(self) -> float: ...


class Disc:
    def __init__(self, x: float, y: float, radius: float) -> None:
        self.centre = (x, y)
        self.radius = radius

    def sdf(self, point: Point) -> float:
        return math.dist(point, self.centre) - self.radius

    def moved(self, turn: Turn) -> "Disc":
        x, y = turn(self.centre)
        return Disc(x, y, self.radius)

    def reach(self) -> float:
        return math.hypot(*self.centre) + self.radius

    def bottom(self) -> float:
        return self.centre[1] + self.radius


class Ring:
    """An annulus. A tyre, and the hole in it is why a wheel reads as a wheel."""

    def __init__(self, x: float, y: float, radius: float, thickness: float) -> None:
        self.centre = (x, y)
        self.radius = radius
        self.thickness = thickness

    def sdf(self, point: Point) -> float:
        return abs(math.dist(point, self.centre) - self.radius) - self.thickness

    def moved(self, turn: Turn) -> "Ring":
        x, y = turn(self.centre)
        return Ring(x, y, self.radius, self.thickness)

    def reach(self) -> float:
        return math.hypot(*self.centre) + self.radius + self.thickness

    def bottom(self) -> float:
        return self.centre[1] + self.radius + self.thickness


class Capsule:
    """A thick segment: every tube, limb and spar on the bike."""

    def __init__(self, a: Point, b: Point, radius: float) -> None:
        self.a, self.b, self.radius = a, b, radius

    def sdf(self, point: Point) -> float:
        ax, ay = self.a
        dx, dy = self.b[0] - ax, self.b[1] - ay
        span = dx * dx + dy * dy
        along = 0.0 if span == 0.0 else ((point[0] - ax) * dx + (point[1] - ay) * dy) / span
        along = max(0.0, min(1.0, along))
        return math.dist(point, (ax + along * dx, ay + along * dy)) - self.radius

    def moved(self, turn: Turn) -> "Capsule":
        return Capsule(turn(self.a), turn(self.b), self.radius)

    def reach(self) -> float:
        return max(math.hypot(*self.a), math.hypot(*self.b)) + self.radius

    def bottom(self) -> float:
        return max(self.a[1], self.b[1]) + self.radius


def rotation(degrees: float) -> Turn:
    """Screen-space turn: y grows downward, so a positive angle lifts the nose."""
    rad = math.radians(degrees)
    cos, sin = math.cos(rad), math.sin(rad)

    def turn(point: Point) -> Point:
        x, y = point
        return (x * cos + y * sin, -x * sin + y * cos)

    return turn


# -- the bike -----------------------------------------------------------------
#
# Level and facing right, in pixels, with the origin at the sprite's centre --
# which is the point the renderer puts at `surface.point + surface.normal * GROUND`.
#
# GROUND is therefore the one measurement here with consequences outside the
# drawing: it is `constants.SPRITE_RADIUS`, and the wheels are tangent to it by
# construction, so "the bike stands on the ground" is a property of the model
# rather than something the renderer has to be told. Its value is bounded from
# both sides. Too small and the bike is a toy in a 16px cell; too large and the
# wheels -- the farthest material from the origin, at `hypot(WHEEL_X, GROUND -
# WHEEL_R - TYRE) + WHEEL_R + TYRE` -- swing outside the cell somewhere in the
# 32 poses and the sprite is quietly clipped. 6.6 leaves 8.38 against a bound of
# 8.5, and `overflow()` is 0.

GROUND = 6.6
WHEEL_R = 2.3  # tyre centreline
TYRE = 0.7  # half its thickness
WHEEL_X = 4.0  # half the wheelbase
AXLE = GROUND - WHEEL_R - TYRE


def chassis() -> list[Part]:
    """The machine, in no particular order -- a union does not have one."""
    rear = (-WHEEL_X, AXLE)
    front = (WHEEL_X, AXLE)
    return [
        Ring(*rear, WHEEL_R, TYRE),
        Ring(*front, WHEEL_R, TYRE),
        # Engine, between the wheels and the only part with room for a rim.
        Capsule((-1.6, AXLE - 1.4), (1.2, AXLE - 1.4), 1.2),
        # Swing arm back to the rear axle; forks up from the front one.
        Capsule(rear, (-0.8, AXLE - 1.0), 0.55),
        Capsule(front, (2.2, AXLE - 3.8), 0.55),
        # Seat and tank, then the bar.
        Capsule((-3.4, AXLE - 3.2), (0.8, AXLE - 3.6), 0.9),
        Capsule((2.4, AXLE - 4.0), (3.4, AXLE - 4.2), 0.5),
    ]


# The rider is four shapes -- leg, torso, helmet, arm -- and a *pose* is where
# those four go. Split out of the model because the crash needs the two halves
# apart: a bike lying on the ground has nobody on it, and a rider walking back to
# it has no bike under them. Riding, they are drawn as one silhouette and the
# union hides the join, which is exactly as it was.
#
# Coordinates are a drop from the axle, because that is the coordinate the rest
# of this model is authored in -- so `RIDING` below is the four literals that
# used to sit at the bottom of `model()`, moved and not rewritten. That matters
# more than it looks: `tests/test_sprite_gen.py` compares the committed PNGs byte
# for byte, so a split that changed a number would be caught, and a split that
# did not is proven to have changed nothing.
# `leg2` is the far leg, and it is optional because the riding pose has no use
# for one: sat on a bike, the second leg is behind the first and drawing it
# would add nothing but a pixel of width. Standing up it is what stops the
# figure reading as a stick.
#: A limb: `(start, end, radius)`, the start and end a drop from the axle.
Limb = tuple[Point, Point, float]


class Pose(NamedTuple):
    """Where the rider's shapes go. `helmet` is `(centre, radius)`."""

    leg: Limb
    torso: Limb
    helmet: tuple[Point, float]
    arm: Limb
    leg2: Limb | None = None

RIDING = Pose(
    # Leaning forward, arm out to the bar.
    leg=((-1.4, -3.6), (-0.4, -1.6), 0.85),
    torso=((-1.2, -4.2), (0.9, -6.4), 1.15),
    helmet=((1.5, -7.2), 1.4),
    arm=((0.9, -5.8), (2.8, -4.2), 0.55),
)


def rider(pose: Pose) -> list[Part]:
    """The four shapes of one pose."""

    def limb(part: Limb) -> Capsule:
        (ax, ay), (bx, by), radius = part
        return Capsule((ax, AXLE + ay), (bx, AXLE + by), radius)

    (helmet_x, helmet_y), helmet_r = pose.helmet
    parts: list[Part] = [
        limb(pose.leg),
        limb(pose.torso),
        Disc(helmet_x, AXLE + helmet_y, helmet_r),
        limb(pose.arm),
    ]
    if pose.leg2 is not None:
        parts.append(limb(pose.leg2))
    return parts


def model() -> list[Part]:
    """The bike as it is ridden: the machine, with somebody on it."""
    return chassis() + rider(RIDING)


def standing(parts: Sequence[Part]) -> list[Part]:
    """The same parts, dropped so their lowest material sits on `GROUND`.

    The ridden bike needs none of this: `AXLE = GROUND - WHEEL_R - TYRE` puts the
    wheels on the ground line by construction, which is what lets the renderer
    place every one of the 32 poses at `surface.point + surface.normal * SPRITE_RADIUS`
    and never think about it again.

    Nothing else in the crash has that property. A chassis turned on its side and
    a rider lying next to it are wherever the rotation left them, and an offset
    guessed by eye is exactly the 3px burial `SPRITE_RADIUS` exists to have
    stopped. So each pose is *measured* and dropped instead, and the renderer
    goes on using the one number it already has.
    """
    drop = GROUND - max(part.bottom() for part in parts)

    def shift(point: Point) -> Point:
        return (point[0], point[1] + drop)

    return [part.moved(shift) for part in parts]


def posed(degrees: float) -> list[Part]:
    turn = rotation(degrees)
    return [part.moved(turn) for part in model()]


# -- the crash ----------------------------------------------------------------
#
# Six more sprites, and between them they are the whole of the animation: one
# wreck and five poses of a rider who is no longer on it. What they *are* is
# here, because they are the same model as the bike and drawing them any other way would give this game two
# riders drawn two ways.
#
# None of them is a rotation of anything the renderer indexes, so none of them
# is named `bike%02d`. They are their own group.

# The bike lying on the ground: upside down, wheels in the air.
#
# **Chosen by looking**, over all 32 rotations of the riderless chassis, and the
# guess it replaced was 112.5 -- past vertical, on the argument that 90 is a
# stoppie rather than a wreck. That argument is right and its answer was wrong:
# 112.5 reads as a bike *propped up on its end*, and so does everything from 200
# to 240. At 16px the flattest silhouette is the one that reads as lying down,
# and the flattest is the full half-turn. It is `bike16`'s own angle, so the
# wreck is exactly the pose the bike would be in upside down with nobody on it.
LIE = 180.0

# The five poses. Same coordinates as `RIDING` -- a drop from the axle -- but
# with no bike under them, so `standing` is what puts them on the ground.
LYING = Pose(
    # Face down, head forward: they went over the bars and slid. Flat and wide,
    # which is the silhouette that reads as "on the ground" at this size.
    leg=((-4.4, -0.8), (-1.6, -1.0), 0.8),
    leg2=((-4.0, -2.2), (-1.4, -1.9), 0.8),
    torso=((-1.2, -1.5), (1.6, -2.0), 1.5),
    helmet=((3.4, -2.4), 1.7),
    arm=((0.4, -0.7), (2.6, -0.7), 0.7),
)

RISING = Pose(
    # Up on one knee: the near leg planted, the far one still folded under.
    leg=((-1.4, 0.0), (0.2, -3.4), 0.8),
    leg2=((-3.2, -0.8), (-0.6, -1.4), 0.8),
    torso=((0.4, -3.8), (0.9, -6.2), 1.4),
    helmet=((1.9, -7.8), 1.7),
    arm=((0.8, -5.8), (2.4, -4.2), 0.7),
)

# The walk is two frames. Only the legs and the arm move: swinging the torso as
# well reads as turning round rather than as walking.
WALK_A = Pose(
    # Mid-stride, legs well apart -- at this size a stride is the only thing
    # that says "walking" rather than "standing".
    leg=((-2.8, 0.0), (-0.2, -4.6), 0.8),
    leg2=((2.6, 0.0), (0.2, -4.6), 0.8),
    torso=((0.0, -5.0), (0.2, -7.6), 1.4),
    helmet=((0.9, -9.6), 1.7),
    arm=((0.2, -7.2), (2.0, -5.8), 0.7),
)

WALK_B = Pose(
    # Feet together, arm swung back: the other half of the cycle.
    leg=((-0.9, 0.0), (-0.2, -4.6), 0.8),
    leg2=((1.0, 0.0), (0.2, -4.6), 0.8),
    torso=((0.0, -5.0), (0.2, -7.6), 1.4),
    helmet=((0.9, -9.6), 1.7),
    arm=((0.2, -7.2), (-1.4, -5.9), 0.7),
)

LIFTING = Pose(
    # Bent over the bike, arm down, hauling it back up.
    leg=((-2.6, 0.0), (-1.0, -4.0), 0.8),
    leg2=((-0.6, 0.0), (-0.6, -4.0), 0.8),
    torso=((-0.8, -4.4), (1.8, -6.2), 1.4),
    helmet=((3.2, -6.8), 1.7),
    arm=((1.8, -5.6), (3.0, -3.0), 0.7),
)

CRASH_POSES = {
    "rider_lying": LYING,
    "rider_rising": RISING,
    "rider_walk_a": WALK_A,
    "rider_walk_b": WALK_B,
    "rider_lifting": LIFTING,
}

# The wreck first, then the rider in the order the crash draws them.
CRASH_NAMES = [
    "wreck",
    "rider_lying",
    "rider_rising",
    "rider_walk_a",
    "rider_walk_b",
    "rider_lifting",
]


def crashed(name: str) -> list[Part]:
    """The parts of one crash sprite, already standing on the ground line."""
    if name == "wreck":
        turn = rotation(LIE)
        return standing([part.moved(turn) for part in chassis()])
    return standing(rider(CRASH_POSES[name]))


# -- the two questions --------------------------------------------------------
#
# Same pair as tile_gen's, and the same order: material first, shade second.
# There the two use different supports (unbounded for one, clamped for the
# other) because terrain has to chain across cells. A bike is one object in one
# cell, so both read the same union and the distinction collapses -- which is
# worth saying, because the *absence* of that subtlety here is the reason this
# file is short.

def raster(parts: Sequence[Part], style: StyleLike = None, size: int = CELL,
           origin: Point | None = None) -> Raster:
    """The size*size palette indices of one pose, row-major.

    `origin` defaults to the centre of the canvas. A larger `size` is how
    `overflow` looks at what a 16x16 cell would have cut off.
    """
    look = _style(style)
    ox, oy = origin if origin is not None else (size / 2.0, size / 2.0)
    out: list[int] = []
    for y in range(size):
        for x in range(size):
            point = (x + 0.5 - ox, y + 0.5 - oy)
            distance = min(part.sdf(point) for part in parts)
            # No texture: a bike is a machine, so its mass is the flat shade
            # whatever the ground is made of.
            out.append(SKY if distance > EPS else look.shade(-distance, texture="bike"))
    return tuple(out)


def overflow(style: StyleLike = None) -> int:
    """Material pixels any pose would lose off the edge of its cell.

    Rasters each pose on a canvas of twice the size and counts what falls
    outside the middle. Zero is the only acceptable answer, and it is checked
    over all 32 rather than argued about, because clipping shows up in one
    rotation and not its neighbours -- which reads as a wobble rather than as a
    missing pixel.
    """
    big = 2 * CELL
    edge = CELL // 2
    worst = 0
    sets = [posed(index * 360.0 / FRAMES) for index in range(FRAMES)]
    # The crash sprites have to be asked the same question and the upright
    # bike's answer does not cover them: `standing` moves the origin, so the
    # 8.38-of-8.5 headroom the wheels leave when the model is centred says
    # nothing about a wreck lying on its back or a rider a head taller than it.
    sets += [crashed(name) for name in CRASH_NAMES]
    for parts in sets:
        art = raster(parts, style, size=big)
        lost = sum(
            1
            for y in range(big)
            for x in range(big)
            if art[y * big + x] != SKY and not (edge <= x < edge + CELL and edge <= y < edge + CELL)
        )
        worst = max(worst, lost)
    return worst


def collect(style: StyleLike = None) -> dict[str, Raster]:
    """{name: art} for the 32 poses and the six of the crash.

    One dictionary and therefore one `--check`: the crash art is written by the
    same tool from the same model, so "art/moto is what the model says" stays a
    single claim rather than becoming two that can drift apart.
    """
    art = {
        name: raster(posed(index * 360.0 / FRAMES), style)
        for index, name in enumerate(NAMES)
    }
    art.update({name: raster(crashed(name), style) for name in CRASH_NAMES})
    return art


# -- output -------------------------------------------------------------------


def sheet(art: Mapping[str, Sequence[int]], scale: int = 1,
          style: StyleLike = None) -> bytes:
    """Everything the tool draws, eight across, for looking at it together.

    Nearest-neighbour `scale`, because 38 sprites of 16px is 128x80 and nobody
    can judge a bike at that size on a modern screen. Not part of the game.

    The rows are the 32 rotations and then the crash, in `NAMES + CRASH_NAMES`
    order rather than sorted, so the poses read in the order they are used.
    """
    order = [name for name in NAMES + CRASH_NAMES if name in art]
    across = 8
    down = (len(order) + across - 1) // across
    width, height = across * CELL * scale, down * CELL * scale
    pixels = [SKY] * (width * height)
    for index, name in enumerate(order):
        col, row = index % across, index // across
        for y in range(CELL * scale):
            for x in range(CELL * scale):
                shade = art[name][(y // scale) * CELL + x // scale]
                pixels[(row * CELL * scale + y) * width + col * CELL * scale + x] = shade
    return encode_png(pixels, width, height, style=style)


def write(directory: str, style: StyleLike = None) -> list[str]:
    """Generate every pose into `directory`. Returns the names written."""
    look = _style(style)
    return write_art(directory, collect(look), look)


DEFAULT_OUT = os.path.join(os.path.dirname(_HERE), "art", "moto")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    generator_arguments(parser, DEFAULT_OUT, "poses")
    # ...and the one thing only this generator can do: all 32 on one sheet, for
    # looking at the rotation set rather than at a pose.
    parser.add_argument("--sheet", metavar="PATH", help="write all 32 to one PNG")
    parser.add_argument("--scale", type=int, default=4, help="nearest-neighbour zoom for --sheet")
    args = parser.parse_args()

    look = _style(args.style)
    art = collect(look)
    if args.sheet:
        with open(args.sheet, "wb") as handle:
            handle.write(sheet(art, args.scale, look))
        print("%d poses -> %s" % (len(art), args.sheet))
        return 0
    return generator_main(parser, args, art, "poses", "the model says")


if __name__ == "__main__":
    sys.exit(main())
