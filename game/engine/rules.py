"""The engine's vocabulary: the states a bike can be in, the moments a race
makes a sound for, the pad, and the rules a mode may move.

The numbers themselves are `original.py`'s.

**A different game is a `Ruleset`.** The few numbers another mode may move are
gathered in one, and `CLASSIC` -- the only one a race gets unless it asks -- is
the original's exactly. Everything else stays fixed for every ruleset.
"""

from dataclasses import dataclass
from enum import Enum, IntEnum

from game.engine.original import (
    BYTE,
    CAP,
    CAP_S,
    INDEX_STEP,
    LAND_AHEAD,
    LAND_BEHIND,
    MAGNITUDE_MAX,
    NITROS_START,
    QUADRANT,
)


class State(IntEnum):
    """What a bike is doing, numbered as the original numbers them."""

    STOPPED = 0
    RIDING = 1
    AIR = 2
    WHEELIE = 3
    FALLING = 4
    CRASHING = 5
    FINISHED = 6
    COUNTDOWN = 7
    DOWN = 8


class Auto(IntEnum):
    """Who holds the throttle: nobody, or the game itself, near the finish."""

    NONE = 0
    #: Past the finish line: the throttle is held for you.
    THROTTLE = 1
    #: Further on: the index is raised to the cap, riding...
    RIDING = 2
    #: ...or in the air.
    AIR = 3
    #: The celebration: the index is left alone.
    CELEBRATING = 4


class Cue(Enum):
    """A moment the original makes a sound for. Which sound is the cartridge's
    business, or this game's own: the race only says when."""

    #: The countdown's three, two, one...
    COUNT = "count"
    #: ...and go.
    GO = "go"
    #: A nitro: on the ground, or in the air in the moment after a take-off...
    NITRO = "nitro"
    #: ...or anywhere in a flight with the J.
    JET = "jet"
    #: B on the ground with no nitros left.
    EMPTY = "empty"
    #: An S, an N or an R picked up.
    PICKUP = "pickup"
    #: A T picked up.
    TIME = "time"
    #: A secret found: the J or a mini-maniac.
    SECRET = "secret"
    #: Riding sand: every third iteration on it while moving.
    SAND = "sand"
    #: A tumble: every eighth tick of it.
    TUMBLE = "tumble"
    #: A crash that ends falling or down.
    CRASH = "crash"
    #: The take-over line: every other sound stops for this one.
    FINISH = "finish"

# -- a ruleset -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ruleset:
    """The numbers a mode other than the original's may move, and nothing else.

    A bike and a race carry one; the default is `CLASSIC`, which is the
    original's, so a race that does not ask rides as the original does.
    """

    #: The top of the speed index with nothing picked up, and with an S.
    cap: int = CAP
    cap_s: int = CAP_S
    #: How far the index moves in one tick, on the throttle or off it.
    index_step: int = INDEX_STEP
    #: Nitros in hand at the start.
    nitros: int = NITROS_START
    #: The landing window, in steps behind and ahead of the surface.
    land_behind: int = LAND_BEHIND
    land_ahead: int = LAND_AHEAD

    def __post_init__(self) -> None:
        if not 0 < self.cap <= self.cap_s <= MAGNITUDE_MAX:
            raise ValueError("the caps must be 0 < cap <= cap_s <= %d, got %d and %d"
                             % (MAGNITUDE_MAX, self.cap, self.cap_s))
        if self.index_step <= 0:
            raise ValueError("the index must move, got a step of %d" % self.index_step)
        if not 0 <= self.nitros <= BYTE:
            raise ValueError("nitros are a byte, got %d" % self.nitros)
        if not (0 <= self.land_behind < QUADRANT and 0 <= self.land_ahead < QUADRANT):
            raise ValueError("a landing window is under a quarter turn each way, got %d and %d"
                             % (self.land_behind, self.land_ahead))


#: The original's rules.
CLASSIC = Ruleset()
