"""The air: how a jump falls, how the rider turns the bike, and whether it lands.

**There is no gravity.** A bike leaves the ground in a straight line, and every
few ticks its direction of travel turns one or two steps towards straight down;
it falls in a straight line at a speed the jump sets. What a jump is -- how fast
the index drops, how often the direction turns, and by how much -- is its
**class**, fixed at take-off from two things: a fast index (a nitro's, or an
S's), and Up held.

The rider turns the bike, not the flight: Right and Left move the **attitude**, a
step a tick, and the direction of travel goes its own way. What the two have to
agree on is the landing: the bike lands if its attitude is within `LAND_BEHIND`
steps behind the surface's direction and `LAND_AHEAD` in front of it, and
crashes otherwise.
"""

from typing import NamedTuple

from game.engine.original import (
    AUTOMATIC,
    DIRECTIONS,
    FALL_AUTOMATIC,
    FALL_OTHER,
    FALL_SLOW,
    INDEX_FLOOR,
    INDEX_LIFT,
    LAND_AHEAD,
    LAND_BEHIND,
    LEFT,
    QUADRANT,
    RIGHT,
    RIGHT_DOWN_STOPS,
    SLOW,
    STRAIGHT_DOWN,
)


class Jump(NamedTuple):
    """How a jump of one class falls."""

    #: Index lost a tick once the hang is over.
    drop: int
    #: The direction turns on ticks where the loop counter `& period` is 0.
    period: int
    #: Steps the direction turns by.
    step: int


def jump(jump_class: int) -> Jump:
    """The slow jump falls fast; every other falls slower; the automatic one, slowest."""
    if jump_class == SLOW:
        return Jump(*FALL_SLOW)
    if jump_class == AUTOMATIC:
        return Jump(*FALL_AUTOMATIC)
    return Jump(*FALL_OTHER)


def fall(index: int, jump_class: int) -> int:
    """The index after one tick of a jump's fall."""
    if index < INDEX_FLOOR:
        index = INDEX_LIFT
    return index - jump(jump_class).drop


def turn(direction: int, step: int) -> int:
    """The direction of travel after one turn towards the ground.

    Heading left (9-24) it turns up to straight down and stops there. Heading
    right it turns the other way round and stops at 25 or 26 -- which one depends
    on where it started, since the step can be two.
    """
    if QUADRANT < direction <= STRAIGHT_DOWN:
        return min(STRAIGHT_DOWN, direction + step)
    if direction in RIGHT_DOWN_STOPS:
        return direction
    return (direction - step) % DIRECTIONS


def rotate(attitude: int, held: int) -> int:
    """Right noses the bike down a step, else Left noses it up a step."""
    if held & RIGHT:
        return (attitude - 1) % DIRECTIONS
    if held & LEFT:
        return (attitude + 1) % DIRECTIONS
    return attitude


def lands(attitude: int, surface: int, behind: int = LAND_BEHIND,
          ahead: int = LAND_AHEAD) -> bool:
    """Whether a bike pointing `attitude` lands on a surface of direction `surface`:
    within `behind` steps behind it and `ahead` in front."""
    return -behind <= (attitude - surface + DIRECTIONS // 2) % DIRECTIONS - DIRECTIONS // 2 \
        <= ahead
