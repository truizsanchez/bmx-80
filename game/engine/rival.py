"""The computer's bike: the same physics, and a few rules of its own.

The original runs the computer's bike through the very tick the player's goes
through, on its own copy of the state, and drives it with rules rather than a
pad:

- **its buttons**: the throttle and Up, always; and Left, in the air heading left
  of straight up with the nose not level -- which brings a tumble round;
- **the gap**, each tick. Ahead of the player by less than the level's reach
  (64, 128, 240 px for A, B, C) it is at its best: cap 119, the R, and it lands
  however it comes down. Further ahead it is held back: cap 79, no R, its
  landings checked like the player's, and Up masked -- no loop can be taken;
- **the teleport**: 48 px or more behind, it is put back on the course just off
  the left of the screen -- at the first stretch of the course's table that
  starts before there, 16 px before the view's edge if the stretch reaches it
  and at its end if not -- and never further back than it already is.

It picks nothing up, and loses nothing when it crashes.
"""

from game.engine.bike import Bike
from game.engine.camera import Camera
from game.engine.original import (
    BEHIND, BEST_CAP, BYTE, LEFT, OFF_SCREEN, PIXEL, QUADRANT, RIVAL_REACH, STRAIGHT_DOWN,
    THROTTLE, UP, WORD)
from game.engine.rules import State


def buttons(rival: Bike) -> int:
    """The throttle and Up, and Left to bring a tumble in the air round."""
    held = THROTTLE | UP
    if (rival.state is State.AIR and QUADRANT < rival.direction < STRAIGHT_DOWN
            and rival.attitude):
        held |= LEFT
    return held


def drive(rival: Bike, player: Bike, camera: Camera, level: int) -> int:
    """This tick's buttons for the computer's bike, and its handicap or its
    teleport by the gap to the player."""
    held = buttons(rival)
    ahead = (rival.x >> PIXEL & WORD) - (player.x >> PIXEL & WORD)
    if ahead > 0:
        near = ahead < RIVAL_REACH[level]
        rival.checks_landing = not near
        rival.speed.cap = BEST_CAP if near else rival.rules.cap
        rival.no_slope = near
        if not near:
            held &= ~UP
    elif -ahead >= BEHIND:
        _teleport(rival, camera)
    return held


def _teleport(rival: Bike, camera: Camera) -> None:
    edge = (camera.x >> PIXEL & WORD) - OFF_SCREEN & WORD
    for start, end, y in rival.ground.teleports():
        if start >= edge:
            continue
        if end >= edge:
            x = edge
        else:
            if end < (rival.x >> PIXEL & WORD):
                return
            x = end
        rival.x = (rival.x & BYTE) | x << PIXEL
        rival.y = (rival.y & BYTE) | y << PIXEL
        rival.attitude = rival.direction = rival.hang = rival.jump_class = 0
        rival.down_timer = 0
        rival.rider_off = False
        rival.state = State.RIDING
        return
