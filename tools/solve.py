"""Can a course be ridden under a ruleset, and how fast: a search over the pad.

A pilot with rules of its own -- hold the throttle, wheelie at a rock -- answers
"does *this pilot* finish", and on the original's courses a pilot that simple
stops at the first wall it cannot read. What a mode needs to know is whether the
course can be finished at all under its rules, and in how long, so this does
not pilot: it **searches**. The engine is integers and has no window, so a race
is a value that can be copied and stepped down every branch.

The search is a beam, synchronous in time: every candidate has ridden the same
number of iterations, so the one furthest along is the one ahead in the race.
Each round every candidate is copied once per button combination in `ACTIONS`,
each copy holds that combination for `block` iterations, and the `width` best
are kept -- at most one per 16 px cell of the map and state, so the beam does
not spend itself on one line. The first round in which a candidate reaches the
take-over line gives the finish; a beam that stops getting further for
`STALL` rounds has found where the course cannot be passed.

It is a lower bound on what a person needs, not a model of one: the search is a
perfect player with a coarse thumb. `fragility` asks the other half -- how much
a late or early thumb costs -- from the line the search found.

    python tools/solve.py 1 2 3             # courses 1-3 out of maps/, classic rules
    python tools/solve.py --rom <gb> 1      # the cartridge's course 1
    python tools/solve.py --cap 111 --step 4 1   # under another ruleset
"""

import argparse
import copy
import multiprocessing
import os
import sys
from dataclasses import dataclass, field
from typing import Iterator, NamedTuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.engine.bike import Bike  # noqa: E402
from game.engine.rules import CLASSIC, Auto, Ruleset, State
from game.engine.original import LEFT, NITRO, RIGHT, THROTTLE, UP
from game.engine.run import TIME_UP, Run
from game.engine.original import COUNTDOWN, NO_LIMIT
from game.engine.terrain import Ground, Probed, Tiles  # noqa: E402
from game.engine.terrain import Hit  # noqa: E402

#: What a thumb can hold: the throttle alone and with each direction, Up with a
#: nose, a nitro, and nothing -- a coast, and a way to arrive later.
ACTIONS = (
    THROTTLE,
    THROTTLE | UP,
    THROTTLE | LEFT,
    THROTTLE | RIGHT,
    THROTTLE | UP | LEFT,
    THROTTLE | UP | RIGHT,
    THROTTLE | NITRO,
    0,
)
#: Nitros in hand beyond this many are worth nothing more to the search.
HOARD = 4
#: Rounds without the beam's furthest getting further before it gives up.
STALL = 120
#: The map, as the engine addresses it.
ROWS, COLS = 16, 256
#: States in which the bike is not being ridden.
CRASHES = (State.FALLING, State.CRASHING, State.DOWN)


class Overlay:
    """A course with the cells a race has changed kept on the side.

    Taking a crate writes the map, and so does the lap line; each branch of the
    search needs its own map, and copying 4096 cells a branch would be most of
    the search. So the course is shared and each branch keeps only what it
    wrote. Everything else is the course's.
    """

    def __init__(self, base: Ground, goal: "dict[tuple[int, int], int] | None" = None) -> None:
        self.base = base
        self.cells: dict[tuple[int, int], int] = {}
        self._goal = goal if goal is not None else _goal_of(base)

    def clone(self) -> "Overlay":
        other = Overlay.__new__(Overlay)
        other.base, other._goal, other.cells = self.base, self._goal, dict(self.cells)
        return other

    def metatile(self, row: int, col: int) -> int:
        if self.cells and row >= 0:
            got = self.cells.get((row % ROWS, col % COLS))
            if got is not None:
                return got
        return self.base.metatile(row, col)

    def tiles(self, metatile: int) -> Tiles:
        return self.base.tiles(metatile)

    def collision(self, tile: int) -> Hit:
        return self.base.collision(tile)

    def is_rock(self, tile: int) -> bool:
        return self.base.is_rock(tile)

    def probes(self, direction: int) -> Probed:
        return self.base.probes(direction)

    def items(self) -> "list[tuple[int, int, int]]":
        return list(self.base.items())

    def teleports(self) -> "list[tuple[int, int, int]]":
        return list(self.base.teleports())

    def put(self, row: int, col: int, metatile: int) -> None:
        self.cells[(row % ROWS, col % COLS)] = metatile

    def goal(self) -> None:
        self.cells.update(self._goal)

    def throw(self, step: int) -> tuple[int, int]:
        return self.base.throw(step)


def _goal_of(base: Ground) -> "dict[tuple[int, int], int]":
    """What putting the sign up writes, found by doing it to a copy."""
    scratch = copy.deepcopy(base)
    scratch.goal()
    return {(row, col): scratch.metatile(row, col)
            for row in range(ROWS) for col in range(COLS)
            if scratch.metatile(row, col) != base.metatile(row, col)}


def clone(run: Run) -> Run:
    """A race to step down one branch: everything copied but the course.

    By hand, field by field, because it is most of what the search spends:
    `copy.deepcopy` takes twice as long as the four iterations it is copied
    for. `test_solve` holds it to deepcopy's answer.
    """
    ground = run.ground
    assert isinstance(ground, Overlay) and run.rival is None
    other = copy.copy(run)
    other.ground = ground.clone()
    other.bike = _bike(run.bike, other.ground)
    other.camera = copy.copy(run.camera)
    other.items = [copy.copy(item) for item in run.items]
    other.cues = list(run.cues)
    other.flash = copy.copy(run.flash)
    return other


def _bike(bike: Bike, ground: Ground) -> Bike:
    other = copy.copy(bike)
    other.ground = ground
    other.speed = copy.copy(bike.speed)
    other.trail = list(bike.trail)
    other.cues = list(bike.cues)
    return other


class Frame(NamedTuple):
    """Where the bike was after one iteration."""

    x: int
    y: int
    state: State
    direction: int
    attitude: int
    speed: int


@dataclass
class Result:
    """What the search found."""

    #: Whether it reached the take-over line, and the race's clock there,
    #: in the original's hundredths -- two an iteration.
    finished: bool
    elapsed: int
    #: The furthest the bike got, in pixels.
    reached: int
    #: The pad, an iteration at a time, from the first after the countdown.
    pad: list[int] = field(default_factory=list)

    @property
    def iterations(self) -> int:
        return self.elapsed // 2


@dataclass
class _Node:
    run: Run
    parent: "_Node | None"
    action: int


def start(course: Ground, rules: Ruleset = CLASSIC, limit: int = NO_LIMIT) -> Run:
    """A race on `course`, through its countdown with the throttle held."""
    run = Run(course if isinstance(course, Overlay) else Overlay(course), limit=limit,
              rules=rules)
    for _ in range(COUNTDOWN):
        run.step(THROTTLE)
    return run


def _over(run: Run) -> bool:
    return run.bike.auto >= Auto.RIDING


def _score(run: Run, limited: bool, horizon: int, nitro: int) -> int:
    """Where the bike will be `horizon` iterations on at the speed it has now,
    in 1/256 px: further along *and faster* is ahead.

    A nitro in hand is worth `nitro` pixels, up to `HOARD` of them. Without it
    the beam spends every nitro the moment one gains a pixel, and arrives at a
    wall that only a nitro climbs with none: course4 cannot be passed that way.
    With a clock to beat, time left counts as the ground it would cover --
    about three pixels an iteration, two hundredths each."""
    bike = run.bike
    return (bike.x + bike.vx * horizon + min(bike.speed.nitros, HOARD) * nitro * 256
            + (run.left * 3 * 128 if limited else 0))


def solve(course: Ground, rules: Ruleset = CLASSIC, limit: int = NO_LIMIT, width: int = 48,
          block: int = 8, horizon: int = 16, nitro: int = 64, most: int = 30000,
          run: "Run | None" = None) -> Result:
    """The fastest finish the beam finds, or how far it got -- from the start,
    or from `run` when one is given."""
    limited = limit != NO_LIMIT
    beam = [_Node(run if run is not None else start(course, rules, limit), None, THROTTLE)]
    furthest, stalled, ridden = 0, 0, 0
    while beam and ridden < most:
        ridden += block
        children, finished = _expand(beam, block, limited, horizon, nitro)
        if finished:
            best = min(finished, key=lambda n: n.run.elapsed)
            return Result(True, best.run.elapsed, best.run.bike.x >> 8, _pad(best, block))
        beam = _prune(children, width)
        ahead = max((n.run.bike.x >> 8 for n in beam), default=0)
        if ahead > furthest:
            furthest, stalled = ahead, 0
        else:
            stalled += 1
            if stalled >= STALL:
                break
    best_node = max(beam, key=lambda n: n.run.bike.x) if beam else None
    return Result(False, best_node.run.elapsed if best_node else 0, furthest,
                  _pad(best_node, block) if best_node else [])


def _expand(beam: "list[_Node]", block: int, limited: bool, horizon: int,
            nitro: int) -> "tuple[list[tuple[int, _Node]], list[_Node]]":
    """Every node of the beam ridden `block` iterations on each action: the
    ones still racing, scored, and the ones that reached the line."""
    children: list[tuple[int, _Node]] = []
    finished: list[_Node] = []
    for node in beam:
        for action in ACTIONS:
            run = clone(node.run)
            for _ in range(block):
                run.step(action)
                if run.over or _over(run):
                    break
            child = _Node(run, node, action)
            if _over(run) or run.over == "finished":
                finished.append(child)
            elif run.over != TIME_UP:
                children.append((_score(run, limited, horizon, nitro), child))
    return children, finished


def _prune(children: "list[tuple[int, _Node]]", width: int) -> "list[_Node]":
    """The best `width` of them, and only one of any that are in the same place
    at the same speed."""
    children.sort(key=lambda sc: -sc[0])
    seen: set[tuple[int, int, bool, int]] = set()
    beam = []
    for _, child in children:
        bike = child.run.bike
        key = (bike.x >> 12, bike.y >> 12, bike.state in CRASHES, bike.speed.index >> 4)
        if key in seen:
            continue
        seen.add(key)
        beam.append(child)
        if len(beam) == width:
            break
    return beam


def _pad(node: "_Node | None", block: int) -> list[int]:
    actions: list[int] = []
    while node is not None and node.parent is not None:
        actions.append(node.action)
        node = node.parent
    return [a for a in reversed(actions) for _ in range(block)]


def replay(course: Ground, pad: "list[int]", rules: Ruleset = CLASSIC,
           limit: int = NO_LIMIT) -> Iterator[tuple[Run, Frame]]:
    """The race a pad rides, an iteration at a time."""
    run = start(course, rules, limit)
    for held in pad:
        run.step(held)
        bike = run.bike
        yield run, Frame(bike.x >> 8, bike.y >> 8, bike.state, bike.direction,
                         bike.attitude, bike.speed.index)
        if run.over or _over(run):
            return


#: How far a thumb is moved either way, in iterations, and how long after it a
#: crash is blamed on it.
SHIFTS = 3
BLAME = 160
#: A crash this close to one the line has is that one, come a little early or late.
SAME_CRASH = 8


class Edge(NamedTuple):
    """A moment the line changes what it holds, and how much slack it has."""

    #: The iteration, and where the bike was then.
    at: int
    x: int
    #: How many iterations early or late the change can come, every one of
    #: them either way, without a crash the line did not have: 0 is a change
    #: that must be exact to the iteration.
    slack: int


def fragility(course: Ground, pad: "list[int]", rules: Ruleset = CLASSIC,
              limit: int = NO_LIMIT) -> "list[Edge]":
    """How exact the line in `pad` has to be ridden, a change at a time.

    A search is a perfect thumb; a person is not, and what makes a course hard
    to a person is how many moments on it must be hit to the iteration. So every
    change of buttons on the line is moved one, two and three iterations early
    and late, the race ridden on `BLAME` iterations from there, and the change
    has as much slack as the largest move that crashes in none of them where
    the line itself did not. In milliseconds that is `slack * 1000 / rate`, and
    the rate is the mode's -- which is how a faster clock shows up here.
    """
    run = start(course, rules, limit)
    saved = [clone(run)]
    frames = []
    for held in pad:
        run.step(held)
        saved.append(clone(run))
        frames.append(run.bike.state in CRASHES)
    crashed = [i for i, down in enumerate(frames) if down and (i == 0 or not frames[i - 1])]
    edges = []
    for at in range(1, len(pad)):
        if pad[at] == pad[at - 1]:
            continue
        slack = 0
        for move in range(1, SHIFTS + 1):
            if any(_crashes(saved, pad, crashed, at, shift) for shift in (-move, move)):
                break
            slack = move
        edges.append(Edge(at, saved[at].bike.x >> 8, slack))
    return edges


def _crashes(saved: "list[Run]", pad: "list[int]", crashed: "list[int]", at: int,
             shift: int) -> bool:
    """Whether the change at `at`, moved by `shift`, crashes where the line did not."""
    begin = max(0, min(at, at + shift))
    moved = _moved(pad, at, shift, begin)
    run = clone(saved[begin])
    theirs = {i for i in crashed if begin <= i < begin + len(moved)}
    down = False
    for i, held in enumerate(moved, begin):
        run.step(held)
        now = run.bike.state in CRASHES
        if now and not down and not any(abs(i - c) <= SAME_CRASH for c in theirs):
            return True
        down = now
        if run.over or _over(run):
            break
    return False


def _moved(pad: "list[int]", at: int, shift: int, begin: int) -> "list[int]":
    """The pad from `begin`, with the change at `at` come `shift` iterations early
    (negative) or late."""
    moved = list(pad[begin:at + BLAME])
    if shift < 0:
        for i in range(at + shift, at):
            if i >= begin:
                moved[i - begin] = pad[at]
    else:
        for i in range(at, min(at + shift, len(pad))):
            moved[i - begin] = pad[at - 1]
    return moved


def _course(number: int, rom: "str | None") -> tuple[Ground, tuple[int, int, int]]:
    """A course by number, and its three clocks in hundredths."""
    if rom:
        from game.rom.cartridge import Cartridge
        from game.rom.course import Course as RomCourse
        with open(rom, "rb") as f:
            cartridge = Cartridge(f.read())
        clocks = (cartridge.limit(number, 0), cartridge.limit(number, 1), cartridge.limit(number, 2))
        return RomCourse(cartridge, number), clocks
    from maps import read
    course = read.course(os.path.join(read.COURSE_DIR, "course%d.json" % number))
    a, b, c = (round(seconds * 100) for seconds in course.limits)
    return course, (a, b, c)


#: What a level is called, and no level at all: the clock left out.
LEVELS = ("easy", "bumpy", "crazy")
FREE = -1


class Config(NamedTuple):
    """How one search is run: see `solve`."""

    width: int = 48
    block: int = 8
    horizon: int = 16
    nitro: int = 64


#: The searches a course is given. **One beam is chaotic**: moving a nitro's
#: worth from 32 to 64 pixels finishes one course and traps the beam on another
#: -- a wall only a saved nitro climbs, a pit only a spent one clears. So a
#: course is searched every one of these ways; any finish proves it can be
#: finished, the fastest is the bound, and how many of them finish says how
#: narrow it is to find.
PORTFOLIO = tuple(Config(48, block, horizon, nitro)
                  for block in (4, 8) for horizon in (0, 16, 32) for nitro in (16, 32, 64, 128))


class Job(NamedTuple):
    number: int
    level: int
    rom: "str | None"
    rules: Ruleset
    config: Config


def run_job(job: Job) -> tuple[Job, Result]:
    course, clocks = _course(job.number, job.rom)
    limit = NO_LIMIT if job.level == FREE else clocks[job.level]
    width, block, horizon, nitro = job.config
    return job, solve(course, job.rules, limit, width=width, block=block, horizon=horizon,
                      nitro=nitro)


def search(numbers: "list[int]", levels: "list[int]", rules: Ruleset = CLASSIC,
           rom: "str | None" = None, configs: "tuple[Config, ...]" = PORTFOLIO,
           jobs: int = 0) -> "dict[tuple[int, int], list[tuple[Config, Result]]]":
    """Every course at every level, searched every way in `configs`, in parallel."""
    work = [Job(n, level, rom, rules, config)
            for n in numbers for level in levels for config in configs]
    found: dict[tuple[int, int], list[tuple[Config, Result]]] = {}
    with multiprocessing.Pool(jobs or os.cpu_count() or 1) as pool:
        for job, result in pool.imap_unordered(run_job, work):
            found.setdefault((job.number, job.level), []).append((job.config, result))
    return found


def best(results: "list[tuple[Config, Result]]") -> "tuple[Config, Result]":
    """The fastest finish, or else the furthest reach."""
    return min(results, key=lambda cr: (not cr[1].finished, cr[1].elapsed if cr[1].finished
                                        else -cr[1].reached))


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("courses", nargs="+", type=int)
    parser.add_argument("--rom")
    parser.add_argument("--levels", default="free",
                        help="comma list of free, easy, bumpy, crazy")
    parser.add_argument("--cap", type=int, default=CLASSIC.cap)
    parser.add_argument("--cap-s", type=int, default=CLASSIC.cap_s)
    parser.add_argument("--step", type=int, default=CLASSIC.index_step)
    parser.add_argument("--quick", action="store_true", help="one search, not the portfolio")
    parser.add_argument("--jobs", type=int, default=0)
    args = parser.parse_args(argv)
    rules = Ruleset(cap=args.cap, cap_s=max(args.cap_s, args.cap), index_step=args.step)
    levels = [FREE if name == "free" else LEVELS.index(name) for name in args.levels.split(",")]
    configs = (Config(),) if args.quick else PORTFOLIO
    found = search(args.courses, levels, rules, args.rom, configs, args.jobs)
    for (number, level), results in sorted(found.items()):
        config, result = best(results)
        name = "free" if level == FREE else LEVELS[level]
        done = sum(r.finished for _, r in results)
        clock = "" if level == FREE else " clock %5d" % _course(number, args.rom)[1][level]
        if result.finished:
            print("course%d %-5s finished %5d%s  (%d/%d searches finish; best %s)" % (
                number, name, result.elapsed, clock, done, len(results), tuple(config)))
        else:
            print("course%d %-5s STUCK at x=%d%s  (0/%d)" % (
                number, name, result.reached, clock, len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
