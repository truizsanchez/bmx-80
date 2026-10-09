"""The original's sound driver, run on its own data out of the cartridge.

Every sound the original makes -- the engine, the effects, the music -- is a
program for this driver: up to seven streams of bytes, one per **slot**, read a
command at a time. The driver runs **64 times a second**, on the timer rather
than the frame, and what it does is write the Game Boy's sound registers. This
is that driver, rule by rule; what it writes is the whole of its output, and
`apu.py` turns the writes into sound.

- **The slots.** 0 and 1 are the effects' two pulse channels, 2 the effects' noise
  channel; 3 and 4 are the music's pulse channels, 5 its wave channel and 6 its
  drums. A music slot on a pulse channel says nothing while the effect slot on
  the same channel is playing, and takes the channel back when the effect ends.
- **A request** names a sound; the sound's header gives a priority and which
  slots it has streams for. A slot already playing something of higher priority
  keeps it.
- **A stream** is commands and notes. A note is a pitch (a semitone above the
  octave, looked up in the cartridge's note table) and a length; a rest is a
  note with no pitch. Commands set the note length, the octave, a transposition,
  the volume and its fade, the duty cycle or the wave, a pitch bend, the tempo
  and the stereo panning; and there are loops, calls, jumps and the end.
- **The tempo** paces the music and not the effects: each tick the tempo is added
  to an 8-bit beat, and on a tick where it overflows the music slots wait.
- **The engine** is one of these sounds, and the one input from the race: its
  pitch is offset by eight times the speed curve's value (`engine`), which the
  race sets every iteration.
- **The drums** are effects: the drum slot's notes request one of seven short
  noise sounds, which play on the effects' noise slot.

Nothing here is copied out of the cartridge: every table is read from it where
the original keeps it.
"""

from dataclasses import dataclass

from game.rom.cartridge import Cartridge

#: One header per sound, from sound 1: a priority, a byte of slots, a stream each.
SOUNDS = 0x6F30
#: Each slot's first register, counted from `NR10`.
BASES = 0x6BC3
#: A word per semitone: the frequency register's value.
NOTES = 0x6DCE
#: Pitch bends, a pointer each.
BENDS = 0x7061
#: The wave channel's shapes, a pointer to sixteen bytes each.
WAVES = 0x6E8E
#: The sound each drum note requests.
DRUMS = 0x7002
#: The music a course plays when the start's last beep ends, by course.
COURSE_MUSIC = 0x678D
#: What of the panning register each slot leaves alone.
PAN_MASKS = 0x6890

SLOTS = 7
NOISE_EFFECT, MUSIC_PULSE, MUSIC_PULSE_2, MUSIC_WAVE, DRUM = 2, 3, 4, 5, 6
#: The register file: `NR10` and the twenty bytes after it, and the wave's RAM.
NR10, NR51, WAVE_RAM = 0xFF10, 0xFF25, 0xFF30
WAVE_BASE = 0x0A
#: The engine's sound, and the start's last beep, whose end starts the music.
ENGINE, GO = 0x09, 0x11
#: The one sound that plays while the game is paused.
PAUSE = 0x08
#: More commands than this without a note, or bend steps without a value, and a
#: stream is not a sound: it is ended rather than read for ever. The original's
#: own read a handful.
RUNAWAY = 0x100
#: A slot's flags.
_RELEASED, _DOWN, _FORCE, _REST = 0x01, 0x08, 0x40, 0x80


def _swap(value: int) -> int:
    return (value << 4 | value >> 4) & 0xFF


@dataclass(slots=True)
class Slot:
    """One stream being played, and everything the driver keeps about it.
    Fields outlive the sound: a new one resets only what `Driver.play` says."""

    sound: int = 0
    priority: int = 0
    at: int = 0
    timer: int = 0
    flags: int = 0
    loops: int = 0
    bend: int = 0
    transpose: int = 0
    atten: int = 0
    offset: int = 0
    bend_count: int = 0
    length: int = 0
    octave: int = 0
    frequency: int = 0
    volume: int = 0
    duty: int = 0
    fade: int = 0
    gate: int = 0
    release: int = 0
    bend_wait: int = 0
    bend_period: int = 0
    wave_wait: int = 0
    wave_period: int = 0
    level: int = 0
    loop_at: int = 0
    back: int = 0
    bend_table: int = 0
    bend_index: int = 0
    bend_loop: int = 0
    #: Which start this is, counted over the driver's life, and the ticks since:
    #: what tells a sound started again from the same sound going on.
    start: int = 0
    ticks: int = 0


class Driver:
    """The driver's state, a request at a time and a tick at a time."""

    def __init__(self, cartridge: Cartridge, course: int = 1) -> None:
        self.cartridge = cartridge
        self.slots = [Slot() for _ in range(SLOTS)]
        #: What the driver last wrote to each of `NR10`..`NR24`.
        self.shadow = bytearray(0x15)
        self.pan = 0
        self.tempo = 0
        #: A tempo written over the stream's from outside, which is what a race
        #: does: **the original rewrites the music's tempo every iteration** out
        #: of one of two tables, so the `EE` in a course's own stream is overruled
        #: for as long as the race runs. None leaves the stream's own, which is
        #: what the music between races keeps.
        self.forced: int | None = None
        self.beat = 0
        #: The speed curve's value, set by the race: the engine's pitch.
        self.engine = 0
        self.paused = False
        #: The music waits while this is set.
        self.holding = False
        #: A sound to request at the end of the next tick.
        self.queued = 0
        self.course = course
        #: Sounds started on a slot, ever.
        self.starts = 0
        self._current = 0
        self._base = 0
        self._writes: list[tuple[int, int]] = []

    # -- the two things the game does ------------------------------------------

    def request(self, sound: int) -> list[tuple[int, int]]:
        """Start a sound, now; returns the register writes that makes."""
        self._writes = []
        self._play(sound)
        return self._writes

    def tick(self) -> list[tuple[int, int]]:
        """One of the 64 a second: every slot a step. Returns the writes."""
        self._writes = []
        if self.forced is not None:
            self.tempo = self.forced
        total = self.beat + self.tempo
        self.beat = total & 0xFF
        late = total > 0xFF or self.holding
        waits_from = MUSIC_PULSE_2 if self.slots[MUSIC_PULSE].sound == ENGINE else MUSIC_PULSE
        for index in range(SLOTS):
            self._current = index
            if self.paused:
                if index != 1:
                    continue
                if self.slots[1].sound != PAUSE:
                    break
            elif index == waits_from and late:
                break
            if self.slots[index].sound:
                self.slots[index].ticks += 1
                self._step(index)
        if self.queued:
            sound, self.queued = self.queued, 0
            self._play(sound)
        return self._writes

    # -- the cartridge -------------------------------------------------------------

    def _byte(self, address: int) -> int:
        """A byte of the cartridge; past its end, the end of a stream."""
        data = self.cartridge.data
        address &= 0xFFFF
        return data[address] if address < len(data) else 0xFF

    def _word(self, address: int) -> int:
        return self._byte(address) | self._byte(address + 1) << 8

    # -- registers ---------------------------------------------------------------

    def _out(self, register: int, value: int) -> None:
        self._writes.append((register, value))

    def _silenced(self) -> bool:
        """A music slot on a channel an effect holds."""
        return (self._current == MUSIC_PULSE and self.slots[0].sound != 0) or \
               (self._current == MUSIC_PULSE_2 and self.slots[1].sound != 0)

    def _set(self, register: int, value: int) -> None:
        """Register `register` of the current channel, if it changes -- or always,
        for the first note after a rest."""
        if self._silenced():
            return
        at = self._base + register
        if not self.slots[self._current].flags & _FORCE and self.shadow[at] == value:
            return
        self.shadow[at] = value
        self._out(NR10 + at, value)

    def _trigger(self) -> None:
        if self._silenced():
            return
        at = self._base + 4
        self._out(NR10 + at, self.shadow[at] | 0x80)

    def _pitch(self, slot: Slot) -> None:
        """The note's frequency, bent; the engine's by its speed."""
        if slot.sound == ENGINE:
            slot.offset = self.engine * 8 & 0xFFFF
        offset = -slot.offset & 0xFFFF if slot.flags & _DOWN else slot.offset
        value = (slot.frequency + offset) & 0xFFFF
        self._set(3, value & 0xFF)
        self._set(4, value >> 8)

    def _shape(self, slot: Slot) -> None:
        """The duty cycle -- or, on the wave channel, the wave itself."""
        if self._base != WAVE_BASE:
            self._set(1, _swap(slot.duty))
            return
        at = self._word(WAVES + ((slot.duty - 1) * 2 & 0xFF))
        for k in range(16):
            self._out(WAVE_RAM + k, self._byte(at + k))

    # -- a request ---------------------------------------------------------------

    def _play(self, sound: int) -> None:
        if not sound:
            self._stop_all()
            return
        header = (SOUNDS + ((sound - 1) * 2 & 0xFF))
        at = self._word(header)
        priority, which = self._byte(at), self._byte(at + 1)
        at += 2
        # Bit n of `which` is slot n, taken in that order; each takes the channel's
        # two panning bits for itself -- the drums, whose effects do, excepted.
        for index, pan in enumerate((0x11, 0x22, 0x88, 0x11, 0x22, 0x44, 0)):
            if not which >> index & 1:
                continue
            if index == 0 or (index == MUSIC_PULSE and not self.slots[0].sound):
                self.shadow[0] = 0x08
                self._out(NR10, 0x08)
            if pan:
                self.pan = (self.pan & ~pan & 0xFF) | pan
            self._start(self.slots[index], sound, priority, self._word(at))
            at += 2
        self._out(NR51, self.pan)

    def _start(self, slot: Slot, sound: int, priority: int, at: int) -> None:
        if priority < slot.priority:
            return
        slot.priority, slot.sound, slot.at = priority, sound, at
        self.starts += 1
        slot.start, slot.ticks = self.starts, 0
        slot.timer, slot.flags = 1, _FORCE
        slot.loops = slot.bend = slot.transpose = slot.atten = slot.offset = 0
        slot.bend_count = 0

    def _stop_all(self) -> None:
        for index in range(SLOTS):
            self.slots[index] = Slot()
        self.shadow = bytearray(0x15)
        self.pan = self.tempo = self.beat = self.engine = self.queued = 0
        for register, value in ((0xFF12, 0), (0xFF14, 0x80), (0xFF17, 0), (0xFF19, 0x80),
                                (0xFF1C, 0), (0xFF21, 0), (0xFF23, 0x80)):
            self._out(register, value)

    # -- a slot's tick -----------------------------------------------------------

    def _step(self, index: int) -> None:
        slot = self.slots[index]
        self._base = self._byte(BASES + index)
        slot.timer = (slot.timer - 1) & 0xFF
        if not slot.timer:
            slot.flags &= ~(_RELEASED | _REST)
            if index == MUSIC_WAVE:
                self.shadow[WAVE_BASE] = 0
                self._out(NR10 + WAVE_BASE, 0)
            self._read(index, slot)
            return
        if slot.release >= slot.timer:
            slot.flags |= _RELEASED
        if slot.flags & _REST or index in (NOISE_EFFECT, DRUM):
            return
        self._bend_tick(slot)
        if index == MUSIC_WAVE:
            self._wave_fade(slot)
            return
        if slot.release != slot.timer:
            return
        # The note's release: its volume, and the fade from it.
        value = _swap(((slot.volume & 0x0F) - slot.atten) & 0xFF) | slot.fade if slot.fade else 0
        self._set(2, value)
        self._trigger()

    def _wave_fade(self, slot: Slot) -> None:
        """After its release, the wave channel steps down its three volumes."""
        if not slot.flags & _RELEASED:
            return
        level, carry = 0, 0
        if slot.fade:
            slot.wave_wait = (slot.wave_wait - 1) & 0xFF
            if slot.wave_wait:
                return
            slot.wave_wait = slot.wave_period
            if slot.level:
                slot.level = (slot.level + 1) & 3
                if slot.level:
                    level = slot.level + slot.atten
                    carry = 1 if level < 4 else 0
                    level = level if level < 4 else 0
        self._set(2, _swap((level << 1 | carry) & 0xFF))

    def _bend_tick(self, slot: Slot) -> None:
        if not slot.bend:
            return
        slot.bend_wait = (slot.bend_wait - 1) & 0xFF
        if slot.bend_wait:
            return
        slot.bend_wait = slot.bend_period
        self._bend(slot)
        self._pitch(slot)

    def _bend(self, slot: Slot) -> None:
        """The next step of the note's pitch bend: an offset, a direction and how
        long it lasts. Its table has a loop mark, a repeat count and an end."""
        for _ in range(RUNAWAY):
            at = (slot.bend_table + slot.bend_index) & 0xFFFF
            for _ in range(RUNAWAY):
                value = self._byte(at)
                if value == 0xFB:
                    slot.bend_index = (slot.bend_index + 1) & 0xFF
                    slot.bend_loop = slot.bend_index
                    at += 1
                    continue
                if value == 0xFE:
                    at += 1
                    count = self._byte(at)
                    if count == slot.bend_count:
                        slot.bend_count = 0
                        slot.bend_index = (slot.bend_index + 2) & 0xFF
                        at += 2
                        continue
                    if count != 0xFF:
                        slot.bend_count = (slot.bend_count + 1) & 0xFF
                    slot.bend_index = slot.bend_loop
                    break
                if value == 0xFF:
                    return
                slot.bend_wait = slot.bend_period = value >> 4
                if value & _DOWN:
                    slot.flags |= _DOWN
                slot.bend_index = (slot.bend_index + 1) & 0xFF
                slot.offset = (value & 7) << 8 | self._byte(at + 1)
                slot.bend_index = (slot.bend_index + 1) & 0xFF
                return

    # -- the stream --------------------------------------------------------------

    def _read(self, index: int, slot: Slot) -> None:
        """Commands until a note, a rest or the end."""
        at = slot.at
        for _ in range(RUNAWAY):
            op = self._byte(at)
            if op >= 0xFB:
                if op == 0xFF:
                    self._end(index, slot)
                    return
                at = self._flow(slot, op, at + 1)
                continue
            if op == 0xE0:
                at = self._envelope(index, slot, at)
                continue
            if op & 0xF0 < 0xE0:
                self._note(index, slot, at)
                return
            if op & 0xF0 == 0xF0:
                slot.atten = op & 0x0F
                if index == NOISE_EFFECT:
                    slot.level = _swap(((slot.volume & 0x0F) - slot.atten) & 0xFF)
                    self._set(2, slot.level | slot.fade)
                    self._trigger()
                at += 1
                continue
            if op < 0xE7:
                slot.octave = ((op & 0x0F) - 1) & 0xFF
                at += 1
                continue
            at += 1
            self._command(index, slot, op, self._byte(at))
            at += 1
        self._end(index, slot)

    def _flow(self, slot: Slot, op: int, at: int) -> int:
        """`FB`-`FE`, the commands that move the reading: mark the loop, return,
        call, and loop a count of times (or jump, with a count of `FF`). Returns
        where the reading goes on from."""
        if op == 0xFB:
            slot.loop_at = at
            return at
        if op == 0xFC:
            return slot.back
        if op == 0xFD:
            slot.back = at + 2
            return self._word(at)
        count = self._byte(at)
        if count == 0xFF:
            return self._word(at + 1)
        slot.loops = (slot.loops + 1) & 0xFF
        if count == slot.loops:
            slot.loops = 0
            return at + 1
        return slot.loop_at

    def _envelope(self, index: int, slot: Slot, at: int) -> int:
        """`E0`: the note length, then the volume, duty, fade and gate."""
        at += 1
        slot.length = self._byte(at)
        if index == DRUM:
            return at + 1
        at += 1
        value = self._byte(at)
        if index == NOISE_EFFECT:
            slot.fade, slot.volume = value & 0x0F, value >> 4
            self._set(2, value)
            self._trigger()
            return at + 1
        slot.volume, slot.duty = value & 0x0F, value >> 4
        self._shape(slot)
        at += 1
        value = self._byte(at)
        slot.fade, slot.gate = value & 0x0F, value >> 4
        return at + 1

    def _command(self, index: int, slot: Slot, op: int, arg: int) -> None:
        if op == 0xE7:
            slot.length = arg
        elif op == 0xE8:
            slot.fade, slot.gate = arg & 0x0F, arg >> 4
        elif op == 0xE9:
            self._set(0, arg)
        elif op == 0xEA:
            kind, value = arg >> 4, arg & 0x0F
            if kind == 0:
                slot.transpose = value
            elif kind == 1:
                slot.transpose = -value & 0xFF
            elif kind == 2:
                slot.bend = value
                slot.bend_table = self._word(BENDS + ((value - 1) * 2 & 0xFF))
                slot.bend_count = 0
            elif kind == 3:
                slot.duty = value
                self._shape(slot)
        elif op == 0xEE:
            self.tempo = arg
        elif op == 0xEF:
            if index == MUSIC_PULSE and self.slots[0].sound:
                return
            mask = self._byte(PAN_MASKS + index)
            self.pan = (self.pan & mask) | (_swap(arg) & ~mask & 0xFF)
            self._out(NR51, self.pan)

    def _note(self, index: int, slot: Slot, at: int) -> None:
        slot.at = at + 1
        op = self._byte(at)
        if index == NOISE_EFFECT:
            # The noise channel's notes are its polynomial register as it stands.
            slot.timer = slot.length
            self._set(3, op)
            self._set(4, 0)
            return
        slot.timer = slot.length * (op & 0x0F) & 0xFF
        if not op & 0xF0:
            slot.flags |= _FORCE | _REST
            self._set(2, 0)
            self._set(4, 0x80)
            return
        if index == DRUM:
            self._play(self._byte(DRUMS + (op >> 4) - 1))
            return
        slot.release = (slot.timer - 1) & 0xFF if slot.gate == 0x0F else \
            _scaled(slot.timer, slot.gate)
        slot.bend_count = 0
        octave = 12 * slot.octave & 0xFF if slot.octave else 0
        semitone = ((op >> 4) - 1 + slot.transpose + octave) & 0xFF
        slot.frequency = self._word(NOTES + semitone * 2)
        if slot.bend:
            slot.bend_index = 0
            self._bend(slot)
        self._pitch(slot)
        slot.flags &= ~_FORCE
        if index == MUSIC_WAVE:
            self._wave_note(slot)
            return
        slot.level = _swap(((slot.volume & 0x0F) - slot.atten) & 0xFF)
        self._set(2, slot.level)
        self._trigger()

    def _wave_note(self, slot: Slot) -> None:
        self.shadow[WAVE_BASE] = 0x80
        self._out(NR10 + WAVE_BASE, 0x80)
        slot.wave_wait = slot.wave_period = slot.fade
        slot.level = (slot.volume & 0x0F) >> 1 & 3
        level = slot.level + slot.atten
        carry = 1 if level < 4 else 0
        level = level if level < 4 else 0
        self._set(2, (_swap(level) << 1 | carry) & 0xF0)
        self._trigger()

    def _end(self, index: int, slot: Slot) -> None:
        """`FF`: the slot is free; an effect gives its channel back to the music."""
        if slot.sound == GO:
            self.queued = self._byte(COURSE_MUSIC + ((self.course - 1) & 0xFF))
        slot.sound = slot.priority = 0
        self._set(2, 0)
        self._trigger()
        if index == 0:
            self._out(NR10, 0)
            music = self.slots[MUSIC_PULSE]
        elif index == 1:
            music = self.slots[MUSIC_PULSE_2]
        else:
            return
        if not music.sound:
            return
        self._shape(music)
        self._set(3, music.frequency & 0xFF)
        self._set(4, music.frequency >> 8)


def _scaled(length: int, gate: int) -> int:
    """`length * gate / 16`, as the original's four-step shift-and-add has it."""
    value = 0
    for _ in range(4):
        carry = gate & 1
        gate >>= 1
        if carry:
            value += length
            carry = 1 if value > 0xFF else 0
            value &= 0xFF
        value = value >> 1 | carry << 7
    return value
