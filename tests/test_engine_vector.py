"""The velocity a magnitude and a direction make, in 1/256 px per tick.

Three of these numbers were measured on the original running -- its horizontal
velocity on level ground at full speed, with an S, and with an S on sand -- and
the rule reproduces all three to the integer. The rest is what the rule has to
be for those three to mean anything: 32 directions that do not change the speed,
and a velocity whose opposite is its exact negative.
"""

import math

import pytest

from game.engine.original import DIRECTIONS, MAGNITUDE_MAX
from game.engine.vector import sine, velocity
from game.engine.original import SINE_STEPS


@pytest.mark.parametrize("magnitude, vx, what", [
    (98, 780, "full speed"),
    (112, 892, "full speed with an S"),
    (56, 446, "an S on sand"),
])
def test_the_three_measured_speeds(magnitude, vx, what):
    """Measured on the original, level ground, one each. Exact, not close:
    `((m >> 1) * 255) >> 4` is how the original rounds, and it is what lands on
    the measured number."""
    assert velocity(magnitude, 0) == (vx, 0), what


@pytest.mark.parametrize("direction", range(DIRECTIONS))
def test_direction_does_not_change_speed(direction):
    """Within 1% of the level speed in every one of the 32 directions."""
    level = velocity(98, 0)[0]
    vx, vy = velocity(98, direction)
    assert 0.99 * level <= math.hypot(vx, vy) <= 1.001 * level, (vx, vy)


def test_the_four_axes():
    """0 is right, 8 up, 16 left, 24 down -- and y grows downward."""
    assert velocity(98, 0) == (780, 0)
    assert velocity(98, 8) == (0, -780)
    assert velocity(98, 16) == (-780, 0)
    assert velocity(98, 24) == (0, 780)


@pytest.mark.parametrize("direction", range(DIRECTIONS))
def test_the_opposite_direction_is_the_exact_negative(direction):
    """The sign goes on after the shift, so nothing rounds differently one way
    round than the other."""
    for magnitude in (7, 55, 98, MAGNITUDE_MAX):
        vx, vy = velocity(magnitude, direction)
        opposite = (direction + DIRECTIONS // 2) % DIRECTIONS
        assert velocity(magnitude, opposite) == (-vx, -vy)


@pytest.mark.parametrize("direction", range(1, 8))
def test_climbing_right_is_up_and_right(direction):
    vx, vy = velocity(98, direction)
    assert vx > 0 and vy < 0
    assert velocity(98, direction - 1)[1] > vy, "a steeper direction climbed less"


def test_everything_is_an_integer():
    for direction in range(DIRECTIONS):
        for magnitude in range(MAGNITUDE_MAX + 1):
            vx, vy = velocity(magnitude, direction)
            assert type(vx) is int and type(vy) is int


def test_the_quarter_sine_runs_from_nothing_to_a_byte():
    values = [sine(i) for i in range(SINE_STEPS)]
    assert values[0] == 0 and values[-1] == 255
    assert values == sorted(values)
    with pytest.raises(ValueError):
        sine(SINE_STEPS)
