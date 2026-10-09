"""What a race sounds like with no cartridge: this game's own effects, as data.

With a cartridge the sound is the original's, its driver run on its own data
(`game/rom/mixer.py`). Without one there is nothing to run, so these are written
here for Pyxel's own synthesizer: a note string, a tone, a volume and an effect
a note, and a speed -- `pyxel.Sound.set`'s five arguments, and nothing else.

**The same moments, not the same sounds.** What makes a sound is the race's own
`Cue` list, the one the cartridge's driver is handed, so a sound is heard on the
iteration the original would make one. What each sounds like is this game's.
There is no music: the effects, the engine, and a jingle for the screens that
end something.

**The engine** is one note, looped, pitched by `Run.revs` -- higher as the bike
winds up -- and put back on its channel only when the pitch moves, since a loop
restarted every iteration would be a buzz of its own.

Pyxel-free, so what plays when can be tested without a window;
`game/render/audio.py` is what hears it.
"""

from dataclasses import dataclass

from game.engine.rules import Cue


@dataclass(frozen=True)
class Effect:
    """One sound, as `pyxel.Sound.set` takes it."""

    notes: str
    tones: str
    volumes: str
    effects: str
    #: Pyxel's ticks a note, at 120 a second.
    speed: int


#: The channels: the engine's, a race's effects, the ones that repeat while a
#: thing lasts (sand, a tumble), and the jingles.
ENGINE_CHANNEL, EFFECT_CHANNEL, REPEAT_CHANNEL, JINGLE_CHANNEL = 0, 1, 2, 3

#: A sound for every cue the race makes.
CUES = {
    Cue.COUNT: Effect("a2", "s", "5", "f", 20),
    Cue.GO: Effect("a3", "s", "6", "f", 40),
    Cue.NITRO: Effect("c1d1e1f1g1a1b1c2", "n", "76655443", "nnnnnnnf", 3),
    Cue.JET: Effect("g1a1b1c2d2e2", "p", "665544", "nnnnnf", 3),
    Cue.EMPTY: Effect("c1c1", "p", "43", "nf", 6),
    Cue.PICKUP: Effect("c3e3g3", "s", "555", "nnf", 5),
    Cue.TIME: Effect("g3c4", "s", "56", "nf", 7),
    Cue.SECRET: Effect("c3e3g3c4e4g4", "s", "555555", "nnnnnf", 4),
    Cue.SAND: Effect("c1", "n", "2", "f", 3),
    Cue.TUMBLE: Effect("f1", "n", "4", "f", 4),
    Cue.CRASH: Effect("c2a1f1d1c1", "n", "76543", "nnnnf", 6),
    Cue.FINISH: Effect("c3e3g3c4", "s", "5556", "nnnf", 10),
}

#: Which of the cues repeat while a thing lasts, and so go on a channel of
#: their own rather than cutting off the one-off sounds.
REPEATING = frozenset((Cue.SAND, Cue.TUMBLE))

#: The screens' sounds, by name: the cursor, the button that settles a choice,
#: and the jingles that end a race -- a finish, a record, the clock run out.
CURSOR, CONFIRM, RESULTS, RECORD, GAMEOVER = (
    "cursor", "confirm", "results", "record", "gameover")
SCREENS = {
    CURSOR: Effect("c3", "s", "4", "f", 4),
    CONFIRM: Effect("e3a3", "s", "55", "nf", 5),
    RESULTS: Effect("c3e3g3e3g3c4", "s", "555556", "nnnnnf", 10),
    RECORD: Effect("c3e3g3c4g3c4e4", "s", "5555556", "nnnnnnf", 9),
    GAMEOVER: Effect("g2f2e2d2c2", "t", "66665", "nnnnf", 14),
}

#: The engine: a pulse, quiet, a note held a few ticks and looped.
ENGINE_TONE, ENGINE_VOLUME, ENGINE_SPEED = "p", "2", 4
#: Its pitch, as a note number (`c0` is 0): idling here, and a semitone higher
#: for every `REVS_A_STEP` of `revs`, up to `HIGHEST`.
IDLE, REVS_A_STEP, HIGHEST = 12, 8, 36

NAMES = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")


def note(number: int) -> str:
    """A note number as Pyxel writes it: 0 is `c0`, 13 is `c#1`."""
    octave, step = divmod(number, len(NAMES))
    return "%s%d" % (NAMES[step], octave)


def engine_pitch(revs: int) -> int:
    """The engine's note for how fast it turns."""
    return min(IDLE + max(revs, 0) // REVS_A_STEP, HIGHEST)


def engine(pitch: int) -> Effect:
    """The engine's loop at a pitch."""
    return Effect(note(pitch), ENGINE_TONE, ENGINE_VOLUME, "n", ENGINE_SPEED)
