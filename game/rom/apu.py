"""The Game Boy's sound chip: register writes in, samples out.

What the driver (`sound.py`) writes is all a sound is, and this turns it into a
signal the way the chip does:

- **two pulse channels**: a square wave of one of four duty cycles, at
  `131072 / (2048 - f)` Hz for an 11-bit `f`, with a volume **envelope** (a start,
  a direction, a step every `n` sixty-fourths of a second) and, on the first, a
  frequency **sweep**;
- **a wave channel**: thirty-two 4-bit samples out of its own RAM, played at
  `65536 / (2048 - f)` Hz, at full, half or quarter volume, or silent;
- **a noise channel**: a 15-bit shift register, or a 7-bit one, clocked at
  `524288 / r / 2^(s+1)` Hz, with an envelope;
- **a length counter** on each, which stops it when it runs out if asked to;
- **a mixer**: the channels the panning register sends to either side, summed,
  through the chip's high-pass filter.

The envelope, the sweep and the length run off the chip's 512 Hz sequencer; the
waveforms are sampled at `rate`.

**The panning is read, and mono is a fold and not an average.** The register
really does send each channel to one side, to both, or to neither, and the
cartridge uses it as an arrangement: the music between races throws the whole of
itself left and then right, a phrase at a time. Summing the two sides turns that
bounce into a dip in the volume -- three fifths of it, measured -- which is what
nobody hears, because nobody listens to this through one speaker. So a channel
sent to **either** side is folded down at its own level, and one sent to neither
is not heard at all. **The fold is a choice about the output and not a claim
about the chip**; what the chip does is `stereo`, which keeps the sides apart,
interleaved and each through a filter of its own. Nothing plays that yet -- Pyxel
mixes to mono -- and it is here so that the day something can, the chip is not
the thing in the way.
"""

from array import array

#: A second, in the chip's clock.
CLOCK = 4194304
#: Samples a second out.
RATE = 22050
#: The driver's ticks a second.
TICKS = 64
SEQUENCER = 512
DUTIES = ((0, 0, 0, 0, 0, 0, 0, 1), (1, 0, 0, 0, 0, 0, 0, 1),
          (1, 0, 0, 0, 0, 1, 1, 1), (0, 1, 1, 1, 1, 1, 1, 0))
#: The wave channel's volume codes, as how far each sample is shifted down.
WAVE_SHIFT = (4, 0, 1, 2)
NR10, NR51, WAVE_RAM = 0xFF10, 0xFF25, 0xFF30
#: A sample at full scale: one channel at its loudest reaches a quarter of it,
#: so all four at once still fit.
LOUDNESS = 32000


def _lfsr(width7: bool) -> bytes:
    """The noise register's output from reset, over one whole period."""
    state, out = 0x7FFF, bytearray()
    for _ in range(127 if width7 else 32767):
        out.append(~state & 1)
        bit = (state ^ state >> 1) & 1
        state = state >> 1 | bit << 14
        if width7:
            state = state & ~0x40 | bit << 6
    return bytes(out)


_NOISE = {False: _lfsr(False), True: _lfsr(True)}


class _Channel:
    """What every channel has: on or off, a DAC, a length, an envelope.

    Slotted, which is not tidiness: `render` reads four of these fields a
    channel a sample, and a slot is read without going through a dictionary.
    """

    __slots__ = ("on", "dac", "length", "length_max", "counting", "volume",
                 "start_volume", "rising", "period", "wait", "frequency", "phase")

    def __init__(self, length_max: int) -> None:
        self.on = False
        self.dac = False
        self.length = 0
        self.length_max = length_max
        self.counting = False
        self.volume = 0
        self.start_volume = 0
        self.rising = False
        self.period = 0
        self.wait = 0
        self.frequency = 0
        self.phase = 0.0

    def envelope(self, value: int) -> None:
        self.start_volume, self.rising, self.period = value >> 4, bool(value & 8), value & 7
        self.dac = bool(value & 0xF8)
        if not self.dac:
            self.on = False

    def trigger(self) -> None:
        self.on = self.dac
        if not self.length:
            self.length = self.length_max
        self.volume = self.start_volume
        self.wait = self.period
        self.phase = 0.0

    def clock_length(self) -> None:
        if self.counting and self.length:
            self.length -= 1
            if not self.length:
                self.on = False

    def clock_envelope(self) -> None:
        if not self.period:
            return
        self.wait -= 1
        if self.wait > 0:
            return
        self.wait = self.period
        if self.rising and self.volume < 15:
            self.volume += 1
        elif not self.rising and self.volume > 0:
            self.volume -= 1


class Apu:
    """The chip's state, a register write at a time and a sample at a time."""

    def __init__(self, rate: int = RATE) -> None:
        self.rate = rate
        self.pulses = [_Channel(64), _Channel(64)]
        self.duty = [0, 0]
        self.wave = _Channel(256)
        self.wave_volume = 0
        self.wave_ram = bytearray(16)
        self.noise = _Channel(64)
        self.noise_width7 = False
        self.noise_clock = 0.0
        self.sweep_period = self.sweep_shift = 0
        self.sweep_down = False
        self.sweep_wait = 0
        self.sweep_on = False
        self.sweep_frequency = 0
        self.pan = 0xFF
        self._sequence = 0.0
        self._step = 0
        self._filter_in = self._filter_out = 0.0
        #: The right side's capacitor, which only `render(stereo=True)` moves.
        self._other_in = self._other_out = 0.0
        self._charge = 0.999958 ** (CLOCK / rate)

    # -- registers ---------------------------------------------------------------

    def write(self, register: int, value: int) -> None:
        at = register - NR10
        if WAVE_RAM <= register < WAVE_RAM + 16:
            self.wave_ram[register - WAVE_RAM] = value
        elif register == NR51:
            self.pan = value
        elif at < 10 and at != 5:
            # The two pulse channels: five registers each, the second's first unused.
            index = 0 if at < 5 else 1
            channel = self.pulses[index]
            kind = at - 5 * index
            if kind == 0 and index == 0:
                self.sweep_period, self.sweep_down, self.sweep_shift = \
                    value >> 4 & 7, bool(value & 8), value & 7
            elif kind == 1:
                self.duty[index] = value >> 6
                channel.length = 64 - (value & 0x3F)
            elif kind == 2:
                channel.envelope(value)
            elif kind == 3:
                channel.frequency = channel.frequency & 0x700 | value
            elif kind == 4:
                self._high(channel, value)
                if value & 0x80:
                    channel.trigger()
                    if index == 0:
                        self._sweep_trigger()
        elif at == 0x0A:
            self.wave.dac = bool(value & 0x80)
            if not self.wave.dac:
                self.wave.on = False
        elif at == 0x0B:
            self.wave.length = 256 - value
        elif at == 0x0C:
            self.wave_volume = value >> 5 & 3
        elif at == 0x0D:
            self.wave.frequency = self.wave.frequency & 0x700 | value
        elif at == 0x0E:
            self._high(self.wave, value)
            if value & 0x80:
                self.wave.on = self.wave.dac
                if not self.wave.length:
                    self.wave.length = 256
                self.wave.phase = 0.0
        elif at == 0x10:
            self.noise.length = 64 - (value & 0x3F)
        elif at == 0x11:
            self.noise.envelope(value)
        elif at == 0x12:
            shift, divisor = value >> 4, value & 7
            self.noise_width7 = bool(value & 8)
            self.noise_clock = CLOCK / ((divisor * 16 if divisor else 8) << shift)
        elif at == 0x13:
            self.noise.counting = bool(value & 0x40)
            if value & 0x80:
                self.noise.trigger()

    @staticmethod
    def _high(channel: _Channel, value: int) -> None:
        channel.frequency = channel.frequency & 0xFF | (value & 7) << 8
        channel.counting = bool(value & 0x40)

    # -- the sweep ---------------------------------------------------------------

    def _sweep_trigger(self) -> None:
        self.sweep_frequency = self.pulses[0].frequency
        self.sweep_wait = self.sweep_period or 8
        self.sweep_on = bool(self.sweep_period or self.sweep_shift)
        if self.sweep_shift:
            self._sweep_next()

    def _sweep_next(self) -> int:
        delta = self.sweep_frequency >> self.sweep_shift
        value = self.sweep_frequency - delta if self.sweep_down else self.sweep_frequency + delta
        if value > 2047:
            self.pulses[0].on = False
        return value

    def _clock_sweep(self) -> None:
        self.sweep_wait -= 1
        if self.sweep_wait > 0:
            return
        self.sweep_wait = self.sweep_period or 8
        if not (self.sweep_on and self.sweep_period):
            return
        value = self._sweep_next()
        if value <= 2047 and self.sweep_shift:
            self.sweep_frequency = value
            self.pulses[0].frequency = value
            self._sweep_next()

    def _sequencer(self) -> None:
        step = self._step
        if step % 2 == 0:
            for channel in (self.pulses[0], self.pulses[1], self.wave, self.noise):
                channel.clock_length()
        if step in (2, 6):
            self._clock_sweep()
        if step == 7:
            for channel in (self.pulses[0], self.pulses[1], self.noise):
                channel.clock_envelope()
        self._step = (step + 1) % 8

    # -- samples -----------------------------------------------------------------

    def render(self, count: int, stereo: bool = False) -> "array[int]":
        """`count` samples, signed 16-bit -- or `count` pairs of them, left then
        right, with `stereo`.

        **This is where the whole of the time goes** -- a bank of clips is a few
        million samples and each one is this loop once -- so everything that
        cannot change between two writes is read once, above the loop: the
        panning, the duties, the wave's shape and volume, the noise's step. What
        a sample does read is what the frame sequencer can move under it while
        it runs: a channel's volume, whether it is on, and pulse 1's frequency,
        which the sweep walks.

        The arithmetic is the same arithmetic in the same order, down to where
        each division falls, because these are floats and a clip has to come out
        of this byte for byte what it came out of before.
        """
        out = array("h")
        append = out.append
        rate = self.rate
        per_step = rate / SEQUENCER
        sequence = self._sequence
        one, two = self.pulses[0], self.pulses[1]
        wave, noise = self.wave, self.noise
        duty_one, duty_two = DUTIES[self.duty[0]], DUTIES[self.duty[1]]
        wave_ram, wave_shift = self.wave_ram, WAVE_SHIFT[self.wave_volume]
        table = _NOISE[self.noise_width7]
        noise_step = self.noise_clock / rate
        noise_len = len(table)
        pan = self.pan
        left_on = tuple(pan >> (4 + index) & 1 for index in range(4))
        right_on = tuple(pan >> index & 1 for index in range(4))
        if not stereo:
            # The fold, and it costs the loop nothing: a channel heard on either
            # side is put on both, so the average below gives it its own level
            # back, and one heard on neither stays off.
            left_on = right_on = tuple(l | r for l, r in zip(left_on, right_on))
        filter_in, filter_out, charge = self._filter_in, self._filter_out, self._charge
        other_in, other_out = self._other_in, self._other_out
        for _ in range(count):
            sequence += 1
            while sequence >= per_step:
                sequence -= per_step
                self._sequencer()
            left = right = 0.0
            if one.dac:
                hz = 131072 / (2048 - one.frequency)
                phase = one.phase = (one.phase + hz / rate) % 1.0
                value = _ANALOG[one.volume if one.on and duty_one[int(phase * 8)] else 0]
                if left_on[0]:
                    left += value
                if right_on[0]:
                    right += value
            if two.dac:
                hz = 131072 / (2048 - two.frequency)
                phase = two.phase = (two.phase + hz / rate) % 1.0
                value = _ANALOG[two.volume if two.on and duty_two[int(phase * 8)] else 0]
                if left_on[1]:
                    left += value
                if right_on[1]:
                    right += value
            if wave.dac:
                hz = 65536 / (2048 - wave.frequency)
                phase = wave.phase = (wave.phase + hz / rate) % 1.0
                position = int(phase * 32)
                byte = wave_ram[position >> 1]
                sample = (byte >> 4 if position % 2 == 0 else byte & 0x0F) >> wave_shift
                value = _ANALOG[sample if wave.on else 0]
                if left_on[2]:
                    left += value
                if right_on[2]:
                    right += value
            if noise.dac:
                noise.phase += noise_step
                high = table[int(noise.phase) % noise_len]
                value = _ANALOG[noise.volume if noise.on and high else 0]
                if left_on[3]:
                    left += value
                if right_on[3]:
                    right += value
            if stereo:
                # One capacitor a side, which is what the chip has.
                level = left / 4
                filtered = level - filter_in + charge * filter_out
                filter_in, filter_out = level, filtered
                append(max(-32767, min(32767, int(filtered * LOUDNESS))))
                level = right / 4
                filtered = level - other_in + charge * other_out
                other_in, other_out = level, filtered
                append(max(-32767, min(32767, int(filtered * LOUDNESS))))
                continue
            level = (left + right) / 8
            # The chip's output capacitor: what stays, stays out.
            filtered = level - filter_in + charge * filter_out
            filter_in, filter_out = level, filtered
            append(max(-32767, min(32767, int(filtered * LOUDNESS))))
        self._sequence = sequence
        self._filter_in, self._filter_out = filter_in, filter_out
        self._other_in, self._other_out = other_in, other_out
        return out


def _analog(value: int) -> float:
    """A channel's 0..15 through its DAC: -1..1."""
    return value / 7.5 - 1.0


#: ...and the sixteen of them worked out once, because the loop above asks for
#: one of these four times a sample and there are only sixteen answers.
_ANALOG = tuple(_analog(value) for value in range(16))


def render(ticks: list[list[tuple[int, int]]], rate: int = RATE,
           apu: Apu | None = None, stereo: bool = False) -> "array[int]":
    """The samples a run of driver ticks makes: each tick's writes, then a
    sixty-fourth of a second. With `stereo`, two samples a moment rather than
    one, left then right."""
    apu = apu or Apu(rate)
    out = array("h")
    owed = 0.0
    for writes in ticks:
        for register, value in writes:
            apu.write(register, value)
        owed += rate / TICKS
        count = int(owed)
        owed -= count
        out.extend(apu.render(count, stereo))
    return out
