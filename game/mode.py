"""A way to play: the rules a race is ridden by, and how fast the engine steps.

**Classic is the original**: its rules (`game/engine/rules.CLASSIC`) stepped
about 41 times for every 60 displayed frames, as its main loop does.

**Excessive is the same race sooner.** The engine steps at the display's rate,
60 for 60, so every course is ridden iteration for iteration as it is in
classic -- the same line, the same jumps, the same landings, the same clocks --
and it all arrives half as soon again. Nothing about the ground changes, so a
course that can be finished in classic can be finished here: what it asks for
is reflexes, a window of 17 ms an iteration where classic's is 24.

The clocks count iterations, as the original's do -- two hundredths each -- so
a qualifying time means the same race in either. That also makes a time in
excessive a time in *game* seconds, which run faster than real ones, and it is
why the board keeps classic's records only: two ways of playing are two races.

Pyxel-free, like the rest of the model.
"""

from dataclasses import dataclass

from game.constants import DISPLAY_FPS
from game.engine.rules import CLASSIC as CLASSIC_RULES
from game.engine.rules import Ruleset


@dataclass(frozen=True, slots=True)
class Mode:
    """How a race is played: by which rules, and at what rate."""

    name: str
    rules: Ruleset
    #: Engine steps for every `DISPLAY_FPS` displayed frames -- which is a
    #: second, so this is also steps a second.
    steps: int
    #: Whether a finish is offered to the board.
    keeps_records: bool

    @property
    def iteration_ms(self) -> float:
        """How long one iteration is on the screen: the finest a thumb works in."""
        return 1000.0 / self.steps


CLASSIC = Mode("classic", CLASSIC_RULES, 41, keeps_records=True)
EXCESSIVE = Mode("excessive", CLASSIC_RULES, DISPLAY_FPS, keeps_records=False)

#: Every mode, by the name `--mode` takes.
MODES = {mode.name: mode for mode in (CLASSIC, EXCESSIVE)}
