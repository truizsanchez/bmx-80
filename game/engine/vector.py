"""A magnitude along one of 32 directions, as a velocity in 1/256 px per tick.

The original turns a magnitude into `(vx, vy)` with a quarter sine and a rule
for the quadrant:

    i        = 8 * (direction mod 8)           the angle inside its quadrant
    a        = ((magnitude >> 1) * sine(i)) >> 4
    b        = ((magnitude >> 1) * sine(63 - i)) >> 4

`(vy, vx)` is `(a, b)`, swapped in the second and fourth quadrants, and signed
by the quadrant: up and left are negative. The sign goes on **after** the shift,
so a velocity and its opposite are exact negatives of each other.

The cosine is read at `63 - i` rather than `64 - i` -- one step short of the
quarter -- which is what the original does and what makes level ground give
`sine(63) = 255` rather than a value off the top of the scale.

**Direction does not change speed**: the sine is good to 1% everywhere it is read.

**A direction past a full turn** -- 32 to 40, which only a crash tumbling down
the slope it climbed takes -- travels as the direction half a turn back from it:
32 + k as 16 + k, down the slope the wrong way round.
"""

import math

from game.engine.original import DIRECTIONS, QUADRANT, SINE_SCALE, SINE_SHIFT, SINE_STEPS


def _quarter_sine(i: int) -> int:
    """`256 * sin` at step `i` of 64, rounded and held to a byte."""
    return min(SINE_SCALE, round((SINE_SCALE + 1) * math.sin(i * math.pi / (2 * SINE_STEPS))))


#: Computed once, from the rule: the one place a float is ever touched, and it
#: is gone before any tick runs.
_SINE = tuple(_quarter_sine(i) for i in range(SINE_STEPS))


def sine(i: int) -> int:
    """The quarter sine at step `i` of 64, as a byte.

    Only the sixteen steps `8k` and `63 - 8k` are ever read, and at those this
    is the original's value exactly.
    """
    if not 0 <= i < SINE_STEPS:
        raise ValueError("the quarter sine has %d steps, not %d" % (SINE_STEPS, i))
    return _SINE[i]


def velocity(magnitude: int, direction: int) -> tuple[int, int]:
    """`(vx, vy)` for a magnitude along a direction, y growing downward."""
    if direction >= DIRECTIONS:
        direction -= DIRECTIONS // 2
    direction %= DIRECTIONS
    quadrant, step = divmod(direction, QUADRANT)
    i = (SINE_STEPS // QUADRANT) * step
    half = magnitude >> 1
    vy = (half * sine(i)) >> SINE_SHIFT
    vx = (half * sine(SINE_STEPS - 1 - i)) >> SINE_SHIFT
    if quadrant % 2:
        vx, vy = vy, vx
    if quadrant in (0, 1):
        vy = -vy
    if quadrant in (1, 2):
        vx = -vx
    return vx, vy
