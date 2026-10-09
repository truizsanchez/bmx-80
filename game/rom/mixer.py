"""What a race sounds like, out of the cartridge: which clip each channel plays.

The race says *when* (`rules.Cue`) and how fast the engine turns (`Run.revs`);
the original's own driver (`sound.py`), run live at 64 ticks a second, decides
*what* -- which request a slot takes and which it refuses for its priority, when
a sound ends, and who holds each of the Game Boy's four channels:

- **pulse 1**: an effect, else the engine;
- **pulse 2**: an effect, else the tune;
- **wave**: the tune, and the wave half of the countdown's beeps;
- **noise**: the effects' noise.

What plays is not the live driver's output but a **clip**: each sound rendered
once, alone, through `apu.py`, one clip per channel it uses, and started on its
channel when the live driver starts it there -- at the offset the live one has
reached, so a channel given back picks up where its sound is. **The engine** is
the exception, because its pitch follows the race: a loop two ticks long, the
two notes the original alternates, rendered for each value of `revs` it reaches.

**A tune has no end**, so it is two clips: an entrance, played once, and a loop
played for ever after, and where one gives way to the other is found by playing
the tune rather than written down (`Clips.music`). Eight courses share four
tunes, each on pulse 2 and the wave. Anything a paused game does but the pause's
own sound is silence.

The clips are a **bank** (`Clips`), rendered before the race rather than during
it and kept for every race after: rendering one costs tens of milliseconds, and
a course is not part of a key -- what a course chooses is which tune it starts,
and a tune is a key of its own.
"""

import hashlib
import json
import marshal
import os
import sys
from array import array
from dataclasses import dataclass, fields
from typing import Any

from game.engine.rules import Cue
from game.rom import apu
from game.rom.cartridge import Cartridge
from game.rom.course import COUNT
from game.rom.sound import (COURSE_MUSIC, DRUM, ENGINE, MUSIC_PULSE, MUSIC_PULSE_2,
                            MUSIC_WAVE, PAUSE, Driver, Slot)

#: The sound the original plays for each cue.
CUES = {Cue.COUNT: 0x10, Cue.GO: 0x11, Cue.NITRO: 0x0A, Cue.JET: 0x0B, Cue.EMPTY: 0x0C,
        Cue.PICKUP: 0x0D, Cue.TIME: 0x0E, Cue.SECRET: 0x0F, Cue.SAND: 0x13,
        Cue.TUMBLE: 0x14, Cue.CRASH: 0x16, Cue.FINISH: 0x18}
#: From this sound on, the sounds are music.
MUSIC = 0x19
#: The sounds the screens between races make: the cursor walking the ways to
#: play, and the button that settles one.
CURSOR, CONFIRM = 0x15, 0x17
SCREEN_EFFECTS = (CURSOR, CONFIRM)
#: ...and their music. The tune belongs to the screen a course is chosen on and
#: not to the title, which is silent; the results have two, and which of them
#: plays is whether the race just ridden beat the course record; the last ends a
#: race the clock ran out on. **None of them is in a table** -- the cartridge
#: lists a tune per course and nothing else -- so these four are named here,
#: read out of the code that asks for them.
SELECT_MUSIC, GAMEOVER_MUSIC = 0x19, 0x1C
RESULTS_MUSIC, RECORD_MUSIC = 0x1A, 0x1B
SCREEN_TUNES = (SELECT_MUSIC, RESULTS_MUSIC, RECORD_MUSIC, GAMEOVER_MUSIC)
#: The two names a tune's entrance and loop go under: at the tempo a race runs
#: at, and at the one it runs at with under ten seconds left. **A clip cannot
#: be played faster** -- neither Pyxel nor a WAV has a rate to turn -- so a
#: course's tune is rendered twice and the pair is chosen by the clock.
STEADY, HURRIED = ("music", "loop"), ("hurry", "hurryloop")
#: Which pair a name belongs to, and whether that pair is the hurried one.
PACE = {name: (pair, pair is HURRIED) for pair in (STEADY, HURRIED) for name in pair}
#: The slots a tune is played on.
MUSIC_SLOTS = (MUSIC_PULSE, MUSIC_PULSE_2, MUSIC_WAVE, DRUM)
#: Each channel's slots, the first that is playing holding it.
CHANNELS = ((0, 3), (1, 4), (5,), (2,))
#: Each channel's registers: from, and to but not including.
REGISTERS = ((0xFF10, 0xFF15), (0xFF15, 0xFF1A), (0xFF1A, 0xFF1F), (0xFF1F, 0xFF24))
WAVE_RAM = range(0xFF30, 0xFF40)
#: ...and the one register that is nobody's channel and everybody's: which side
#: each channel goes to.
NR51 = apu.NR51
#: A clip is rendered until its sound ends, or this long.
LONGEST = apu.TICKS * 30
#: The engine's loop: past its first ticks, two of them.
ENGINE_WARM, ENGINE_LOOP = 2, 2
#: The engine's pitch is a byte, and every value of it is a clip of its own.
REVS = 256
#: The course a clip is rendered on. Any of them: what a course changes is which
#: tune it starts, and a tune is a clip of its own under its own number.
ANY_COURSE = 1
#: A tune is looked at for this long to find where it comes back to. The longest
#: of the four takes 77 seconds to get round once.
TUNE = apu.TICKS * 120
#: A music slot's whole state bar the two counters that only ever rise: what
#: tells one moment of a tune from the same moment a loop later.
MOMENT = tuple(f.name for f in fields(Slot) if f.name not in ("ticks", "start"))
#: The first line of a bank written to disk, and the only version of the format.
BANK = b"bmx-80 sound bank 1\n"
#: The modules that decide what a sample is: a bank is this code's or it is not.
RENDERS = ("game.rom.apu", "game.rom.sound", __name__)

#: What a clip is: a sound on a channel, or the engine at a speed.
Key = tuple[str, int, int]


@dataclass(frozen=True, slots=True)
class Play:
    """Start `key` on `channel`, `offset` seconds in; or, with no key, stop it."""

    channel: int
    key: Key | None
    offset: float = 0.0
    loop: bool = False


class Clips:
    """The bank: every clip a race can ask for, rendered once and kept.

    A key is a sound and the channel it is heard on, the engine at a pitch, or
    a tune's entrance or its loop -- **and never the course**. What a course
    chooses is which tune it starts, and that tune is a key of its own, so the
    bank outlives a race and a second race renders nothing.

    `prime` renders the lot up front, which is the point of the class: rendering
    a clip costs tens of milliseconds and a tune costs seconds, and either first
    asked for mid-race is frames dropped where the player can hear them. It is
    paid once, with no window open. `clip` stays lazy underneath, so a key nobody
    foresaw is still heard rather than missing.
    """

    def __init__(self, cartridge: Cartridge, path: str | None = None) -> None:
        self.cartridge = cartridge
        #: Where the bank is kept between runs, if it is kept at all.
        self.path = path
        self._clips: dict[Key, "array[int]"] = {}
        self._keys: list[Key] | None = None
        self._screens: list[Key] | None = None
        self._music: dict[tuple[int, bool], tuple[int, int, bool]] = {}

    def keys(self) -> list[Key]:
        """Every key `Mixer.changes` can name.

        **Found by running the driver, not written down**: a sound is heard on
        the channels whose slots hold it, which is exactly what `Mixer._holder`
        looks at, so the bank cannot drift from the cartridge. Most sounds hold
        one channel and none holds four.
        """
        if self._keys is None:
            keys: list[Key] = []
            for sound in sorted(set(CUES.values()) | {PAUSE}):
                keys += [("sound", sound, channel) for channel in self._channels(sound)]
            for channel in self._channels(ENGINE):
                keys += [("engine", revs, channel) for revs in range(REVS)]
            for sound in self.tunes():
                keys += self._tune_keys(sound, STEADY)
                if self.hurries(sound):
                    keys += self._tune_keys(sound, HURRIED)
            keys += [key for key in self.screen_keys() if key not in keys]
            self._keys = keys
        return self._keys

    def screen_keys(self) -> list[Key]:
        """The part of the bank a screen between races can ask for.

        A screen wants its two tunes, the drums that go with them and the two
        noises a cursor makes, and nothing else -- the engine's two hundred and
        fifty-six pitches are a race's business -- so this is what the `Audio`
        that outlives a race is primed on.
        """
        if self._screens is None:
            keys: list[Key] = []
            for sound in SCREEN_EFFECTS:
                keys += [("sound", sound, channel) for channel in self._channels(sound)]
            for sound in SCREEN_TUNES:
                # Two tunes share a drum, so the second one's list is filtered:
                # a key twice in a bank is a clip rendered and written twice.
                keys += [key for key in self._tune_keys(sound, STEADY) if key not in keys]
            self._screens = keys
        return self._screens

    def hurries(self, sound: int) -> bool:
        """Whether the cartridge has a hurried tempo for this tune.

        The courses' four do; the two the screens play are outside the tables
        and keep whatever their own stream asks for, so they are rendered once.
        """
        return self.cartridge.tempo(sound, True) is not None

    def _tune_keys(self, sound: int, names: tuple[str, str]) -> list[Key]:
        """A tune's clips at one tempo: its entrance where it has one, its loop,
        and the drums, which are sounds of their own and not part of it.

        The drums are the same hits at either tempo -- a hit is a sound in its
        own right and the tempo does not reach it -- so they are named once, by
        the steady pass, and the hurried one adds none.
        """
        first, second = names
        entrance, _ = self.music(sound, names is HURRIED)
        keys: list[Key] = []
        for channel in self._channels(sound):
            if entrance:
                keys.append((first, sound, channel))
            keys.append((second, sound, channel))
        if names is HURRIED:
            return keys
        return keys + [key for key in self._drums(sound) if key not in keys]

    def clip(self, key: Key) -> "array[int]":
        """A clip's samples, rendered the first time it is asked for."""
        if key not in self._clips:
            kind, value, channel = key
            if kind in PACE:
                # One pass gives both, because the loop has to be rendered
                # through the entrance anyway for the chip to start where the
                # entrance left it.
                (first, second), hurried = PACE[kind]
                entrance, loop = self._render_tune(value, channel, hurried)
                self._clips[(first, value, channel)] = entrance
                self._clips[(second, value, channel)] = loop
            else:
                self._clips[key] = self._render(key)
        return self._clips[key]

    def prime(self) -> None:
        """Have every clip in hand, so that a race renders none.

        Read from `path` when what is there is this cartridge's and this code's,
        and otherwise rendered and written there for the next run. Rendering the
        lot is about four seconds; reading it back is a fortieth of one.
        """
        if self._read():
            return
        for key in self.keys():
            self.clip(key)
        self._write()

    def kept(self) -> bool:
        """Whether the bank on disk is one this run can use -- the header alone,
        so that a caller can say what is about to happen before it happens."""
        return self._stamped() is not None

    # -- the bank between runs ---------------------------------------------------
    #
    # One file: the line above, a line of JSON naming the cartridge, the code and
    # every clip with its length, and then the samples end to end in that order.
    # One file rather than a clip each because there is one thing to check, one
    # thing to write and one thing to throw away.

    def _stamp(self) -> dict[str, str]:
        """What a bank has to match to be this one: the cartridge it was read
        out of, and the code that turned it into samples.

        The code by its **compiled form and not its source**, because a built
        executable keeps no `.py` files on disk to read. A different Python
        marshals differently, which throws the bank away, which is right.
        """
        renderer = hashlib.sha1()
        for name in RENDERS:
            loader = sys.modules[name].__loader__
            renderer.update(marshal.dumps(loader.get_code(name)))    # type: ignore[union-attr]
        return {"cartridge": hashlib.sha1(self.cartridge.data).hexdigest(),
                "renderer": renderer.hexdigest(), "order": sys.byteorder}

    def _stamped(self) -> dict[str, Any] | None:
        """The header of the bank on disk, if there is one and it is ours.

        Anything wrong with the file -- absent, half-written, from another
        cartridge, from another build -- is the same answer: there is no bank,
        and one will be rendered. Nothing here is worth an exception in a
        player's face.
        """
        if self.path is None:
            return None
        try:
            with open(self.path, "rb") as bank:
                if bank.readline() != BANK:
                    return None
                header = json.loads(bank.readline())
            want = self._stamp()
            if any(header.get(field) != want[field] for field in want):
                return None
            return header if isinstance(header, dict) else None
        except (OSError, ValueError, AttributeError):
            return None

    def _read(self) -> bool:
        """Fill the bank from disk. False if there was nothing to fill it with."""
        header = self._stamped()
        if header is None:
            return False
        try:
            index = [(_key(entry), int(entry[3])) for entry in header["clips"]]
            with open(self.path or "", "rb") as bank:
                bank.readline()
                bank.readline()
                samples = bank.read()
            if len(samples) != 2 * sum(length for _, length in index):
                return False
            clips, at = {}, 0
            for key, length in index:
                clip = array("h")
                clip.frombytes(samples[at:at + 2 * length])
                at += 2 * length
                clips[key] = clip
        except (OSError, ValueError, TypeError, KeyError):
            return False
        self._clips = clips
        self._keys = [key for key, _ in index]
        return True

    def _write(self) -> None:
        """Keep the bank for the next run. A failure here costs the next run
        those few seconds again and nothing else, so it is swallowed as
        `records.save` swallows its own."""
        if self.path is None:
            return
        keys = self.keys()
        header = dict(self._stamp(), clips=[list(key) + [len(self._clips[key])] for key in keys])
        part = self.path + ".part"
        try:
            with open(part, "wb") as bank:
                bank.write(BANK)
                bank.write(json.dumps(header).encode() + b"\n")
                for key in keys:
                    bank.write(self._clips[key].tobytes())
            os.replace(part, self.path)
        except OSError:
            try:
                os.remove(part)
            except OSError:
                pass

    def tunes(self) -> list[int]:
        """The music a race can play: the tune each course starts when the last
        beep of the start ends. Eight courses and four tunes between them.

        A course with no tune names sound 0, which is no sound at all.
        """
        named = {self.cartridge.byte(COURSE_MUSIC + n) for n in range(COUNT)}
        return sorted(named - {0})

    def ends(self, sound: int, hurried: bool = False) -> bool:
        """Whether a tune stops of its own accord, which the four-slot ones do.

        A course's tune has no end and is played for ever; the one a race the
        clock ran out on gets is a jingle that finishes. The two look alike from
        outside -- entrance and loop -- so which is which is asked here rather
        than guessed from an entrance of nothing.
        """
        self.music(sound, hurried)
        return self._music[sound, hurried][2]

    def music(self, sound: int, hurried: bool = False) -> tuple[int, int]:
        """A tune's entrance and its loop, in ticks: it plays the first once and
        the second for ever after.

        **Found by playing it**, because a tune has no end and a clip rendered
        until one would be cut mid-phrase. The music slots are photographed every
        tick, the ticks where nothing moved are dropped -- those are the tempo's
        waits, and during one a slot does not change at all -- and the first
        moment that comes back names both: where the loop starts, and how long
        it is. No length is written down here and no stream is decoded.

        **The loop is a loop and not the tune.** The original never repeats
        itself exactly: the beat is eight bits, its phase moves on each time
        round, and the waits land a tick differently -- it takes about thirty
        turns to come back true, half an hour. What a repeated clip loses is
        that drift, a 64th of a second, and what it keeps is the tune.
        """
        if (sound, hurried) not in self._music:
            self._music[sound, hurried] = self._loop(sound, hurried)
        entrance, loop, _ = self._music[sound, hurried]
        return entrance, loop

    def _loop(self, sound: int, hurried: bool = False) -> tuple[int, int, bool]:
        driver = self._driver(sound, hurried)
        driver.request(sound)
        first: dict[tuple[tuple[object, ...], ...], int] = {}
        last: tuple[tuple[object, ...], ...] | None = None
        for tick in range(TUNE):
            if tick and not any(slot.sound == sound for slot in driver.slots):
                return 0, tick, True    # it ended: a tune that stops is its own loop
            moment = tuple(tuple(getattr(driver.slots[index], name) for name in MOMENT)
                           for index in MUSIC_SLOTS)
            if moment != last:
                if moment in first:
                    return first[moment], tick - first[moment], False
                first[moment] = tick
                last = moment
            driver.tick()
        return 0, TUNE, False   # a tune that does not come back in two minutes

    def _driver(self, sound: int, hurried: bool = False) -> Driver:
        """A driver paced as a race paces one: a course's tune at the tempo the
        original's table forces on it, and anything else at its stream's own."""
        driver = Driver(self.cartridge, ANY_COURSE)
        driver.forced = self.cartridge.tempo(sound, hurried)
        return driver

    def _drums(self, sound: int) -> list[Key]:
        """The drum hits a tune asks for, as keys of their own.

        **A four-slot tune's drums are not the tune.** The slot that carries
        them plays no note: each hit is a separate sound requested on the noise
        channel as the tune goes, so a bank holding the tune's three channels
        and nothing else would drop the drums and stall on the first bar of it.

        Which hits a tune uses is **found by playing it**, like the channels
        above and for the same reason: the cartridge's table of drums has seven
        entries and a tune uses two or three of them, and which ones is not
        written down anywhere.
        """
        mixer = Mixer(self.cartridge, ANY_COURSE, clips=self)
        mixer.driver.request(sound)
        keys = {play.key for play in mixer.changes() if play.key}
        entrance, loop = self.music(sound)
        for _ in range(entrance + loop):
            keys.update(play.key for play in mixer.tick() if play.key)
        return sorted(key for key in keys if key[0] == "sound")

    def _channels(self, sound: int) -> list[int]:
        """The channels a sound is heard on: the ones whose slots hold it at any
        point between the request and the end of it. The engine never ends, and
        is cut off by `LONGEST` like a clip."""
        driver = Driver(self.cartridge, ANY_COURSE)
        driver.request(sound)
        held: set[int] = set()
        for _ in range(LONGEST):
            holding = [index for index, slot in enumerate(driver.slots) if slot.sound == sound]
            if not holding:
                break
            held.update(channel for channel, slots in enumerate(CHANNELS)
                        if any(index in slots for index in holding))
            driver.tick()
        return sorted(held)

    def _render(self, key: Key) -> "array[int]":
        kind, value, channel = key
        driver = Driver(self.cartridge, ANY_COURSE)
        if kind == "engine":
            driver.engine = value
            driver.request(ENGINE)
            ticks = [driver.tick() for _ in range(ENGINE_WARM + ENGINE_LOOP)]
            chip = apu.Apu()
            apu.render([_on(channel, t) for t in ticks[:ENGINE_WARM]], apu=chip)
            return apu.render([_on(channel, t) for t in ticks[ENGINE_WARM:]], apu=chip)
        writes = [_on(channel, driver.request(value))]
        while len(writes) < LONGEST and any(s.sound == value for s in driver.slots):
            writes.append(_on(channel, driver.tick()))
        return apu.render(writes)

    def _render_tune(self, sound: int, channel: int,
                     hurried: bool = False) -> tuple["array[int]", "array[int]"]:
        """A tune's two clips, from one playing of it: the entrance and the loop."""
        entrance, loop = self.music(sound, hurried)
        driver = self._driver(sound, hurried)
        writes = [_on(channel, driver.request(sound))]
        while len(writes) < entrance + loop:
            writes.append(_on(channel, driver.tick()))
        chip = apu.Apu()
        return apu.render(writes[:entrance], apu=chip), apu.render(writes[entrance:], apu=chip)


class Mixer:
    """The live driver, and what each channel should be playing.

    The clips come from a `Clips` handed in, which is how one bank serves every
    race of a session; without one it keeps a bank of its own.
    """

    def __init__(self, cartridge: Cartridge, course: int = 1,
                 clips: "Clips | None" = None) -> None:
        self.cartridge = cartridge
        self.driver = Driver(cartridge, course)
        self.clips = clips if clips is not None else Clips(cartridge)
        #: Whether the clock is pressing. The original reads it every iteration
        #: and takes the music's tempo from the other of two tables while it
        #: holds; here it also chooses which of a tune's two clips is played.
        self.hurrying = False
        self._holding: list[tuple[int, ...] | None] = [None] * len(CHANNELS)
        #: The driver's ticks, and the one each *playing of a tune* began on --
        #: keyed by `_playing`, so a tune's voices share one clock however late
        #: a channel of it becomes audible. **A clip runs on
        #: this clock and `Slot.ticks` does not**: the tempo makes a music slot
        #: wait, and on a tick it waits the slot takes no step and its counter
        #: does not move -- so the slot's count falls behind the wall by however
        #: much the tune has waited. An effect slot never waits, which is why
        #: theirs is read straight off `Slot.ticks`.
        self._ticks = 0
        self._began: dict[int, int] = {}
        #: Which pair of clips each tune is being played from, so that a change
        #: of tempo can be seen and the tune kept where it stood across it.
        self._paced: dict[int, bool] = {}

    def start(self) -> None:
        """The race's engine, which runs from the countdown to the line."""
        self.driver.request(ENGINE)

    def play(self, sound: int) -> None:
        """Ask the driver for a sound outright, or for 0, which is silence.

        What a screen between races has, where a race has `start` and `cue`: its
        music and the noises its cursor makes are not cued by anything the
        engine does.
        """
        self.driver.request(sound)

    def cue(self, cues: list[Cue], revs: int, hurrying: bool = False) -> None:
        """An iteration's cues, the engine's speed after it, and the clock.

        The clock because the original reads it here too, in the same iteration
        and for the music: with under ten seconds left the tempo comes from the
        other of two tables.
        """
        for cue in cues:
            if cue is Cue.FINISH:
                self.driver.request(0)
            self.driver.request(CUES[cue])
        self.driver.engine = revs
        self.hurrying = hurrying

    def pause(self, paused: bool) -> None:
        self.driver.paused = paused
        if paused:
            self.driver.request(PAUSE)

    def tick(self) -> list[Play]:
        """One of the driver's 64 a second; what changes on the channels."""
        self._pace()
        self.driver.tick()
        self._ticks += 1
        return self.changes()

    def changes(self) -> list[Play]:
        """The channels whose holder is not what it was."""
        self._clock()
        plays = []
        for channel, slots in enumerate(CHANNELS):
            play, identity = self._holder(channel, slots)
            if identity != self._holding[channel]:
                self._holding[channel] = identity
                plays.append(play)
        return plays

    def _clock(self) -> None:
        """Start a tune's clock on the tick the **driver** started it.

        Not the tick a channel of it first becomes audible: an effect can be
        sitting on top of every voice a tune has when it begins -- the screen a
        course is chosen on asks for the button that settles the title and the
        tune in the same breath -- and a clock started when the mixer first saw
        the tune would then be late by however long the effect lasted, and the
        tune would play from its beginning after it rather than from where it
        had got to.
        """
        for slot in self.driver.slots:
            if slot.sound >= MUSIC:
                self._began.setdefault(self._playing(slot.sound), self._ticks)

    def _pace(self) -> None:
        """The tempo the original rewrites every iteration, out of one of two
        tables by whether the clock is pressing.

        A tune the tables do not cover -- the two the screens play -- keeps the
        one its own stream set, which is what the original's routine does with
        a tune outside its range.
        """
        playing = next((sound for sound in
                        (self.driver.slots[index].sound for index in MUSIC_SLOTS)
                        if sound >= MUSIC), 0)
        self.driver.forced = self.cartridge.tempo(playing, self.hurrying) if playing else None

    def _holder(self, channel: int, slots: tuple[int, ...]) -> tuple[Play, tuple[int, ...] | None]:
        """What should play on a channel, and what tells it from what was: which
        start of which slot -- or, for the engine, its speed."""
        driver = self.driver
        for index in slots:
            slot = driver.slots[index]
            if not slot.sound:
                continue
            if driver.paused and slot.sound != PAUSE:
                break
            if slot.sound == ENGINE:
                return Play(channel, ("engine", driver.engine, channel), loop=True), \
                    (-1, driver.engine)
            if slot.sound >= MUSIC:
                return self._tune(channel, index, slot)
            return Play(channel, ("sound", slot.sound, channel), slot.ticks / apu.TICKS), \
                (index, slot.start)
        return Play(channel, None), None

    def _tune(self, channel: int, index: int, slot: Slot) -> tuple[Play, tuple[int, ...]]:
        """A tune on a channel: its entrance once, and then its loop for ever.

        A tune runs on whatever the race does to it -- an effect taking pulse 2
        silences it and hands it back mid-phrase -- so what plays is wherever it
        has got to. **How far that is, is the driver's ticks since it began and
        not the slot's own count**, which the tempo's waits hold back. The last
        of the identity is which of the two clips it is, so the one Play that
        matters, the entrance giving way to the loop, is a change like any other.

        **The clock is the tune's and not the channel's** (`_playing`). All of a
        tune's voices start on one tick, and a channel that cannot be heard yet
        is still playing: an effect on top of it hides a voice without stopping
        it, and when the effect ends the original hands that voice back where
        the tune has got to. A clock per channel, started when the mixer first
        *saw* the voice, hands it back at the beginning instead -- and the voice
        then runs behind the others for as long as the tune lasts.
        """
        hurried = self.hurrying and self.clips.hurries(slot.sound)
        playing = self._playing(slot.sound)
        self._began.setdefault(playing, self._ticks)
        if self._paced.setdefault(playing, hurried) != hurried:
            self._carry(playing, slot.sound, hurried)
            self._paced[playing] = hurried
        first, second = HURRIED if hurried else STEADY
        entrance, loop = self.clips.music(slot.sound, hurried)
        # Wall-clock ticks since this tune began, not the slot's own: see `_ticks`.
        played = self._ticks - self._began[playing]
        if played < entrance:
            return Play(channel, (first, slot.sound, channel), played / apu.TICKS), \
                (index, slot.start, 0, hurried)
        repeats = not self.clips.ends(slot.sound, hurried)
        offset = (played - entrance) % loop if repeats else played - entrance
        return Play(channel, (second, slot.sound, channel), offset / apu.TICKS,
                    loop=repeats), (index, slot.start, 1, hurried)

    def _playing(self, sound: int) -> int:
        """Which playing of a tune this is: one number, shared by its voices.

        The driver starts all of a tune's slots in one call, so their `start`
        numbers are consecutive and the lowest of them names this playing --
        the same number from every channel of it, and a different one when the
        tune is started again.

        Every slot is looked at and not only the four a tune usually holds: a
        tune requested while those are busy lands where it can, and the caller
        is holding one of them either way.
        """
        return min(slot.start for slot in self.driver.slots if slot.sound == sound)

    def _carry(self, start: int, sound: int, hurried: bool) -> None:
        """Keep a tune where it stands when its tempo changes.

        **The original does not jump.** It rewrites the tempo and the stream
        goes on from the note it was on, only read faster. Two clips cannot do
        that, so the place in the tune is carried across as a fraction -- the
        two clips are the same music at two speeds, so the same fraction of
        either is the same bar -- and the clock the offset is counted from is
        moved to put the new clip there. Without this the music jumps to a
        different part of itself on the tenth second, which is the one moment
        of a race nobody is listening for a fault in the sound.
        """
        was, now = self.clips.music(sound, not hurried), self.clips.music(sound, hurried)
        played = self._ticks - self._began[start]
        if played < was[0]:
            ahead = round(played * now[0] / was[0]) if was[0] else 0
        else:
            ahead = now[0] + round((played - was[0]) % was[1] * now[1] / was[1])
        self._began[start] = self._ticks - ahead

    def clip(self, key: Key) -> "array[int]":
        """A clip's samples, out of the bank."""
        return self.clips.clip(key)


def _key(entry: Any) -> Key:
    """A key as a bank on disk writes it: a list of three, back to a tuple."""
    kind, value, channel = entry[:3]
    return str(kind), int(value), int(channel)


def _on(channel: int, writes: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The writes that reach one channel -- **and the panning, which reaches all
    four**.

    The panning register is not in any channel's window, and leaving it out of
    all of them meant every clip was rendered under the chip's default of both
    sides at once -- so a channel the cartridge sends nowhere was heard anyway.
    What a side is worth is the chip's business (`apu.render`, which folds
    rather than sums); whether the register arrives at all is this function's.
    """
    low, high = REGISTERS[channel]
    return [(r, v) for r, v in writes
            if low <= r < high or r == NR51 or (channel == 2 and r in WAVE_RAM)]
