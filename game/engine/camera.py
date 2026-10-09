"""The original's camera: it rides with the bike's velocity rather than its place.

Once an iteration, before the physics, the camera moves by the player's velocity
of the iteration before -- sideways always, and up or down only when the bike's
picture is in the half of the screen it is heading away from, so the view keeps
the bike in its upper part while it climbs and its lower part while it falls.
Its y is held to 0..128 px, which is the course's 256 minus the 128 px view.
When the player is snapped onto a right-hand wall, the camera's x is snapped with
it; once the bike celebrates past the line, the camera stops. Its x is exact;
its y is as exact as the one input it cannot see -- where the bike's picture was
on the frame the game last drew, which an iteration a frame long and one two
frames long see differently -- and is right on all but a handful of ticks a race.
"""

from game.engine.bike import Bike
from game.engine.original import (
    BYTE, PIXEL, SCREEN_HALF, SPRITE_Y_OFFSET, X_ON_GRID, X_WORD, Y_LIMIT)
from game.engine.rules import Auto


class Camera:
    """Where the view is, in fixed point: y 8.8, x 16.8."""

    def __init__(self) -> None:
        self.y = Y_LIMIT
        self.x = 0
        self._vx = 0
        self._vy = 0
        #: Where the player's picture was last drawn, in the hardware's y.
        self.sprite_y = 0

    @property
    def px(self) -> tuple[int, int]:
        return self.x >> PIXEL, self.y >> PIXEL

    def move(self) -> None:
        """Before the physics: by the velocity taken after the last player tick."""
        y = self.y + self._vy
        self.y = 0 if y < 0 else min(Y_LIMIT, y)
        self.x = (self.x + self._vx) & X_WORD

    def snap_x(self) -> None:
        """The player was snapped onto a right-hand wall: so is the view."""
        pixel = (self.x >> PIXEL) & X_ON_GRID
        self.x = (self.x & BYTE) | pixel << PIXEL

    def take(self, bike: Bike) -> None:
        """After the player's tick: the velocity the next move will use -- none
        while the bike celebrates."""
        if bike.auto is Auto.CELEBRATING:
            self._vx = self._vy = 0
            return
        self._vx = bike.vx
        heading_down = bike.vy >= 0
        below = self.sprite_y >= SCREEN_HALF
        self._vy = bike.vy if heading_down == below else 0

    def drawn(self, bike: Bike) -> None:
        """The frame is drawn: where the player's picture is now."""
        self.sprite_y = (bike.px[1] - self.px[1] + SPRITE_Y_OFFSET) & BYTE
