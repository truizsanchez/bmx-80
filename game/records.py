"""Best times and best scores, and the one file this game writes.

**They survive the power being switched off**, and that is a decision rather than
a default: a scoreboard held in memory is hardware apologising for itself, and a
record you cannot come back to tomorrow is a record nobody chases.

**A record is keyed by course *and* level**, because the three levels are three
different races -- the same ground against three different clocks -- and one
number over all of them would be the easy level's number for ever.

**Two axes, each keeping its own best.** A time and a score are two different
races over the same ground: the fast way round is the one that takes no jump it
does not have to, and points are only ever earned in the air. Pairing them --
keeping the score of the fastest run -- would leave the trick column reading
whatever the quick line happened to pass through, which is a readout of nothing.
So a run can improve one, the other, both, or neither.

Pyxel-free, like everything under `game/` that is not `render/`: this is a dict
and a file, and `tests/test_model_is_window_free.py` covers it.
"""

import json

from game import paths
from game.course import LEVEL_LETTERS

# Beside `editor.log`, which is the precedent: the repo is the game, and a file
# the game writes lives where the game does and is gitignored. Not a dot-file in
# the user's home -- there is one player and one checkout, and a path that
# depends on the platform is a path nobody can find when it goes wrong.
#
# **Which is `game/paths.user_dir` and not the repo**, because a shared build has
# no checkout: there the same sentence points at `bmx-80-data/` beside the
# executable. In a checkout it is the repo, unchanged.
PATH = paths.user_path("records.json")

# One course-and-level's record, `{TIME: seconds, SCORE: points}`, either half
# possibly absent -- and the whole scoreboard, `{course: {level letter: Entry}}`.
# A score is written as an int and read back as one; `float` here is only the
# wider of the two, so one alias can hold both halves.
Entry = dict[str, float]
Records = dict[str, dict[str, Entry]]


# The two things kept about a run, as they are keyed in the file. Short because
# they are written once per record and read by a person only when something has
# gone wrong.
TIME = "t"
SCORE = "s"


def load(path: str = PATH) -> Records:
    """`{course: {level: {TIME: seconds, SCORE: points}}}`, and an unreadable
    file is an empty one.

    **A bare number where the pair should be is read as a time**, which is what
    a scoreboard written before there were points looks like. Same argument as
    the rest of this function rather than a new one: what is understood is kept
    and what is not is dropped, and a player who has a file of times keeps them.

    Deliberately forgiving. This is a scoreboard: a corrupt or half-written file
    should cost the player their times, which is sad, and not the ability to
    start the game, which is a bug. Nothing else in this repo reads a file it
    would rather guess about -- a map that will not parse is an error, because a
    map that half-loads is a map you ride into a hole.
    """
    try:
        with open(path) as handle:
            found = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(found, dict):
        return {}
    records: Records = {}
    for course, times in found.items():
        if not isinstance(times, dict):
            continue
        kept: dict[str, Entry] = {}
        for letter, record in times.items():
            if letter not in LEVEL_LETTERS:
                continue
            entry = _entry(record)
            if entry:
                kept[letter] = entry
        if kept:
            records[course] = kept
    return records


def _entry(record: object) -> Entry:
    """One course-and-level's record, out of whatever the file had there.

    A number is a time, which is the old file. A dict is read field by field and
    a field that is not a number is simply not there -- so half a record is half
    a record rather than a reason to lose the rest of the scoreboard.
    """
    if isinstance(record, bool):
        return {}
    if isinstance(record, (int, float)):
        return {TIME: float(record)}
    if not isinstance(record, dict):
        return {}
    entry: Entry = {}
    if isinstance(record.get(TIME), (int, float)) and not isinstance(record.get(TIME), bool):
        entry[TIME] = float(record[TIME])
    if isinstance(record.get(SCORE), int) and not isinstance(record.get(SCORE), bool):
        entry[SCORE] = record[SCORE]
    return entry


def save(records: Records, path: str = PATH) -> bool:
    """Write, and say whether it worked rather than raising.

    Same argument as `load`: a read-only checkout is a reason not to keep the
    scoreboard, and not a reason for the run that just finished to end in a
    traceback.
    """
    try:
        with open(path, "w") as handle:
            json.dump(records, handle, indent=1, sort_keys=True)
    except OSError:
        return False
    return True


def best(records: Records, course: str, level: int) -> float | None:
    """The time to beat, or `None` where there is not one yet."""
    return records.get(course, {}).get(LEVEL_LETTERS[level], {}).get(TIME)


def best_score(records: Records, course: str, level: int) -> int:
    """The score to beat. **Zero rather than `None`**, unlike the time: a course
    nobody has finished has no time at all, and one nobody has done a trick on
    has a score, and it is nought."""
    return int(records.get(course, {}).get(LEVEL_LETTERS[level], {}).get(SCORE, 0))


def beats(records: Records, course: str, level: int, seconds: float) -> bool:
    """Whether `seconds` would be a new record. A first time always is."""
    standing = best(records, course, level)
    return standing is None or seconds < standing


def beats_score(records: Records, course: str, level: int, score: int) -> bool:
    """Whether `score` would be a new best. **A nought never is**, so a run that
    took no jump leaves the column alone instead of writing a zero into it."""
    return score > best_score(records, course, level)


def put(records: Records, course: str, level: int, seconds: float,
        score: int = 0) -> bool:
    """Record the run, each axis on its own. Returns whether either stuck.

    Independent because they are two races (see the module docstring): a slow
    run full of flips takes the score column and leaves the clock alone.

    Mutates rather than returning a new dict, because there is one scoreboard
    and the caller is holding it.
    """
    keep: Entry = {}
    if beats(records, course, level, seconds):
        keep[TIME] = float(seconds)
    if beats_score(records, course, level, score):
        keep[SCORE] = int(score)
    if not keep:
        # Nothing beaten, and nothing written: an entry made here for a run that
        # improved neither axis would put a course on the scoreboard with no
        # record in it.
        return False
    records.setdefault(course, {}).setdefault(LEVEL_LETTERS[level], {}).update(keep)
    return True


def clock(seconds: float | None) -> str:
    """`M:SS.t`, which is a record and not a countdown.

    The HUD prints `M:SS` at the line because that is what you were racing
    against; a scoreboard wants the tenth, because two runs of the same course
    land in the same second often enough to make a whole-second record useless.
    """
    if seconds is None:
        return "--:--"
    minutes, rest = divmod(float(seconds), 60.0)
    return "%d:%04.1f" % (minutes, rest)
