"""The original's sound: its driver, the chip, the mixer, and when a race asks.

No cartridge ships with this repo, so the driver runs here on a few bytes laid
out where the original keeps its sounds: a header, a stream of commands and a
note table. What these check is the rules -- a stream read to its note, a
priority refused, a channel handed back, a pulse at the pitch its register says.
That the rules are the original's, write for write over all its sounds, is
checked against recordings of it, where a cartridge exists.
"""

import json
from array import array

from game.engine.rules import Cue, State
from game.engine.original import THROTTLE
from game.engine.run import Run
from game.engine.original import BEEPS_AT, COUNTDOWN, GO_AT
from game.rom import apu
from game.rom.cartridge import Cartridge
from game.rom.course import COUNT
from game.rom.mixer import (
    CUES, GAMEOVER_MUSIC, RECORD_MUSIC, RESULTS_MUSIC, REVS, SELECT_MUSIC, Clips, Mixer)
from game.rom.cartridge import FIRST_TUNE, TEMPO, TEMPO_HURRIED
from game.rom.sound import (
    BASES, COURSE_MUSIC, DRUMS, ENGINE, NOTES, SOUNDS, Driver)

from tests.test_engine_bike import _floor, _solid_from

#: A 512 Hz note: `131072 / (2048 - 1792)`.
FREQUENCY = 1792
STREAM = 0x7010
#: A stream that never ends: a note, then a note jumped back to for ever.
TUNE_STREAM, TUNE_LOOP = 0x7020, 0x7027


#: The cue whose number the bank tests use, the game's own: a pickup.
PICKUP = CUES[Cue.PICKUP]


def _cartridge(length=16, fade_gate=0x00, also=(), tempo=0x00, paced=None):
    """Sound 1, an effect on pulse 1 at priority 4; sound 2, the same at priority
    2; sound 0x19, a tune on pulse 2. The effects' stream is the envelope, one
    note and the end; the tune's is the envelope, one note and a jump back to
    the note, so that it goes round for ever as the cartridge's own do.

    `also` gives more sounds the first one's header, for a test that needs the
    numbers the game asks for rather than 1 and 2. `paced` is `(steady,
    hurried)`: the tune goes under the first number a course can play and the
    two tempo tables are filled, which is what makes it a tune a race paces.
    """
    data = bytearray(0x8000)

    def word(at, value):
        data[at], data[at + 1] = value & 0xFF, value >> 8
    for sound, header in ((1, 0x7000), (2, 0x7004), (0x19, 0x7008)):
        word(SOUNDS + 2 * (sound - 1), header)
    for sound in also:
        word(SOUNDS + 2 * (sound - 1), 0x7000)
    for header, priority, which, stream in ((0x7000, 4, 0b1, STREAM),
                                           (0x7004, 2, 0b1, STREAM),
                                           (0x7008, 16, 0b10000, TUNE_STREAM)):
        data[header], data[header + 1] = priority, which
        word(header + 2, stream)
    # Every course plays the one tune, where the game looks up a course's music.
    data[COURSE_MUSIC:COURSE_MUSIC + COUNT] = bytes([0x19] * COUNT)
    if paced is not None:
        word(SOUNDS + 2 * (FIRST_TUNE - 1), 0x7008)     # the same tune, as a course's
        data[COURSE_MUSIC:COURSE_MUSIC + COUNT] = bytes([FIRST_TUNE] * COUNT)
        data[TEMPO], data[TEMPO_HURRIED] = paced
    data[BASES:BASES + 7] = bytes((0x00, 0x05, 0x0F, 0x00, 0x05, 0x0A, 0x0F))
    word(NOTES, FREQUENCY)
    # E0: a length, then volume 15 with duty 2 (50%), then the fade and gate;
    # a note of the first semitone, one length long; and the end.
    data[STREAM:STREAM + 6] = bytes((0xE0, length, 0x2F, fade_gate, 0x11, 0xFF))
    # The tune: an envelope, a tempo, a note, and then a note that FE FF jumps
    # back to instead of ending -- so the first note is the entrance and the
    # second is the loop, which is the shape the cartridge's own four have. A
    # `tempo` makes the music wait, as the cartridge's own do.
    data[TUNE_STREAM:TUNE_STREAM + 12] = bytes(
        (0xE0, length, 0x2F, fade_gate, 0xEE, tempo, 0x11, 0x11, 0xFE, 0xFF,
         TUNE_LOOP & 0xFF, TUNE_LOOP >> 8))
    return Cartridge(bytes(data), check=False)


#: The drum a four-slot tune hits, as a sound of its own.
BEEP = 0x02
DRUM_HIT = 3


def _four_slot_cartridge():
    """A cartridge with the two tunes a screen between races plays.

    `SELECT_MUSIC` is the shape the cartridge's own four-slot tunes have: a note
    on pulse 2 **and a drum slot that plays no note of its own** -- what it
    plays is a request for another sound, on the noise channel, which is the
    whole reason the drums need keys of their own. `GAMEOVER_MUSIC` is the other
    shape: a tune that ends rather than going round, and the results' two are
    that shape as well -- a fanfare is played once.
    """
    data = bytearray(0x8000)

    def word(at, value):
        data[at], data[at + 1] = value & 0xFF, value >> 8
    for sound, header in ((SELECT_MUSIC, 0x7100), (DRUM_HIT, 0x7108),
                          (GAMEOVER_MUSIC, 0x7110), (RESULTS_MUSIC, 0x7118),
                          (RECORD_MUSIC, 0x7160), (BEEP, 0x7168)):
        word(SOUNDS + 2 * (sound - 1), header)
    # The tune: pulse 2 and the drums. The drum hit: the noise slot, so it is
    # heard on a channel the tune itself never touches.
    data[0x7100], data[0x7101] = 16, 0b1010000
    word(0x7102, 0x7120)
    word(0x7104, 0x7130)
    data[0x7108], data[0x7109] = 8, 0b100
    word(0x710A, 0x7140)
    data[0x7110], data[0x7111] = 16, 0b10000
    word(0x7112, 0x7150)
    # The results' two: each a fanfare of one note that ends, on pulse 1, and
    # each its own stream so that neither can be mistaken for the other.
    data[0x7118], data[0x7119] = 16, 0b1
    word(0x711A, 0x7170)
    data[0x7160], data[0x7161] = 16, 0b1
    word(0x7162, 0x7180)
    # An effect on slot 1, which is the other slot of the channel the tune is
    # heard on: it takes the channel from the tune and hands it back.
    data[0x7168], data[0x7169] = 16, 0b10
    word(0x716A, 0x7190)
    data[DRUMS] = DRUM_HIT
    data[BASES:BASES + 7] = bytes((0x00, 0x05, 0x0F, 0x00, 0x05, 0x0A, 0x0F))
    word(NOTES, FREQUENCY)
    # A note and a note jumped back to for ever; a drum note likewise; the hit
    # itself; and a tune of one note that ends.
    data[0x7120:0x7120 + 10] = bytes((0xE0, 4, 0x2F, 0x00, 0x11, 0x11, 0xFE, 0xFF, 0x24, 0x71))
    data[0x7130:0x7130 + 7] = bytes((0xE7, 4, 0x11, 0xFE, 0xFF, 0x32, 0x71))
    data[0x7140:0x7140 + 6] = bytes((0xE0, 4, 0x2F, 0x00, 0x11, 0xFF))
    data[0x7150:0x7150 + 6] = bytes((0xE0, 4, 0x2F, 0x00, 0x11, 0xFF))
    data[0x7170:0x7170 + 6] = bytes((0xE0, 4, 0x2F, 0x00, 0x11, 0xFF))
    data[0x7180:0x7180 + 6] = bytes((0xE0, 4, 0x2F, 0x00, 0x12, 0xFF))
    # The effect: a few ticks of one note and then it is over.
    data[0x7190:0x7190 + 6] = bytes((0xE0, 4, 0x2F, 0x00, 0x13, 0xFF))
    return Cartridge(bytes(data), check=False)


def _run(driver, ticks):
    return [driver.tick() for _ in range(ticks)]


class _Counted(Clips):
    """A bank that counts what it renders, so that a test can say `nothing more`."""

    def __init__(self, cartridge, path=None):
        super().__init__(cartridge, path)
        self.renders = 0

    def _render(self, key):
        self.renders += 1
        return super()._render(key)

    def _render_tune(self, sound, channel, hurried=False):
        self.renders += 1
        return super()._render_tune(sound, channel, hurried)


def _bank():
    return _Counted(_cartridge(length=4, also=(PICKUP, ENGINE)))


def test_the_chip_makes_the_same_samples_it_made_before():
    """Why this test, and why a number nobody can read.

    What it pins is not that these are the **right** samples -- the chip is
    checked against the original's own output elsewhere, where a cartridge
    exists -- but that they are **the same** ones. The render loop is where the
    whole of a bank's cost lives, so it gets rewritten for speed; every such
    rewrite has to come out bit for bit what it went in as, and a clip that
    drifted by a rounding would sound right and hash differently for ever after.

    Four channels at once, on and panned, with an envelope falling and a sweep
    walking pulse one, so a rewrite that dropped any of those moves the number.
    """
    import hashlib

    chip = apu.Apu()
    for register, value in ((0xFF25, 0xFF),
                            (0xFF11, 0x80), (0xFF12, 0xF3), (0xFF13, 0x00), (0xFF14, 0x86),
                            (0xFF16, 0x40), (0xFF17, 0xA1), (0xFF18, 0x55), (0xFF19, 0x87),
                            (0xFF20, 0x20), (0xFF21, 0x60), (0xFF22, 0x30), (0xFF23, 0x80)):
        chip.write(register, value)
    samples = chip.render(2000)
    assert len(samples) == 2000
    assert hashlib.sha1(samples.tobytes()).hexdigest() == \
        "a2c789d935abfcafce3dea2fe878d6888b20d921"


def test_a_note_writes_duty_frequency_volume_and_a_trigger():
    """The request takes the channel's panning; the first tick reads the stream
    to its note and sets the channel going; the end silences it."""
    driver = Driver(_cartridge(length=4))
    assert driver.request(1) == [(0xFF10, 0x08), (0xFF25, 0x11)]
    first = driver.tick()
    assert (0xFF11, 0x20) in first, "duty 2 in the top bits"
    assert (0xFF13, FREQUENCY & 0xFF) in first and (0xFF14, FREQUENCY >> 8) in first
    assert first[-2:] == [(0xFF12, 0xF0), (0xFF14, 0x87)], "volume 15, then the trigger"
    rest = _run(driver, 4)
    assert (0xFF10, 0x00) in rest[-1] and not driver.slots[0].sound


def test_a_slot_keeps_what_it_plays_against_a_lower_priority():
    driver = Driver(_cartridge())
    driver.request(1)
    driver.request(2)
    assert driver.slots[0].sound == 1
    driver.request(1)
    assert driver.slots[0].start == 2, "the same priority starts it again"


def test_the_chip_plays_the_pitch_the_register_says():
    """A 50% pulse at register 1792 is 512 Hz: counted from its rising edges."""
    driver = Driver(_cartridge())
    writes = [driver.request(1)] + _run(driver, 16)
    samples = apu.render(writes)
    held = samples[apu.RATE // 64 * 2:apu.RATE // 64 * 14]
    rises = sum(1 for a, b in zip(held, held[1:]) if a < 0 <= b)
    seconds = len(held) / apu.RATE
    assert abs(rises / seconds - 512) < 8
    assert isinstance(samples, array) and max(samples) > 1000


def test_the_mixer_starts_a_clip_and_stops_it_when_the_sound_ends():
    mixer = Mixer(_cartridge(length=4))
    mixer.driver.request(1)
    plays = mixer.tick()
    assert [(p.channel, p.key) for p in plays] == [(0, ("sound", 1, 0))]
    assert len(mixer.clip(("sound", 1, 0))) > 0
    later = [p for _ in range(8) for p in mixer.tick()]
    assert [(p.channel, p.key) for p in later] == [(0, None)]


def test_a_pause_silences_everything_but_its_own_sound():
    mixer = Mixer(_cartridge())
    mixer.driver.request(1)
    mixer.tick()
    mixer.pause(True)
    assert [(p.channel, p.key) for p in mixer.changes()] == [(0, None)]


def test_a_tune_plays_its_entrance_once_and_then_its_loop():
    """Why this test: a tune has no end, so it cannot be a clip the way an effect
    is -- rendered until it stops. It is rendered as far as the point it comes
    back to, and from there on the same stretch goes round. What the mixer has
    to do is hand the channel from the one clip to the other at that point and
    never again, and `loop` has to be set or the tune would play once and stop.
    """
    mixer = Mixer(_cartridge(length=4))
    assert mixer.clips.music(0x19) == (5, 4), "a note in, then a note round"
    mixer.driver.request(0x19)
    heard = [(p.key, p.loop) for _ in range(12) for p in mixer.tick()]
    assert heard == [(("music", 0x19, 1), False), (("loop", 0x19, 1), True)], \
        "the entrance, then the loop, and then nothing more to say"


def test_a_tune_is_timed_by_the_clock_its_clip_runs_on():
    """Why this test: a clip runs on the driver's ticks, a 64th of a second each
    whatever the music is doing, and `Slot.ticks` does not. **The tempo makes a
    music slot wait**, and on a tick it waits the slot takes no step and its
    counter does not move -- so the slot falls behind the wall by however long
    the tune has waited.

    Timing the entrance by the slot's own count handed over to the loop five
    seconds late on the cartridge's first course, and the tune fell silent in
    between: the entrance clip had run out and nothing had replaced it.
    """
    mixer = Mixer(_cartridge(length=4, tempo=0x80))
    entrance, _ = mixer.clips.music(0x19)
    mixer.driver.request(0x19)
    mixer.changes()                     # noticed on the tick it starts, as in a race
    over = []
    for tick in range(1, 4 * entrance):
        for play in mixer.tick():
            if play.key and play.key[0] == "loop":
                over.append((tick, mixer.driver.slots[4].ticks))
    assert [tick for tick, _ in over] == [entrance], \
        "the loop takes over on the clock the entrance ran out on"
    assert over[0][1] < entrance, \
        "and the slot's own count is behind by then, which is the whole of the trap"


def test_an_effect_hands_the_tune_back_where_it_has_got_to():
    """Why this test: an effect on pulse 2 silences the tune and gives the
    channel back mid-phrase -- the tune never stopped running underneath. The
    offset is what makes that true, and for the loop it is the offset *round*
    the loop, which is the one place `slot.ticks` has to be taken modulo
    something. Off by a loop and the tune restarts every time a sound is made.
    """
    mixer = Mixer(_cartridge(length=4))
    entrance, loop = mixer.clips.music(0x19)
    mixer.driver.request(0x19)
    mixer.changes()
    played = 0
    while played < entrance + loop + 3:     # past the first time round
        mixer.tick()
        played += 1
    play, _ = mixer._holder(1, (1, 4))
    assert play.key == ("loop", 0x19, 1) and play.loop
    assert play.offset == ((played - entrance) % loop) / apu.TICKS, \
        "where it has got to round the loop, not how far it has come altogether"


# -- the bank ------------------------------------------------------------------------


def test_the_bank_names_only_the_channels_a_sound_is_heard_on():
    """The keys are found by running the driver, not written down, because what
    `Mixer._holder` can name is what the driver's slots say and nothing else. On
    the cartridge that is 19 keys against the 52 a sound-by-channel table would
    have; the other 33 render to silence and are never asked for.
    """
    bank = _bank()
    keys = bank.keys()
    assert ("sound", PICKUP, 0) in keys, "the pickup is on pulse 1, where its slot is"
    assert [k for k in keys if k[0] == "sound"] == [("sound", PICKUP, 0)], \
        "and on no other channel, and no sound this cartridge does not have"
    assert [k for k in keys if k[0] == "engine"] == [("engine", r, 0) for r in range(REVS)]
    assert [k for k in keys if k[0] in ("music", "loop")] == \
        [("music", 0x19, 1), ("loop", 0x19, 1)], "the tune, in two clips, on pulse 2"


def test_mono_folds_the_sides_rather_than_averaging_them():
    """Why this test: summing the two sides is the arithmetic a Game Boy's own
    speaker does, and it is the wrong answer here. The cartridge uses the
    panning as an arrangement -- the music between races throws the whole of
    itself left and then right, a phrase at a time -- and a sum turns that
    bounce into a dip to three fifths of the volume, measured, which is what
    nobody hears: nobody listens to this through one speaker.

    So a channel sent to either side keeps its own level, and **a channel sent
    to neither is not heard**, which is the part a render blind to the register
    got wrong. The fold is a choice about the output; `stereo` is the chip.

    The stereo half is here for the day something can play it. Nothing does --
    Pyxel mixes its channels to mono -- so what it has to prove is only that the
    chip is not the thing in the way.
    """
    def samples(pan, stereo=False):
        writes = [[(0xFF25, pan), (0xFF11, 0x80), (0xFF12, 0xF0),
                   (0xFF13, 0x00), (0xFF14, 0x87)]]
        return apu.render(writes + [[] for _ in range(8)], apu=apu.Apu(), stereo=stereo)

    both, one = samples(0xFF), samples(0x10)          # 0x10: pulse 1 to the left
    assert max(both) > 0 and max(one) == max(both), "one side keeps its own level"
    assert set(samples(0x00)) == {0}, "and a channel sent to neither is not heard"
    pairs = samples(0x10, stereo=True)
    assert max(pairs[0::2]) == max(both), "kept apart, that side is the whole of it"
    assert set(pairs[1::2]) == {0}, "and the other is silent"


def test_the_panning_reaches_every_channels_clip_and_nothing_elses():
    """Why this test: the writes are split per channel by a window of registers,
    and the panning is one register outside every window -- so the obvious
    filter drops it, which is exactly what happened. It is not a fifth channel:
    it says where the other four go, so it belongs in all of them.
    """
    from game.rom.mixer import NR51, _on

    writes = [(0xFF10, 1), (0xFF17, 2), (NR51, 0x42), (0xFF31, 3)]
    for channel in range(4):
        assert (NR51, 0x42) in _on(channel, writes)
    assert _on(0, writes) == [(0xFF10, 1), (NR51, 0x42)]
    assert _on(1, writes) == [(0xFF17, 2), (NR51, 0x42)]


def test_a_tunes_drums_are_clips_of_their_own_on_a_channel_the_tune_never_holds():
    """Why this test: a four-slot tune's drum slot plays no note. Each hit is a
    separate sound requested on the noise channel as the tune goes -- so a bank
    built from the channels the tune itself holds has every note of it and none
    of the drums, and the first bar of the screen stalls while they render. The
    hit is on a channel the tune never touches, which is what makes it easy to
    miss and what this pins.
    """
    clips = Clips(_four_slot_cartridge())
    tune = [key for key in clips.screen_keys() if key[1] == SELECT_MUSIC]
    assert [key[2] for key in tune] == [1, 1], "the tune is heard on pulse 2 alone"
    assert ("sound", DRUM_HIT, 3) in clips.screen_keys(), \
        "and its drum on the noise channel, which is not one of the tune's own"


def test_a_tune_that_ends_is_played_once_and_a_tune_that_does_not_is_looped():
    """Why this test: both shapes come out of `music` as an entrance and a loop,
    and a jingle's entrance is nothing -- so the two are told apart by asking,
    not by looking at the numbers. Get it wrong and the screen a race the clock
    ran out on ends on plays its four and a half seconds for ever.
    """
    clips = Clips(_four_slot_cartridge())
    assert clips.ends(GAMEOVER_MUSIC) and not clips.ends(SELECT_MUSIC)
    looped = {}
    for sound in (SELECT_MUSIC, GAMEOVER_MUSIC):
        mixer = Mixer(_four_slot_cartridge(), clips=clips)
        mixer.play(sound)
        plays = [play for play in mixer.changes() if play.key]
        plays += [play for _ in range(4) for play in mixer.tick() if play.key]
        looped[sound] = {play.loop for play in plays if play.key[0] == "loop"}
    assert looped[SELECT_MUSIC] == {True}
    assert looped[GAMEOVER_MUSIC] == {False}


def test_the_results_two_tunes_are_both_in_the_bank_and_are_not_each_other():
    """Why this test: the results play one of two tunes and which one is decided
    the moment the screen goes up, so **both have to have been rendered before
    the window opened** -- a bank with only the ordinary one would stall the
    screen on the race that earned the other. And they are different clips: a
    bank that named one twice would play the same fanfare either way, which is
    the bug that would look exactly like it working.
    """
    clips = Clips(_four_slot_cartridge())
    keys = clips.screen_keys()
    for sound in (RESULTS_MUSIC, RECORD_MUSIC):
        assert [key for key in keys if key[1] == sound], "rendered before the window"
    assert clips.ends(RESULTS_MUSIC) and clips.ends(RECORD_MUSIC), "a fanfare is played once"
    ordinary = [clips.clip(key) for key in keys if key[1] == RESULTS_MUSIC]
    record = [clips.clip(key) for key in keys if key[1] == RECORD_MUSIC]
    assert ordinary != record, "two tunes, not one under two names"


def test_a_race_paces_the_music_from_the_cartridges_table_and_not_the_stream():
    """Why this test: a course's tune sets a tempo of its own with `EE`, and on
    the cartridge that number is **not** the one the game plays it at -- the
    original rewrites the tempo every iteration out of a table and the stream's
    own is overruled for as long as the race runs. So a driver left to the
    stream plays the whole race a little off, on three of the four tunes, and
    nothing sounds wrong enough to notice.
    """
    cartridge = _cartridge(length=4, tempo=0x60, paced=(0x80, 0x20))
    assert cartridge.tempo(FIRST_TUNE) == 0x80
    assert cartridge.tempo(FIRST_TUNE, hurried=True) == 0x20
    assert cartridge.tempo(0x19) is None, "the screens' music is outside the tables"
    driver = Driver(cartridge)
    driver.forced = cartridge.tempo(FIRST_TUNE)
    driver.request(FIRST_TUNE)
    _run(driver, 20)
    assert driver.tempo == 0x80, "the stream asked for 0x60 and was overruled"


def test_a_clock_that_is_pressing_plays_the_tune_from_its_other_pair_of_clips():
    """Why this test: a clip cannot be played faster -- there is no rate to turn
    on a WAV or on Pyxel -- so the tempo the clock forces has to be baked in,
    which means a course's tune is two pairs of clips and not one. What is
    pinned is that the hurried pair is shorter, which is the whole of it being
    faster, and that the screens' music has no second pair: it is not in the
    tables and the original leaves it alone.
    """
    bank = Clips(_cartridge(length=4, tempo=0x60, paced=(0x80, 0x20)))
    assert bank.hurries(FIRST_TUNE) and not bank.hurries(0x19)
    steady, hurried = bank.music(FIRST_TUNE), bank.music(FIRST_TUNE, True)
    assert hurried[1] < steady[1], "the same music, fewer ticks: that is faster"
    kinds = [key[0] for key in bank.keys() if key[1] == FIRST_TUNE]
    assert kinds == ["music", "loop", "hurry", "hurryloop"]
    assert [key[0] for key in bank.keys() if key[1] == 0x19] == ["music", "loop"]


def test_the_tune_stays_where_it_stood_when_the_clock_starts_pressing():
    """Why this test: the original does not jump on the tenth second -- it reads
    the same stream faster and the music goes on from the note it was on. Two
    clips cannot do that by themselves, so the place in the tune is carried
    across as a fraction of the loop. Without it the music leaps to another bar
    of itself at the one moment of a race nobody is listening for a fault in
    the sound, and a test that only checked the clip changed would pass.
    """
    cartridge = _cartridge(length=32, tempo=0x60, paced=(0x80, 0x20))
    bank = Clips(cartridge)
    mixer = Mixer(cartridge, clips=bank)
    mixer.driver.request(FIRST_TUNE)
    mixer.changes()
    ticks = 300
    for _ in range(ticks):
        mixer.tick()
    mixer.changes()
    mixer.cue([], 0, hurrying=True)
    quick = [play for play in mixer.tick() if play.key]
    ticks += 1
    assert quick and {play.key[0] for play in quick} == {"hurryloop"}, \
        "the clip changes, because the pair does"
    entrance, loop = bank.music(FIRST_TUNE)
    fast_entrance, fast_loop = bank.music(FIRST_TUNE, True)
    was = (ticks - entrance) % loop / loop
    now = quick[0].offset * apu.TICKS / fast_loop
    assert abs(now - was) <= 1.0 / fast_loop, "the same bar, within a tick of it"
    naive = (ticks - fast_entrance) % fast_loop / fast_loop
    assert abs(naive - was) > 4.0 / fast_loop, \
        "and the clock it is counted from really did move: reading the new " \
        "clip off the old one lands somewhere else entirely"


def test_priming_the_bank_leaves_a_race_with_nothing_to_render():
    """Why this test: a clip rendered the first time it is wanted costs tens of
    milliseconds, which is frames dropped where the player can hear them. The
    bank exists to spend that before the race, so what it has to prove is that
    afterwards there is nothing left to spend.
    """
    bank = _bank()
    bank.prime()
    primed = bank.renders
    assert primed > REVS, "the engine alone is a clip for every pitch"
    for key in bank.keys():
        bank.clip(key)
    assert bank.renders == primed, "asked again, and it rendered nothing"


def test_one_bank_serves_every_course():
    """Why this test: the course is not part of a key. That holds because the
    music is the only thing a course changes and the music is left out -- on the
    cartridge every clip of course 1 is byte for byte course 5's. If the music
    ever arrives, a race will be heard playing another course's sound, and the
    sharing this asserts is where that starts.
    """
    bank = _bank()
    bank.prime()
    primed = bank.renders
    for course in (1, 5):
        mixer = Mixer(bank.cartridge, course, clips=bank)
        mixer.driver.request(PICKUP)
        mixer.tick()
        assert len(mixer.clip(("sound", PICKUP, 0))) > 0
    assert bank.renders == primed, "the second course rendered nothing of its own"


# -- the bank between runs -------------------------------------------------------------


def _kept(tmp_path):
    """A bank rendered and written to disk, and the file it went to."""
    path = str(tmp_path / "sound.bank")
    first = _Counted(_cartridge(length=4, also=(PICKUP, ENGINE)), path)
    first.prime()
    return first, path


def test_a_bank_kept_on_disk_is_read_back_and_not_rendered_again(tmp_path):
    """Why this test: rendering the bank is several seconds on the cartridge,
    and it is the same several seconds every time the game starts. Kept beside
    the game it is a fortieth of one. What has to hold is
    that what comes back is what went out -- every key, in order, sample for
    sample -- because nothing downstream would notice if it were not.
    """
    first, path = _kept(tmp_path)
    assert first.renders and first.kept(), "rendered once, and now there is a bank"
    second = _Counted(_cartridge(length=4, also=(PICKUP, ENGINE)), path)
    second.prime()
    assert second.renders == 0, "read, not rendered"
    assert second.keys() == first.keys()
    assert all(second.clip(key) == first.clip(key) for key in first.keys())


def test_a_bank_is_refused_unless_it_is_this_cartridge_and_this_code(tmp_path):
    """Why this test: a bank is samples, and there is nothing in a sample that
    says what it is. Read against another cartridge it would play another game's
    sound; read against changed code it would play what the code used to do --
    both silently and both for ever, because a bank that is accepted is never
    rendered again. Every way the file can be wrong has the one answer: there is
    no bank, and one is rendered.
    """
    first, path = _kept(tmp_path)
    assert Clips(_cartridge(length=8, also=(PICKUP, ENGINE)), path).kept() is False, \
        "another cartridge"

    def doctor(field):
        with open(path, "rb") as bank:
            line, header, rest = bank.readline(), json.loads(bank.readline()), bank.read()
        header[field] = "not what this run says"
        with open(path, "wb") as bank:
            bank.write(line + json.dumps(header).encode() + b"\n" + rest)

    for field in ("renderer", "order"):
        doctor(field)
        assert Clips(first.cartridge, path).kept() is False, field
        first._write()                          # put it back for the next one

    for junk in (b"", b"not a bank at all", open(path, "rb").read()[:1000]):
        with open(path, "wb") as bank:
            bank.write(junk)
        fresh = _Counted(first.cartridge, path)
        assert fresh.kept() is False
        fresh.prime()
        assert fresh.renders, "and it rendered rather than raising"


def test_a_bank_that_cannot_be_written_costs_the_next_run_and_nothing_else(tmp_path):
    """Why this test: the bank is a convenience, and a read-only directory or a
    full disk is not a reason a player cannot play. `records.save` swallows its
    own `OSError` for the same reason.
    """
    bank = _Counted(_cartridge(length=4, also=(PICKUP, ENGINE)),
                    str(tmp_path / "nowhere" / "sound.bank"))
    bank.prime()
    assert bank.renders and not bank.kept(), "played, and there is still no bank"


# -- when a race asks ----------------------------------------------------------------


def test_the_countdown_beeps_three_times_and_says_go():
    run = Run(_solid_from(_floor(0), 15))
    heard = []
    for iteration in range(1, COUNTDOWN + 1):
        run.step(0)
        heard += [(COUNTDOWN - iteration, cue) for cue in run.cues]
    assert heard == [(n, Cue.COUNT) for n in BEEPS_AT] + [(GO_AT, Cue.GO)]


def test_the_engine_revs_with_the_throttle_in_the_countdown():
    """Before the start the engine is pitched by the index itself; riding, by
    the curve's value for it."""
    run = Run(_solid_from(_floor(0), 15))
    for _ in range(10):
        run.step(THROTTLE)
    assert run.bike.state is State.COUNTDOWN and run.revs == run.bike.speed.index > 0


def test_sand_sounds_every_third_iteration_moving_on_it():
    run = Run(_solid_from(_floor(0, soft=True), 15))
    heard = []
    for _ in range(COUNTDOWN + 30):
        run.step(THROTTLE)
        heard.append(Cue.SAND in run.cues)
    moving = heard[COUNTDOWN + 3:]
    assert any(moving) and all(heard[i] == heard[i + 3] for i in
                                range(COUNTDOWN + 3, len(heard) - 3))
    assert sum(moving[:9]) == 3


def test_b_is_a_nitro_or_a_click_and_a_crash_is_heard():
    from game.engine.bike import Bike
    from game.engine.speed import Speed, update_index
    from tests.test_engine_bike import Ground
    assert update_index(Speed(nitros=1), State.RIDING, False, True) is Cue.NITRO
    assert update_index(Speed(nitros=0), State.RIDING, False, True) is Cue.EMPTY
    assert update_index(Speed(), State.RIDING, True, False) is None
    upside_down = Bike(Ground(), x=0x4000, y=0x4000, state=State.STOPPED, direction=16)
    upside_down.step(0, 0)
    assert upside_down.state is State.FALLING and upside_down.cues == [Cue.CRASH]


def test_an_effect_over_a_voice_hands_it_back_where_the_tune_has_got_to():
    """Why this test: a tune's voices all start on one tick, and an effect on
    top of one of them **hides it without stopping it** -- the original hands
    that voice back wherever the tune has reached, which is what keeps the parts
    together. A clock per channel, started when the mixer first *saw* a voice,
    hands it back at the beginning instead, and the voice then runs behind the
    rest for as long as the tune lasts.

    It is the screen a course is chosen on that this happened on, and every
    time: the button that settles the title and the tune it starts are asked for
    in the same breath, so the beep is always over a voice as the tune begins.

    What is checked is where each clip is **anchored on the wall clock** -- the
    tick its own beginning falls on, which is the tick it was asked for less how
    far into it the ask was. The same tune is played twice, once under an effect
    and once in the clear, and every clip has to be anchored to the same moment
    in both: a voice handed back late is a clip anchored late, and that is the
    fault this pins whatever the offsets happen to be. A looping clip is
    anchored **modulo its own length**, because a loop a whole turn later is the
    same place in the tune and not a fault.
    """
    clips = Clips(_four_slot_cartridge())

    def anchors(beep):
        mixer = Mixer(_four_slot_cartridge(), clips=clips)
        if beep:
            mixer.play(BEEP)
            mixer.changes()
        mixer.play(SELECT_MUSIC)
        _, loop = clips.music(SELECT_MUSIC)
        found, plays = {}, list(mixer.changes())
        for tick in range(150):
            for play in plays:
                if play.key and play.key[1] == SELECT_MUSIC:
                    at = tick - round(play.offset * apu.TICKS)
                    found.setdefault(play.key, at % loop if play.loop else at)
            plays = mixer.tick()
        return found

    under, clear = anchors(True), anchors(False)
    assert clear and under, "the tune has to be heard both ways"
    shared = set(under) & set(clear)
    assert shared, "the effect has to take a voice and give it back"
    assert {key: under[key] for key in shared} == {key: clear[key] for key in shared}, \
        "a voice under an effect came back anchored elsewhere"
    # The clips the two runs do not share are the entrance the effect outlasted,
    # which is the tune moving on without its hidden voice and not a fault.
    assert all(key[0] == "music" for key in set(clear) - set(under))
