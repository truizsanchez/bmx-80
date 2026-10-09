"""One bike, and one tick of the original's physics for it.

A tick, in the original's order:

1. the speed index (`speed.update_index`);
2. the world ceiling: in the air near the top, a direction pointing up is laid flat;
3. the magnitude and the velocity -- except falling and in the countdown, which
   keep the velocity they have. Riding with the index at 0 is stopping;
4. the state's own step (below);
5. the window of tiles around the bike, and
6. its probes (`probes.py`);
7. the collision response of the state (below);
8. the move: `y += vy`, `x += vx`, in fixed point.

**Every state but the finish's celebration is modelled**: stopped, riding, a
wheelie, the air, falling, tumbling, down, and the countdown.

**A wheelie** starts riding on the level with Left held. Held, the nose comes up
a step every other tick, on the level only; at 90 degrees it is a tumble.
Released, the nose comes down a step a tick to the direction of travel, and the
bike is riding again. Its ground check is the collision response, and it runs
on the tick riding starts one too.

**In the air** the state step is the flight (`flight.py`): the rider turns the
attitude, the jump hangs and then falls, and its direction of travel turns
towards the ground. The collision response is the landing: a head-first touch
above is a crash; otherwise the first of the attitude probes and the third floor
probe that touches solid is the surface, and the bike lands on it -- direction
and attitude its direction, snapped to the grid, riding again -- if the attitude
is inside the landing window, and crashes if not.

**A crash** starts by what is under the bike: nothing is a straight fall; level
ground, or the top of a slope, is down on the ground; a slope is a tumble.

- **Falling**, the bike keeps the velocity the crash gave it until a cell under it
  touches ground, and tumbles there.
- **Tumbling**, it turns end over end, two steps a tick, following the ground under
  it; when both cells under it are level it is down on the ground.
- **Down** is 57 ticks of the rider's own story, told with the position: the
  items are lost and the place is remembered; the rider is thrown along an arc
  the ground hands over (`Ground.throw`), lies, gets up and walks back; the
  remembered place is restored; and at the end the bike is stopped there, on the
  8 px grid. **The bike comes back where it came to rest.** The attitude carries
  the pictures of the rider meanwhile, which is why it passes 31.

Riding, the state step is the slope term, the sand and the start of a wheelie;
the collision response is **following the ground**: when the third floor probe
touches solid, the tile's direction becomes the bike's direction and attitude,
and on the level, up a right-hand wall and on a ceiling the position is snapped
to the tile grid and the velocity across it zeroed. With nothing under the
wheels, the bike takes off -- unless another floor probe still touches.

**What a tick makes a sound for** is kept in `cues`: a nitro fired, on the ground
or in the air, and B pressed with none left; every eighth tick of a tumble; and a
crash that ends falling or down. Which sound each is, is not the bike's business.
"""

from dataclasses import dataclass, field

from game.engine import flight
from game.engine.probes import Probes, probe, window
from game.engine.original import (
    AIR_NITRO_ATTITUDE,
    AIR_NITRO_HANG,
    AUTO_CLASS,
    BYTE,
    CEILING,
    CEILING_LIFT,
    CELEBRATION_ATTITUDE,
    CRAWL_BLINK,
    CRAWL_FROM,
    DIRECTIONS,
    DOWN_TICKS,
    FALL_SPEED,
    FAST,
    FAST_CLASS,
    FINISH_MASK,
    FINISH_SHIFT,
    FINISH_Y,
    FLOURISH_BEAT,
    FLOURISH_FROM,
    FLOURISHES,
    GRID,
    HALF_TURN,
    HANG_PER_CLASS,
    HEAD_FIRST,
    LANDED_FROM,
    LEFT,
    NITRO,
    NITRO_INDEX,
    NITRO_TICKS,
    NOT_LEVEL,
    PIXEL,
    POSE_CRAWLING,
    POSE_FLYING,
    POSE_OFF,
    POSE_READY,
    POSE_REMOUNT,
    POSE_SITTING,
    QUADRANT,
    READY_FROM,
    REMOUNT_FROM,
    ROCK_TUMBLE_AIR,
    SNAP_LEVEL,
    SOFT_TERM,
    STANDING_FROM,
    STRAIGHT_DOWN,
    THROTTLE,
    THROW_STEPS,
    THROWN_OFF,
    TRAIL,
    TUMBLE_BEAT,
    TUMBLE_LEVEL,
    TUMBLE_SPIN,
    UP,
    UP_45,
    UP_CLASS,
    WALL_RIGHT,
    WHEELIE_GROUND,
    WHEELIE_OVER,
    WORD,
    WORLD_TOP,
    X_WORD,
    Y_ON_GRID,
)
from game.engine.rules import CLASSIC, Auto, Cue, Ruleset, State
from game.engine.speed import Speed, magnitude, slope, update_index
from game.engine.terrain import SKY, Ground
from game.engine.vector import velocity

_NO_PROBES = Probes(SKY, SKY, SKY, SKY, SKY, SKY, SKY, SKY, SKY, SKY, 0)


@dataclass(slots=True)
class Bike:
    """One bike: where it is, where it is going, and how fast."""

    ground: Ground
    #: The numbers this bike is ridden by: the original's unless a mode says.
    #: Its `speed` is started from them by whoever makes the bike (`Speed.of`).
    rules: Ruleset = CLASSIC
    #: Pixels in 8.8 fixed point, y growing downward.
    y: int = 0
    #: Pixels in 16.8 fixed point.
    x: int = 0
    #: The direction of travel, 0-31.
    direction: int = 0
    #: Where the bike points, 0-31: what the picture shows and a landing checks.
    attitude: int = 0
    state: State = State.COUNTDOWN
    speed: Speed = field(default_factory=Speed)
    #: This tick's magnitude, and the velocity in 1/256 px per tick.
    magnitude: int = 0
    vx: int = 0
    vy: int = 0
    auto: Auto = Auto.NONE
    #: The R: the slope term is not applied.
    no_slope: bool = False
    #: The player's bike, as against the computer's.
    player: bool = True
    #: What the last tick's probes read -- which the next tick's state step uses.
    probes: Probes = _NO_PROBES
    #: Set by a take-off: the jump's class, and the ticks it hangs.
    jump_class: int = 0
    hang: int = 0
    #: Ticks after a take-off in which a nitro may be fired in the air anyway.
    air_nitro_window: int = 0
    #: The J: a nitro may be fired anywhere in a flight, nose up.
    jet: bool = False
    #: Mini-maniacs riding along, 0-3.
    minis: int = 0
    #: Where this bike has been, newest last: `(x, y, attitude)` an iteration,
    #: `TRAIL` of them. **The mini-maniacs ride on it** -- each one is the
    #: player some iterations ago -- so it is only kept for the bike that can
    #: have them, which the run decides.
    trail: list[tuple[int, int, int]] = field(default_factory=list)
    #: Past the line: ticks of the celebration left before the run is over.
    finish_timer: int = 0
    #: Set by this tick's snap onto a right-hand wall, which the camera follows.
    wall_snapped: bool = False
    #: Whether a landing is checked: the player's always are; the computer's
    #: bike in its fast setup lands whatever its attitude.
    checks_landing: bool = True
    #: Ticks a bike that is down stays down.
    down_timer: int = 0
    #: A tumble's direction as it started, and the ticks it spends in the air.
    tumble_from: int = 0
    tumble_air: int = 0
    #: What this tick made a sound for, in order (`rules.Cue`).
    cues: list[Cue] = field(default_factory=list)
    #: Down: whether the rider was thrown backwards (the tumble was down a climb),
    #: whether the rider is off the bike, and the place remembered: y, then x's
    #: whole pixels.
    thrown_back: bool = False
    rider_off: bool = False
    saved: tuple[int, int] = (0, 0)

    @property
    def px(self) -> tuple[int, int]:
        """Where the bike is, in whole pixels: `(x, y)`."""
        return self.x >> PIXEL, (self.y >> PIXEL) & BYTE

    def remember(self) -> None:
        """Put this iteration on the trail the mini-maniacs ride.

        **Nothing is remembered while the bike is standing still**, so the three
        of them do not pile up on a stopped bike; the original guards this the
        same way, off a work area its velocity is written into, and the exact
        shape of that guard is not read yet -- this is the part of it that can
        be seen.
        """
        if not (self.vx or self.vy):
            return
        x, y = self.px
        self.trail.append((x, y, self.attitude))
        del self.trail[:-TRAIL]

    def behind(self, back: int) -> tuple[int, int, int] | None:
        """Where this bike was `back` iterations ago, if it has been there."""
        return self.trail[-back - 1] if len(self.trail) > back else None

    def step(self, held: int, new: int, tick: int = 0) -> None:
        """One tick, with the pad's buttons held and newly pressed. `tick` is the
        main loop's counter, which paces the turn of a falling jump."""
        self.wall_snapped = False
        self.cues = []
        cue = update_index(self.speed, self.state, bool(held & THROTTLE), bool(new & NITRO),
                           self.auto)
        if cue:
            self.cues.append(cue)
        if self.state is State.AIR and self.auto is Auto.NONE:
            self._air_nitro(new)
        self._world_ceiling()
        if self.state not in (State.FALLING, State.COUNTDOWN):
            if self.speed.index == 0 and self.state is State.RIDING:
                self.state = State.STOPPED
            self.magnitude = magnitude(self.speed)
            self.vx, self.vy = velocity(self.magnitude, self.direction)
        self._state_step(held, tick)
        x, y = self.px
        cells = window(self.ground, y, x)
        self.probes = probe(self.ground, cells, y, x, self.direction, self.attitude, self.state)
        self._respond(held)
        self.y = (self.y + self.vy) & WORD
        self.x = (self.x + self.vx) & X_WORD

    # -- the steps -----------------------------------------------------------------

    def _world_ceiling(self) -> None:
        if self.state is not State.AIR or self.px[1] >= WORLD_TOP or self.direction == 0:
            return
        if self.direction <= QUADRANT:
            self.direction = 0
        elif self.direction < HALF_TURN:
            self.direction = HALF_TURN

    def _air_nitro(self, new: int) -> None:
        """A nitro in the air: in the ticks just after the take-off, or with the J
        and the nose up. It re-aims the flight along the nose and hangs it."""
        if not new & NITRO:
            return
        if not self.air_nitro_window and not (self.jet and self.attitude < AIR_NITRO_ATTITUDE):
            return
        if not self.speed.nitros:
            return
        self.cues.append(Cue.NITRO if self.air_nitro_window else Cue.JET)
        self.hang = AIR_NITRO_HANG
        self.direction = self.attitude
        self.speed.nitros -= 1
        self.speed.nitro_timer = NITRO_TICKS
        self.speed.index = NITRO_INDEX

    def _state_step(self, held: int, tick: int) -> None:
        """The state's own step: `STATE_STEPS` says which, one per state."""
        STATE_STEPS[self.state](self, held, tick)

    def _stopped(self, held: int, tick: int) -> None:
        if self.probes.second.soft:
            self.speed.slope_term = SOFT_TERM
        if self.magnitude:
            self.state = State.RIDING

    def _riding(self, held: int, tick: int) -> None:
        under = self.probes.second
        level = self.direction == 0 and not under.no_wheelie
        if level and held & LEFT and not self.probes.above.solid:
            self.state = State.WHEELIE
        slope(self.speed, self.direction, soft=level and under.soft, no_slope=self.no_slope)

    def _tumbling(self, held: int, tick: int) -> None:
        self.attitude = (self.attitude + TUMBLE_SPIN) % DIRECTIONS
        if not tick & TUMBLE_BEAT:
            self.cues.append(Cue.TUMBLE)

    def _celebrating(self, held: int, tick: int) -> None:
        """The celebration: a wheelie at 45 degrees, the game at the throttle."""
        self.auto = Auto.CELEBRATING
        self.finish_timer -= 1
        self.attitude = CELEBRATION_ATTITUDE

    def _lying(self, held: int, tick: int) -> None:
        self._down()

    def _idling(self, held: int, tick: int) -> None:
        """The engine idling: the bike shivers a pixel up and down."""
        self.y ^= 1 << PIXEL

    def _nothing(self, held: int, tick: int) -> None:
        """Falling: the physics does it all."""

    def _wheelie(self, held: int, tick: int) -> None:
        if self.probes.second.soft:
            self.speed.slope_term = SOFT_TERM
        if held & LEFT and self.auto is Auto.NONE:
            if self.direction or tick & 1:
                return
            self.attitude += 1
            if self.attitude >= WHEELIE_OVER:
                self.state = State.CRASHING
            return
        if self.attitude != self.direction:
            self.attitude -= 1
            if self.attitude != self.direction:
                return
        self.state = State.RIDING

    def _fly(self, held: int, tick: int) -> None:
        if self.auto is Auto.NONE:
            self.attitude = flight.rotate(self.attitude, held)
        if self.hang:
            self.hang -= 1
            return
        if self.air_nitro_window:
            self.air_nitro_window -= 1
        if self.auto >= Auto.RIDING:
            self._auto_attitude(tick)
        jump = flight.jump(self.jump_class)
        self.speed.index = flight.fall(self.speed.index, self.jump_class)
        if tick & jump.period:
            return
        self.direction = flight.turn(self.direction, jump.step)

    def _auto_attitude(self, tick: int) -> None:
        """Past the line, the game flies the bike: nose up a step a tick to 3, then
        every fourth tick through the rider's three flourishes, and it stays on
        the last."""
        if self.auto is not Auto.AIR:
            if self.attitude == FLOURISH_FROM:
                self.auto = Auto.AIR
            else:
                self.attitude = (self.attitude + 1) % DIRECTIONS
            return
        if tick & FLOURISH_BEAT:
            return
        if self.attitude == FLOURISHES[-1]:
            return
        if self.attitude in FLOURISHES[:-1]:
            self.attitude = FLOURISHES[FLOURISHES.index(self.attitude) + 1]
        elif self.attitude == FLOURISH_FROM:
            self.attitude = FLOURISHES[0]
        else:
            self.attitude = FLOURISH_FROM

    def _respond(self, held: int) -> None:
        if self.state is State.STOPPED:
            if QUADRANT < self.direction < STRAIGHT_DOWN:
                self._crash()
        elif self.state is State.RIDING:
            self._ride(held)
        elif self.state is State.AIR:
            self._land()
        elif self.state is State.WHEELIE:
            self._wheelie_ground(held)
        elif self.state is State.FALLING:
            self._fall_to_ground()
        elif self.state is State.CRASHING:
            self._tumble_on()

    def _fall_to_ground(self) -> None:
        for cell in (self.probes.below_left, self.probes.below):
            if cell.solid:
                self._snap(cell.direction)
                self.state = State.CRASHING
                return

    def _tumble_on(self) -> None:
        """A tumble follows the ground under it, and stops when all of it is level."""
        probes = self.probes
        if not (probes.below_left.solid or probes.below.solid):
            self._crash()
            return
        third = probes.third
        if third.solid:
            direction = third.direction
            if direction <= QUADRANT:
                direction += DIRECTIONS
            if self.direction % DIRECTIONS:
                self.tumble_from = self.direction
                if direction % DIRECTIONS == 0 and not self.tumble_from & DIRECTIONS:
                    direction = 0
                self.direction = direction
                self._snap(direction % DIRECTIONS)
                return
        elif self.tumble_air:
            self.tumble_air -= 1
            return
        self._settle()

    def _settle(self) -> None:
        """Down on the ground, if everything under the tumble is level."""
        probes = self.probes
        for cell in (probes.below_left, probes.below):
            if not cell.solid or cell.direction:
                return
        if self.direction not in (0, TUMBLE_LEVEL):
            return
        self.thrown_back = bool(self.direction & DIRECTIONS)
        self._snap(self.direction % DIRECTIONS)
        self.state = State.DOWN
        self.down_timer = DOWN_TICKS
        self.cues.append(Cue.CRASH)

    def _down(self) -> None:
        """One tick of the 57 a crashed bike spends down, by the timer."""
        self.down_timer -= 1
        t = self.down_timer
        back = self.thrown_back
        if t == 0:
            self.magnitude = 0
            self.state = State.STOPPED
            self.direction = self.attitude = 0
            self.y &= Y_ON_GRID
        elif t >= DOWN_TICKS - THROWN_OFF:
            self._come_off()
            self.attitude = POSE_OFF[not back]
            self.saved = (self.y, self.x >> PIXEL)
        elif t >= DOWN_TICKS - THROWN_OFF - THROW_STEPS:
            dy, dx = self.ground.throw(t - (DOWN_TICKS - THROWN_OFF - THROW_STEPS))
            self.y = (self.y + dy) & WORD
            self._move_px(dx if back else -dx)
            self.attitude = POSE_FLYING[not back]
        elif t >= LANDED_FROM:
            self.attitude = POSE_FLYING[not back]
        elif t >= CRAWL_FROM:
            self.attitude = POSE_SITTING[not back]
        elif t >= REMOUNT_FROM:
            self.attitude = POSE_CRAWLING[not back] + (1 if t & CRAWL_BLINK else 0)
            self._move_px(1 if back else -1)
        elif t >= READY_FROM:
            self.attitude = POSE_REMOUNT
            self.rider_off = False
            self.y = self.saved[0]
            self.x = (self.x & BYTE) | (self.saved[1] & WORD) << PIXEL
        elif t >= STANDING_FROM:
            self.attitude = POSE_READY

    def _come_off(self) -> None:
        """The rider off the bike: and the player loses what was picked up."""
        self.rider_off = True
        if self.player:
            self.jet = self.no_slope = False
            self.minis = 0
            self.speed.cap = self.rules.cap

    def _move_px(self, dx: int) -> None:
        """Move x by whole pixels, as the down animation does: the fraction stays."""
        pixel = ((self.x >> PIXEL) + dx) & WORD
        self.x = (self.x & BYTE) | pixel << PIXEL

    def _wheelie_ground(self, held: int) -> None:
        """A wheelie's ground check -- which runs on the very tick riding starts
        one: the third probe on solid ends the wheelie there, taking the tile's
        direction; nothing under the second is a take-off; nose up past 2, the
        first attitude probe on solid ends it too."""
        probes = self.probes
        if probes.third.solid:
            self.direction = self.attitude = probes.third.direction
            self.state = State.RIDING
        elif not probes.second.solid:
            self._take_off(held)
        elif self.attitude >= WHEELIE_GROUND and probes.attitude_first.solid:
            self.direction = self.attitude = probes.attitude_first.direction
            self.state = State.RIDING

    def _land(self) -> None:
        probes = self.probes
        for above in (probes.above, probes.at):
            if above.solid and above.direction in HEAD_FIRST:
                self._crash()
                return
        for touching in (probes.attitude_second, probes.attitude_first, probes.third):
            if touching.solid:
                break
        else:
            return
        surface = touching.direction
        landed = (not self.checks_landing or self.auto is not Auto.NONE
                  or flight.lands(self.attitude, surface,
                                  self.rules.land_behind, self.rules.land_ahead))
        if not landed:
            self._crash()
            return
        self.direction = self.attitude = surface
        self._snap(surface)
        self.state = State.RIDING

    def _ride(self, held: int) -> None:
        if self._finishing() or self._on_a_rock():
            return
        third = self.probes.third
        climbing_a_wall = QUADRANT <= self.direction < HALF_TURN
        if third.solid and not (climbing_a_wall and third.direction < QUADRANT):
            self.direction = self.attitude = third.direction
            self._snap(third.direction)
            return
        if self._leaves_the_ground():
            self._take_off(held)

    def _finishing(self) -> bool:
        """Past the take-over, low enough on the right column: the celebration."""
        if (self.auto >= Auto.RIDING and self.px[1] >= FINISH_Y
                and (self.x >> FINISH_SHIFT) & FINISH_MASK == 0):
            self.state = State.FINISHED
            return True
        return False

    def _on_a_rock(self) -> bool:
        """A rock under a level bike: the player tumbles, and the computer's bike
        rides over it as up a 45."""
        if self.direction != 0 or not self.ground.is_rock(self.probes.at_tile):
            return False
        if self.player:
            self.tumble_air = ROCK_TUMBLE_AIR
            self._tumble(TUMBLE_LEVEL)
        else:
            self.direction = UP_45
        return True

    def _leaves_the_ground(self) -> bool:
        """With nothing under the probes that hold it: level, the second; on the
        45 up, nothing beside the third; anywhere else, the first and second."""
        probes = self.probes
        if self.direction == 0:
            return not probes.second.solid
        if self.direction == UP_45 and probes.beside_third.solid:
            return False
        return not (probes.first.solid or probes.second.solid)

    def _snap(self, direction: int) -> None:
        """On the level, the right-hand wall and the ceiling: onto the tile grid,
        and nothing across it."""
        if direction < SNAP_LEVEL or direction == CEILING:
            lift = CEILING_LIFT if direction == CEILING else 0
            pixel = (((self.y >> PIXEL) + lift) & GRID) & BYTE
            self.y = pixel << PIXEL | (self.y & BYTE)
            self.vy = 0
        elif direction == WALL_RIGHT:
            pixel = (self.x >> PIXEL) & GRID & BYTE
            self.x = (self.x & ~(BYTE << PIXEL)) | pixel << PIXEL
            self.vx = 0
            self.wall_snapped = True

    def _crash(self) -> None:
        """Into a crash, chosen by the two cells under the bike."""
        below_left, below = self.probes.below_left, self.probes.below
        if below_left.solid and below_left.direction != DIRECTIONS - 1 \
                and below_left.direction & NOT_LEVEL:
            self._tumble(below_left.direction)
        elif not below_left.solid or not below.solid:
            self._fall()
        elif below.direction == DIRECTIONS - 1 or not below.direction & NOT_LEVEL:
            self.state = State.DOWN
            self.down_timer = DOWN_TICKS
            self.thrown_back = False
            self.cues.append(Cue.CRASH)
        else:
            self._tumble(below.direction)

    def _fall(self) -> None:
        self.state = State.FALLING
        self.direction = STRAIGHT_DOWN
        self.vx, self.vy = 0, FALL_SPEED
        self.cues.append(Cue.CRASH)

    def _tumble(self, direction: int) -> None:
        """A tumble, heading the way the tile under it slopes -- a climb as its
        direction plus a full turn, which is how a tumble tells the two apart."""
        if direction != TUMBLE_LEVEL and direction % DIRECTIONS and direction <= QUADRANT:
            direction += DIRECTIONS
        self.direction = self.tumble_from = direction
        grid = self.probes.below_left if self.probes.below_left.solid else self.probes.below
        self._snap(grid.direction)
        self.state = State.CRASHING

    def _take_off(self, held: int) -> None:
        """Into the air, with a class for the jump: fast or not, Up held or not."""
        self.state = State.AIR
        if self.auto >= Auto.RIDING:
            self.jump_class = AUTO_CLASS
        else:
            self.jump_class = ((FAST_CLASS if self.speed.index >= FAST else 0)
                               + (UP_CLASS if held & UP else 0))
        self.hang = HANG_PER_CLASS * self.jump_class
        self.speed.nitro_timer = 0
        self.air_nitro_window = 1


#: Each state's own step, as `Bike._state_step` runs it.
STATE_STEPS = {
    State.STOPPED: Bike._stopped,
    State.RIDING: Bike._riding,
    State.AIR: Bike._fly,
    State.WHEELIE: Bike._wheelie,
    State.FALLING: Bike._nothing,
    State.CRASHING: Bike._tumbling,
    State.FINISHED: Bike._celebrating,
    State.DOWN: Bike._lying,
    State.COUNTDOWN: Bike._idling,
}
