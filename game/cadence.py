"""How many engine steps a displayed frame owes: the display and the physics, apart.

The window runs at `DISPLAY_FPS` and an engine steps at its own rate, which need
not divide it. The original game steps its physics about 41 times for every 60
frames -- its main loop runs both bikes and an iteration takes longer than a
frame -- and an engine that means to reproduce it has to reproduce that rate,
not round it to one in two.

`Cadence(steps, frames)` hands out exactly `steps` for every `frames` displayed,
spread as evenly as integers allow and the same way every time, so a replay, a
test and the window agree on which frames stepped. It starts on a step: the first
frame after a reset moves the race, so a press of Enter is answered at once.

No Pyxel here, so it can be asked about with no window: which frames step is a
question about arithmetic.
"""


class Cadence:
    """`steps` engine steps spread evenly over every `frames` displayed frames."""

    __slots__ = ("steps", "frames", "_acc")

    def __init__(self, steps: int, frames: int) -> None:
        if steps <= 0 or frames <= 0:
            raise ValueError("a cadence needs a positive rate, got %d per %d" % (steps, frames))
        self.steps = steps
        self.frames = frames
        self._acc = 0
        self.reset()

    def reset(self) -> None:
        """Back to a first frame that steps."""
        # One short of a whole step, so the first `tick` crosses it.
        self._acc = self.frames - self.steps

    def tick(self) -> int:
        """Advance one displayed frame; how many engine steps it owes.

        0 or 1 while the engine is no faster than the display, which is every
        cadence the game uses; more if it ever were.
        """
        self._acc += self.steps
        owed, self._acc = divmod(self._acc, self.frames)
        return owed
