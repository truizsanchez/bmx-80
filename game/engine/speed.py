"""How fast the bike goes: an index, a curve, and a term for the slope.

Speed is not a velocity kept from tick to tick. It is an **index**, 0 to 144,
that the throttle walks up and releasing it walks down, two a tick either way.
Each tick the index is turned into a **magnitude** through a curve -- steep at
the bottom, flat at the top -- a **slope term** is added, and the magnitude is
turned into a velocity along the direction of travel (`vector.py`).

Three things follow, and they are the feel of the original:

- **The bike never rolls back.** The index stops at 0, on any slope, and nothing
  else can make the magnitude negative.
- **A coast from index `i` lasts `ceil(i / 2)` ticks, on any slope.** The slope
  term changes the magnitude, never the index.
- **Steepness does not enter.** A climb costs the same at 11.25 degrees as at
  78.75; only the direction's side of the circle does.

The order of the calls is the tick's, and `update_index`, `slope` and
`magnitude` are three separate steps of it: the slope term is set while riding
and spent by the magnitude of the *next* tick.
"""

from dataclasses import dataclass

from game.engine.original import (
    CAP,
    CURVE,
    CURVE_BASE,
    CURVE_EVERY,
    CURVE_FROM,
    CURVE_PER,
    CURVE_TOP,
    INDEX_CRASHING,
    INDEX_FINISHED,
    INDEX_STEP,
    MAGNITUDE_MAX,
    NITRO_INDEX,
    NITRO_TICKS,
    NITROS_START,
    QUADRANT,
    SLOPE_FLOOR,
    SLOPE_STEP,
    SLOPE_TOP,
    SOFT_TERM,
    STRAIGHT_DOWN,
)
from game.engine.rules import Auto, Cue, Ruleset, State


@dataclass(slots=True)
class Speed:
    """The bike's speed as the original keeps it: six small integers, and the
    step its ruleset walks the index by."""

    #: 0-144. What the throttle, the coast and a nitro move.
    index: int = 0
    #: Where the throttle stops: `original.CAP`, or `original.CAP_S` with an S.
    cap: int = CAP
    #: Nitros in hand.
    nitros: int = NITROS_START
    #: Ticks a nitro still holds the index where it put it.
    nitro_timer: int = 0
    #: The slope accumulator, walked two a tick on a slope.
    slope_acc: int = 0
    #: What the next magnitude adds, set while riding and spent by `magnitude`.
    slope_term: int = 0
    #: What the engine's note is pitched by: the index as `update_index` leaves
    #: it, and the curve's value once `magnitude` has read it.
    revs: int = 0
    #: How far the throttle and the coast move the index a tick.
    step: int = INDEX_STEP

    @classmethod
    def of(cls, rules: Ruleset) -> "Speed":
        """A bike's speed at the start of a race under `rules`."""
        return cls(cap=rules.cap, nitros=rules.nitros, step=rules.index_step)


def curve(index: int) -> int:
    """The magnitude an index stands for, before the slope.

    Four pieces: steps of eight at the very bottom, of sixteen to 7, then a line
    of slope two to 15, then two every four indices up to 112. From `CURVE_TOP`
    up -- which only a nitro reaches -- the index is its own value.
    """
    if index >= CURVE_TOP:
        return index
    for up_to, base, per, every in CURVE:
        if index <= up_to:
            return base + per * (index // every)
    return min(CURVE_TOP, CURVE_BASE + CURVE_PER * ((index - CURVE_FROM) // CURVE_EVERY))


def update_index(speed: Speed, state: State, throttle: bool, nitro_pressed: bool,
                 auto: Auto = Auto.NONE) -> Cue | None:
    """One tick of the index: the one rule the tick's state picks.

    In this order, the first that applies deciding: the celebration after the
    line; the throttle held for you past it; the index raised to the cap further
    on; the air; a crash tumble; a bike down; a nitro still running; and
    otherwise the player's own rule, `_player`.

    **In the air the index does not move here.** What changes it in flight --
    the fall, and a nitro fired in the air -- is the flight's.

    Returns the sound a press of B makes, if it made one.
    """
    cue = None
    if state is State.FINISHED:
        speed.index = INDEX_FINISHED
    elif auto is Auto.THROTTLE:
        _throttle(speed)
    elif auto >= Auto.RIDING:
        # Raised to the cap and never lowered to it, except in the air and in
        # the celebration, which leave it alone.
        if state is not State.AIR and auto is not Auto.CELEBRATING:
            speed.index = max(speed.index, speed.cap)
    elif state is State.AIR:
        pass
    elif state is State.CRASHING:
        speed.index = INDEX_CRASHING
    elif state is State.DOWN:
        speed.index = 0
    elif speed.nitro_timer > 0:
        # A nitro holds the index where it put it, and a second press is not read.
        speed.nitro_timer -= 1
    else:
        cue = _player(speed, throttle, nitro_pressed)
    speed.revs = speed.index
    return cue


def _player(speed: Speed, throttle: bool, nitro_pressed: bool) -> Cue | None:
    """The rule a rider's thumbs drive: a nitro on a press, else throttle or coast.

    A press with no nitros left is spent on a click -- that tick the index
    neither climbs nor falls. Returns the press's sound, if there was a press.
    """
    if nitro_pressed:
        if not speed.nitros:
            return Cue.EMPTY
        speed.nitros -= 1
        speed.nitro_timer = NITRO_TICKS
        speed.index = NITRO_INDEX
        return Cue.NITRO
    if throttle:
        _throttle(speed)
    else:
        _coast(speed)
    return None


def _throttle(speed: Speed) -> None:
    """Two up, to the cap and not past it.

    **Above the cap -- after a nitro -- the throttle coasts**, two down a tick
    with nothing to stop it at the cap on the way: from an even index it goes
    one step under an odd cap, and the next tick's climb clamps it back up.
    """
    if speed.index == speed.cap:
        return
    if speed.index > speed.cap:
        _coast(speed)
        return
    speed.index = min(speed.cap, speed.index + speed.step)


def _coast(speed: Speed) -> None:
    """Two down, and never below zero: the bike never rolls back."""
    speed.index = max(0, speed.index - speed.step)


def slope(speed: Speed, direction: int, soft: bool, no_slope: bool) -> None:
    """The slope term, set while the wheels are on the ground.

    **Soft ground first**: it sets the term to `SOFT_TERM` -- `soft` is the
    caller's to decide, and riding it is read only on the level (`bike.py`). Then, unless the R
    is held, the direction walks the accumulator:

    - **level** (direction 0): the accumulator is emptied and the term left alone;
    - **climbing** (1-7): two down, not lowered again once it is under
      `SLOPE_FLOOR` -- so it rests at -34 -- and the term becomes it;
    - **descending** (24-31): two up, to `SLOPE_TOP`, and the term becomes it;
    - **a wall or a ceiling** (8-23): nothing. There is no gravity on a wall.

    The original only ever draws sand on the level, so what the order decides in
    practice is the R: it skips the slope step and never the sand. **The R is for
    the hills** -- no loss climbing, and no gain descending -- and sand costs the
    same with it or without.
    """
    if soft:
        speed.slope_term = SOFT_TERM
    if no_slope:
        return
    if direction == 0:
        speed.slope_acc = 0
    elif direction < QUADRANT:
        if speed.slope_acc >= SLOPE_FLOOR:
            speed.slope_acc -= SLOPE_STEP
        speed.slope_term = speed.slope_acc
    elif direction >= STRAIGHT_DOWN:
        if speed.slope_acc < SLOPE_TOP:
            speed.slope_acc += SLOPE_STEP
        speed.slope_term = speed.slope_acc


def magnitude(speed: Speed) -> int:
    """This tick's magnitude: the curve, plus the slope term, held to 0..144.

    The term is spent: it is cleared here, so a term that nothing sets again
    this tick is gone by the next.
    """
    speed.revs = curve(speed.index)
    value = speed.revs + speed.slope_term
    speed.slope_term = 0
    return max(0, min(MAGNITUDE_MAX, value))
