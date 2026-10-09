"""The engine rides as it rode: every iteration of a few races, against a record.

Why this test: every other engine test pins one rule. Nothing pinned the whole
of it -- the order the rules run in, and what each hands the next -- so a change
meant to move code and not behaviour (a number out of a module and into a table,
a long function into short ones) could change a ride and pass. This one fails
on the first iteration that differs, and says which race and when.

The course is written here, not read from `maps/` (a map is content, meant to
be retuned; the engine is not): a lap of road with a jump, a steep ramp, sand,
rocks, every kind of crate and two stretches for the computer's bike to be put
back on. The pads are pseudo-random from fixed seeds, mostly throttle so the
races go somewhere, and each race has the computer's bike in it.

**When it fails**, the change either meant to change how the engine rides --
then say so in its PR and record again:

    python tests/test_engine_golden.py

-- or it did not, and the change is wrong. The record is a hash per stretch of
iterations, so a failure names the first stretch that went apart; the race can
be ridden again with `ride()` to see how.
"""

import hashlib
import json
import pathlib
import random
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from game.course import COLS, ROWS, Course, Tileset
from game.engine.original import DOWN, LEFT, NITRO, RIGHT, THROTTLE, UP
from game.engine.run import Run
from maps import read

RECORD = pathlib.Path(__file__).with_name("golden") / "engine.json"

#: How many iterations each race is ridden, and how many make one hash.
ITERATIONS = 4500
STRETCH = 100

#: (seed, level, clock in hundredths): one race each, the computer's bike in
#: every one. The first five finish; the last runs out of time.
RACES = [(1, 0, 60000), (2, 1, 60000), (3, 2, 60000), (4, 0, 60000), (5, 2, 60000),
         (6, 1, 2500)]

TILES = {
    "floor": {"solid": True, "dir": 0},
    "fill": {"solid": True, "dir": 0},
    "up": {"solid": True, "dir": 4},
    "down": {"solid": True, "dir": 28},
    "sand": {"solid": True, "soft": True},
    "stone": {"solid": True, "rock": True},
}
METATILES = {
    "road": ["sky", "sky", "floor", "floor"],
    "under": ["fill"] * 4,
    "beach": ["sky", "sky", "sand", "sand"],
    "boulder": ["sky", "sky", "stone", "stone"],
    "up_fill": ["up", "fill", "fill", "fill"], "up_tip": ["-", "-", "-", "up"],
    "down_fill": ["fill", "down", "fill", "fill"], "down_tip": ["-", "-", "down", "-"],
}
PIECES = {
    "ramp_up": [[".", ".", "up_tip"], [".", "up_tip", "up_fill"],
                ["up_tip", "up_fill", "under"], ["up_fill", "under", "under"]],
    "ramp_down": [["down_tip", ".", "."], ["down_fill", "down_tip", "."],
                  ["under", "down_fill", "down_tip"], ["under", "under", "down_fill"]],
    "table": [["under"] * 3] * 3,
}


def course() -> Course:
    floor = ROWS - 1
    stampings = [(floor, col, "road") for col in range(COLS)]
    # A jump over a gap: up, and down again six cells on.
    stampings += [(12, 30, "ramp_up"), (12, 38, "ramp_down")]
    # A table: up, three cells across the top, down.
    stampings += [(12, 70, "ramp_up"), (13, 73, "table"), (12, 76, "ramp_down")]
    stampings += [(12, col, "road") for col in (73, 74, 75)]
    stampings += [(floor, col, "beach") for col in range(100, 112)]
    stampings += [(floor, col, "boulder") for col in (130, 170, 171)]
    # Two ramps in a row, the second from the foot of the first.
    stampings += [(12, 190, "ramp_up"), (12, 194, "ramp_up"), (12, 198, "ramp_down")]
    items = [("s", 14, 20), ("n", 14, 50), ("t", 14, 90), ("r", 14, 120),
             ("j", 14, 150), ("mini", 14, 180), ("n", 11, 74)]
    teleports = [(2400, 3900, 224), (100, 2200, 224)]
    return Course(Tileset(TILES, METATILES), PIECES, read.tables(), stampings=stampings,
                  items=items, teleports=teleports)


#: What a thumb holds, and how often: the throttle most of the time.
HOLDS = [THROTTLE] * 6 + [THROTTLE | UP, THROTTLE | LEFT, THROTTLE | RIGHT,
                          THROTTLE | NITRO, THROTTLE | DOWN, 0, NITRO, UP | LEFT]


def _pad(seed: int) -> list[int]:
    chance = random.Random(seed)
    pad: list[int] = []
    while len(pad) < ITERATIONS:
        pad += [chance.choice(HOLDS)] * chance.randint(2, 24)
    return pad[:ITERATIONS]


def _bike(bike) -> tuple:
    return (bike.x, bike.y, bike.vx, bike.vy, int(bike.state), int(bike.auto),
            bike.direction, bike.attitude, bike.speed.index, bike.speed.nitros,
            bike.speed.cap)


def ride(seed: int, level: int, limit: int):
    """Each iteration of one race: what both bikes, the clocks and the sounds were."""
    run = Run(course(), limit=limit, rival=True, level=level)
    for held in _pad(seed):
        run.step(held)
        assert run.rival is not None
        yield (run.iterations, run.tick, run.elapsed, run.left, run.laps_left, run.over,
               _bike(run.bike), _bike(run.rival), [cue.value for cue in run.cues],
               [not item.there for item in run.items], run.camera.x, run.camera.y)


def hashes(seed: int, level: int, limit: int) -> list[str]:
    out, digest = [], hashlib.sha256()
    for n, frame in enumerate(ride(seed, level, limit), 1):
        digest.update(repr(frame).encode())
        if n % STRETCH == 0:
            out.append(digest.hexdigest()[:16])
            digest = hashlib.sha256()
    return out


def _key(seed: int, level: int, limit: int) -> str:
    return "seed %d, level %d, clock %d" % (seed, level, limit)


def test_the_engine_rides_every_race_as_it_did():
    record = json.loads(RECORD.read_text())
    assert sorted(record) == sorted(_key(*race) for race in RACES), \
        "the races changed: record again"
    for race in RACES:
        now, then = hashes(*race), record[_key(*race)]
        for stretch, (a, b) in enumerate(zip(now, then)):
            assert a == b, "%s went apart in iterations %d-%d" % (
                _key(*race), stretch * STRETCH, (stretch + 1) * STRETCH)
        assert len(now) == len(then)


def test_the_races_go_somewhere():
    """A record of bikes that never left the grid would pin nothing: between
    them the races have to crash, fly, take things, finish and run out of time."""
    states, taken, ends = set(), False, set()
    for race in RACES:
        for frame in ride(*race):
            states.add(frame[6][4])
            taken = taken or any(frame[9])
        ends.add(frame[5])
    assert taken, "nothing was ever picked up"
    assert len(states) >= 6, "only states %s were ever seen" % sorted(states)
    assert ends == {"finished", "time up"}, ends


if __name__ == "__main__":
    RECORD.parent.mkdir(exist_ok=True)
    RECORD.write_text(json.dumps({_key(*race): hashes(*race) for race in RACES}, indent=1)
                      + "\n")
    print("recorded", RECORD)
