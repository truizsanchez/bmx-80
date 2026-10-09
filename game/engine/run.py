"""A run: one bike on one course, from the countdown to the end of the race.

What the original's main loop does around the physics:

- **the countdown**: 48 iterations with the bike idling, the throttle already
  read; at the end the bike is stopped and the idling shiver is taken out of y,
  and the same iteration's tick starts it riding if the throttle is held. **They
  are slower than the race's iterations** -- the original's loop runs about 18 a
  second before the green against about 41 after it, and holds the first for
  about 54 frames -- which changes nothing here, the clocks being stopped, and
  is what the window paces the start by (`main.COUNTDOWN_STEPS`);
- **the loop counter**, which paces a jump's turn and a wheelie's nose, counted
  once an iteration;
- **the pad**, read once an iteration: a button is *new* when it is held now and
  was not on the last iteration -- so a tap shorter than an iteration can be
  missed, as it can in the original;
- **two clocks**, in hundredths of a second: the race's time counts up and the
  time left counts down, **two hundredths a tick** -- about 41 ticks a second, so
  the original's second is a little slower than a real one. Both stop in the
  countdown and once the game has taken over past the line. The time left
  starts at the course's qualifying time for the level; a T adds ten seconds;
  at nothing the race is lost;
- **the lines**, on the bike's x to the 16 px: at `LAP_LINE` the one lap left is
  counted off and every crate comes back; at `FINISH_LINE` the game holds the
  throttle; at `TAKEOVER_LINE` it takes the bike over -- riding or flying -- and
  from `CELEBRATION_X` on the ground the bike celebrates until the race is over;
- **the things on the course**, picked up after the move (`items.py`);
- **the camera** (`camera.py`), moved before the physics by the player's velocity,
  and **the screen's background** (`background.py`) scrolled after it: the course
  as the screen has it, which is not the map where the map changed in view;
- **the computer's bike**, against the player (`rival.py`): driven by its rules,
  stepped by the same tick right after the player's, crossing the same lines;
- **what the iteration made a sound for** (`cues`), the player's alone: the
  countdown's beeps at 34, 26 and 18 iterations left and its go at 10; the
  player's bike's own; a thing picked up; every third iteration riding sand; and
  the take-over line, for which every other sound stops. And the engine's pitch
  (`revs`), which the original's sound reads every iteration.
"""

from game.engine import rival as rivals
from game.engine.background import Background
from game.engine.bike import Bike
from game.engine.camera import Camera
from game.engine.items import Flash, Item, SECRET, give, taken
from game.engine.original import (
    BEEPS_AT,
    BEST_CAP,
    BYTE,
    CELEBRATION,
    CLOCK_STEP,
    COUNTDOWN,
    EMPTY,
    FINISH_LINE,
    GO_AT,
    HURRY,
    LAP_LINE,
    LAPS,
    LINE_GRID,
    NO_LIMIT,
    PIXEL,
    SAND_BEAT,
    START_X,
    START_Y,
    T,
    TAKEOVER_LINE,
    WORD,
)
from game.engine.rules import CLASSIC, Auto, Cue, Ruleset, State
from game.engine.speed import Speed
from game.engine.terrain import Ground

#: The idling shiver lives in this bit of y's pixel byte.
SHIVER = 1 << PIXEL

FINISHED, TIME_UP = "finished", "time up"


class Run:
    """A bike on a course, stepped an iteration at a time."""

    def __init__(self, ground: Ground, limit: int = NO_LIMIT, rival: bool = False,
                 level: int = 0, rules: Ruleset = CLASSIC) -> None:
        #: What both bikes are ridden by: the original's unless a mode says.
        self.rules = rules
        self.bike = Bike(ground, rules, x=START_X << PIXEL, y=START_Y << PIXEL,
                         state=State.COUNTDOWN, speed=Speed.of(rules))
        #: The computer's bike, when there is one: on the grid beside the player,
        #: at its best from the start.
        self.rival: Bike | None = None
        if rival:
            self.rival = Bike(ground, rules, x=START_X << PIXEL, y=START_Y << PIXEL,
                              state=State.COUNTDOWN, speed=Speed.of(rules), player=False,
                              checks_landing=False)
            self.rival.speed.cap = BEST_CAP
            self.rival.speed.nitros = BYTE
        self.level = level
        self.camera = Camera()
        self.ground = ground
        #: What the screen shows of the course, which is the map as each column
        #: of it was when it scrolled into view.
        self.background = Background(ground)
        self.background.scroll(self.camera.px[0])
        self.countdown = COUNTDOWN
        #: The main loop's counter, as the physics reads it.
        self.tick = 0
        self.iterations = 0
        self._held = 0
        self.items = [Item(kind, row, col) for kind, row, col in ground.items()]
        self.laps_left = LAPS
        #: Hundredths of a second: the race's time, and the time left.
        self.elapsed = 0
        #: ...and the computer's own, which is a clock of its own and not a copy
        #: of the player's: the two bikes reach the line at different moments,
        #: and each one's clock stops when that bike gets there.
        self.rival_elapsed = 0
        self.left = limit
        self.lap_time: int | None = None
        #: How the race ended, or None while it is on.
        self.over: str | None = None
        #: What this iteration made a sound for, in order.
        self.cues: list[Cue] = []
        #: The flourish a secret taken has left on the screen, while it lasts.
        self.flash: Flash | None = None
        self._sand = 0

    @property
    def finished(self) -> bool:
        return self.over is not None

    @property
    def hurrying(self) -> bool:
        """Whether the clock is pressing: under ten seconds left.

        The original reads this every iteration and takes the music's tempo
        from the other of two tables while it holds. Two conditions of its own
        are left out -- it skips the reading in the bike's last state and once
        the game has taken over past the line -- because in both of those the
        clock has stopped moving anyway, so the answer cannot change.
        """
        return self.left < HURRY

    @property
    def rival_time(self) -> int | None:
        """The computer's time, if it got to the line, in hundredths.

        **None until it does**, which is the usual end of a race against it: the
        player crosses the line, the results go up, and the other bike is still
        riding. Its clock says nothing then and the results say so.
        """
        rival = self.rival
        if rival is None or rival.auto < Auto.RIDING:
            return None
        return self.rival_elapsed

    @property
    def revs(self) -> int:
        """What the engine's note is pitched by, as the player's speed left it."""
        return self.bike.speed.revs

    def step(self, held: int) -> None:
        """One iteration of the main loop, with the buttons held now -- in the
        original's order: the countdown, the flourish, the camera, the player,
        the computer's bike, then the clocks."""
        self.cues = []
        if self.over:
            return
        new = held & ~self._held
        self._held = held
        self.tick = (self.tick + 1) & BYTE
        self.iterations += 1
        if self.countdown:
            self._count_down()
        if self.flash is not None:
            # It rises a pixel an iteration and then it is over. Stepped before
            # the bike so that the iteration it was taken on is its first and
            # not a frame it spent where the bike still was.
            self.flash.step()
            if not self.flash.left:
                self.flash = None
        self.camera.move()
        self._player(held, new)
        if self.rival is not None:
            self._computer(self.rival)
        self.camera.drawn(self.bike)
        self.background.scroll(self.camera.px[0])
        self._clocks()

    def _count_down(self) -> None:
        """An iteration of the countdown: a beep, the go, and the bikes let go."""
        self.countdown -= 1
        if self.countdown in BEEPS_AT:
            self.cues.append(Cue.COUNT)
        elif self.countdown == GO_AT:
            self.cues.append(Cue.GO)
        if not self.countdown:
            for one in (self.bike, self.rival):
                if one is not None:
                    one.state = State.STOPPED
                    one.y &= ~SHIVER & WORD

    def _player(self, held: int, new: int) -> None:
        """The player's tick, and everything that reads where it left the bike."""
        bike = self.bike
        bike.step(held, new, self.tick)
        self.cues.extend(bike.cues)
        if bike.wall_snapped:
            self.camera.snap_x()
        self._lines(bike)
        self._pick_up()
        # Where the bike ended this iteration goes on the trail the mini-maniacs
        # ride. **The player's only**: the computer's bike never has any. The
        # original does it in the pass that draws, which is after the physics,
        # so what is remembered is the place that is about to be on the screen.
        bike.remember()
        if bike.probes.second.soft and bike.magnitude:
            self._sand = (self._sand + 1) % SAND_BEAT
            if not self._sand:
                self.cues.append(Cue.SAND)
        self.camera.take(bike)

    def _computer(self, rival: Bike) -> None:
        """The computer's tick, driven by its own buttons, and its own clock."""
        rival.step(rivals.drive(rival, self.bike, self.camera, self.level), 0, self.tick)
        self._lines(rival)
        if rival.state is not State.COUNTDOWN and rival.auto < Auto.RIDING:
            self.rival_elapsed += CLOCK_STEP

    def _clocks(self) -> None:
        """The race's clock and the time left, which run from the go to the
        take-over; and whether the race is over."""
        bike = self.bike
        if bike.state is not State.COUNTDOWN and bike.auto < Auto.RIDING:
            self.elapsed += CLOCK_STEP
            self.left = max(0, self.left - CLOCK_STEP)
            if not self.left:
                self.over = TIME_UP
        if bike.state is State.FINISHED and bike.finish_timer <= 0:
            self.over = FINISHED

    def _lines(self, bike: Bike) -> None:
        line = (bike.x >> PIXEL) & LINE_GRID
        if line == LAP_LINE and bike is self.bike and self.laps_left:
            self.laps_left -= 1
            self.lap_time = self.elapsed
            for item in self.items:
                item.there = True
                self.ground.put(item.row, item.col, item.kind if item.kind < SECRET else EMPTY)
            # ...and the sign over the finish goes up, because this is the last
            # lap. What that is, and whether the course has one, is the course's.
            self.ground.goal()
        elif line == FINISH_LINE and bike.auto is Auto.NONE:
            bike.auto = Auto.THROTTLE
        elif line == TAKEOVER_LINE and bike.auto < Auto.RIDING:
            bike.auto = Auto.RIDING if bike.state is State.RIDING else Auto.AIR
            bike.finish_timer = CELEBRATION
            if bike is self.bike:
                self.cues.append(Cue.FINISH)

    def _pick_up(self) -> None:
        for item in self.items:
            if item.there and item.reached(self.bike):
                item.there = False
                if item.kind >= SECRET:
                    self.flash = taken(self.bike, item.kind)
                self.left += give(self.bike, item.kind)
                self.cues.append(Cue.SECRET if item.kind >= SECRET
                                 else Cue.TIME if item.kind == T else Cue.PICKUP)
                if item.kind < SECRET:
                    self.ground.put(item.row, item.col, EMPTY)
                    self.background.take(item.row, item.col, EMPTY)
