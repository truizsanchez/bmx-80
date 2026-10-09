"""A race's sound, played: the mixer's clips on Pyxel's four channels.

`game/rom/mixer.py` says what each of the Game Boy's channels should be playing;
this plays it on the Pyxel channel of the same number. A clip reaches Pyxel the
one way Pyxel takes samples, as a WAV file, written into a directory of its own
that goes when the race does -- a sound out of the player's cartridge is never
written anywhere that stays.

`prime` writes them all before the race, which is the point: a clip first wanted
mid-race is a stall the player hears. `_sound` stays lazy behind it.

**Without a cartridge** there are no clips: `OwnAudio` plays this game's own
effects (`game/sfx.py`) on Pyxel's synthesizer, and answers the same calls, so
the window drives either one the same way.
"""

import shutil
import tempfile
import wave
from collections.abc import Iterable

import pyxel

from game import sfx
from game.engine.rules import Cue
from game.rom import apu
from game.rom import mixer as original
from game.rom.mixer import Key, Mixer, Play

#: Pyxel's channel volume for a clip. Its own, an eighth, is for its synth; a clip
#: is already at the chip's level, a quarter of full scale a channel.
GAIN = 1.0


class Audio:
    """A mixer, heard."""

    def __init__(self, mixer: Mixer) -> None:
        self.mixer = mixer
        self._folder = tempfile.mkdtemp(prefix="bmx-80-sound-")
        self._sounds: dict[Key, pyxel.Sound] = {}
        for channel in range(len(pyxel.channels)):
            pyxel.channels[channel].gain = GAIN

    def prime(self, keys: "Iterable[Key] | None" = None) -> None:
        """Every clip on disk and in Pyxel's hands before it is wanted.

        The rendering is the mixer's bank's, and is paid once a session; this is
        the rest of it -- a WAV written and a `pyxel.Sound` built, milliseconds
        for the lot -- and past it `_sound` never renders anything again.

        With no keys named it is the whole bank, which is what a race wants. A
        screen between races wants the handful it can make and nothing else
        (`Clips.screen_keys`): writing the race's three hundred clips for it
        would be work nobody ever hears.
        """
        for key in self.mixer.clips.keys() if keys is None else keys:
            self._sound(key)

    def start(self) -> None:
        self.mixer.start()
        self._play(self.mixer.changes())

    def play(self, sound: int) -> None:
        """A sound asked for outright, or 0, which is silence: what a screen
        between races has where a race has `start` and `cue`."""
        self.mixer.play(sound)
        self._play(self.mixer.changes())

    def cue(self, cues: list[Cue], revs: int, hurrying: bool = False) -> None:
        self.mixer.cue(cues, revs, hurrying)

    def pause(self, paused: bool) -> None:
        self.mixer.pause(paused)
        self._play(self.mixer.changes())

    def tick(self) -> None:
        self._play(self.mixer.tick())

    def close(self) -> None:
        pyxel.stop()
        shutil.rmtree(self._folder, ignore_errors=True)

    def _play(self, plays: list[Play]) -> None:
        for play in plays:
            if play.key is None:
                pyxel.stop(play.channel)
            else:
                pyxel.play(play.channel, self._sound(play.key), sec=play.offset, loop=play.loop)

    def _sound(self, key: Key) -> pyxel.Sound:
        if key not in self._sounds:
            path = "%s/%s_%d_%d.wav" % ((self._folder,) + key)
            with wave.open(path, "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(apu.RATE)
                out.writeframes(self.mixer.clip(key).tobytes())
            sound = pyxel.Sound()
            sound.pcm(path)
            self._sounds[key] = sound
        return self._sounds[key]


#: The screens ask for the original's sounds by the original's numbers; these
#: are the ones this game has one of its own for. Anything else -- the course
#: select's tune above all -- is silence, there being no music without a
#: cartridge.
SCREEN_SOUNDS = {original.CURSOR: sfx.CURSOR, original.CONFIRM: sfx.CONFIRM,
                 original.RESULTS_MUSIC: sfx.RESULTS, original.RECORD_MUSIC: sfx.RECORD,
                 original.GAMEOVER_MUSIC: sfx.GAMEOVER}
#: The number the screens ask for silence by.
SILENCE = 0


def _built(effect: sfx.Effect) -> pyxel.Sound:
    sound = pyxel.Sound()
    sound.set(effect.notes, effect.tones, effect.volumes, effect.effects, effect.speed)
    return sound


class OwnAudio:
    """This game's own sound, for a race or a screen with no cartridge.

    The calls are `Audio`'s, so the window needs to know nothing about which it
    has: `cue` is where a race's sounds come from, `play` a screen's.
    """

    def __init__(self) -> None:
        self._cues = {cue: _built(effect) for cue, effect in sfx.CUES.items()}
        self._screens = {name: _built(effect) for name, effect in sfx.SCREENS.items()}
        self._engines: dict[int, pyxel.Sound] = {}
        self._pitch: int | None = None
        self._revs = 0
        #: Whether the engine is heard: from the green to the line.
        self.running = False
        self.paused = False
        for channel in range(len(pyxel.channels)):
            pyxel.channels[channel].gain = GAIN / 4

    def prime(self, keys: "Iterable[Key] | None" = None) -> None:
        """Nothing to render: the synthesizer plays what it is handed."""

    def start(self) -> None:
        self.running = True
        self._engine()

    def play(self, sound: int) -> None:
        if sound == SILENCE:
            pyxel.stop()
            return
        name = SCREEN_SOUNDS.get(sound)
        if name is not None:
            pyxel.play(sfx.JINGLE_CHANNEL, self._screens[name])

    def cue(self, cues: list[Cue], revs: int, hurrying: bool = False) -> None:
        self._revs = revs
        for cue in cues:
            if cue is Cue.FINISH:
                # Past the line the engine is the game's and not the player's:
                # it goes quiet under the finish.
                self.running = False
                pyxel.stop(sfx.ENGINE_CHANNEL)
                self._pitch = None
            channel = sfx.REPEAT_CHANNEL if cue in sfx.REPEATING else sfx.EFFECT_CHANNEL
            pyxel.play(channel, self._cues[cue])
        self._engine()

    def pause(self, paused: bool) -> None:
        self.paused = paused
        if paused:
            pyxel.stop()
            self._pitch = None
        else:
            self._engine()

    def tick(self) -> None:
        """Nothing to step: Pyxel keeps the time."""

    def close(self) -> None:
        pyxel.stop()

    def _engine(self) -> None:
        """The engine's note where the revs put it, replayed only when it moves."""
        if not self.running or self.paused:
            return
        pitch = sfx.engine_pitch(self._revs)
        if pitch == self._pitch:
            return
        if pitch not in self._engines:
            self._engines[pitch] = _built(sfx.engine(pitch))
        self._pitch = pitch
        pyxel.play(sfx.ENGINE_CHANNEL, self._engines[pitch], loop=True)


#: Either voice, as the window holds it.
Voice = Audio | OwnAudio
