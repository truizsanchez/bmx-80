"""A Motocross Maniacs cartridge file, identified before anything is read from it.

A 32 KB ROM with no bank switching, so every address below is also an offset
into the file. It is accepted only if it is the European release -- checked by
its SHA-1, the one thing that says "these addresses mean what this code thinks"
-- and refused otherwise with a sentence that says which of the checks failed.
"""

import hashlib

from game.engine.original import DIRECTIONS
from game.engine.terrain import Hit

#: The whole file, and the release this code reads.
SIZE = 0x8000
TITLE = b"MOTOCROSSMANIACS"
EUROPE_SHA1 = "956a12a65a1c39948c312303719895bd6f141a61"

# Where the header says what the cartridge is.
_TITLE_AT = 0x134

#: One byte per tile id: bit 7 solid, bit 6 soft, bit 5 no wheelie, bits 0-4 the
#: direction of travel.
COLLISION = 0x5CA0
_SOLID, _SOFT, _NO_WHEELIE, _DIRECTION = 0x80, 0x40, 0x20, 0x1F

#: Three window cells per direction, which the floor probes read.
PROBES = 0x5DA0
#: A thrown rider's path: `(dy, dx)` a step, two signed words each.
THROW = 0x5EE8
#: One tile per direction for a mini-maniac riding behind the player: a little
#: bike in four poses, and **bit 7 says it is mirrored** -- the original draws
#: those flipped in both axes at once, being half a turn round.
MINIS = 0x5EC8
#: A pose past the thirty-two directions is the rider's own, and the original
#: draws a mini-maniac in this one for all of them.
MINI_FALLBACK = 4
_MIRRORED = 0x80
#: A bike's picture at every attitude it can have -- the thirty-two directions,
#: the rider thrown, down, walking back and lifting the bike, and the three
#: flourishes -- as a table of addresses, one a pose. Each is a count and then
#: that many **sprite slots**, in order: `dy, dx, tile, flags` as the object
#: memory takes them, or the one byte `$80`, which empties its slot.
POSES = 0x3492
POSE_COUNT = 0x38
_EMPTY_SLOT = 0x80
#: A sprite's flags, the object memory's own bits: mirrored left to right,
#: upside down, and drawn in the second object palette -- the computer's bike.
X_FLIP, Y_FLIP, SECOND_PALETTE = 0x20, 0x40, 0x10
#: The object palettes, where the routine that sets them writes them as bytes
#: of its own code: the first is the background's, colour for colour, and the
#: second turns every colour but the clear one into the same dark grey.
OBJECT_PALETTES = (0x02F1, 0x02F7)
#: The qualifying times, one table per level (A, B, C): per course, hundredths,
#: seconds and minutes, in binary-coded decimal.
QUALIFYING = (0x2DE2, 0x2DFD, 0x2E15)
#: The times on the board before anybody has ridden, in the same three bytes a
#: course. The original has no battery and keeps no times, so **these are what
#: its card shows every time it is switched on** until a race beats one.
RECORDS = 0x2E39

#: The music's tempo, in two tables of four bytes: the one a race runs at, and
#: the one it runs at **with under ten seconds left**. The original rewrites the
#: driver's tempo out of one of them every iteration, so a course's tune is
#: played at the table's rate and not at the one its own stream asks for.
TEMPO, TEMPO_HURRIED = 0x7FFB, 0x7FF7
#: The tunes the two tables cover: the courses' four and no others. The music
#: the screens between races play keeps whatever tempo its own stream sets --
#: the original's routine reads the tune's number and leaves anything outside
#: this range alone.
FIRST_TUNE, TUNES = 0x1D, 4


class NotTheCartridge(ValueError):
    """The file is not the European Motocross Maniacs, and the message says why."""


class Cartridge:
    """The ROM's bytes, and reads of them by address."""

    def __init__(self, data: bytes, check: bool = True) -> None:
        """`check` is off only for a test that builds a cartridge-shaped file."""
        if check:
            identify(data)
        self.data = bytes(data)

    @classmethod
    def from_file(cls, path: str) -> "Cartridge":
        with open(path, "rb") as handle:
            return cls(handle.read())

    def byte(self, address: int) -> int:
        return self.data[address]

    def word(self, address: int) -> int:
        """Little-endian, as the Game Boy stores a pointer."""
        return self.data[address] | self.data[address + 1] << 8

    def hit(self, tile: int) -> Hit:
        """What the collision makes of tile id `tile`."""
        value = self.data[COLLISION + tile]
        return Hit(bool(value & _SOLID), bool(value & _SOFT), bool(value & _NO_WHEELIE),
                   value & _DIRECTION)

    def limit(self, course: int, level: int) -> int:
        """The time a race of `course` at `level` (0-2) starts with, in hundredths
        of a second."""
        return self._time(QUALIFYING[level] + 3 * (course - 1))

    def record(self, course: int) -> int:
        """The course's record as the cartridge ships it, in hundredths.

        Not a record anybody set: the original copies this table into memory at
        every boot, so it is the number its card shows until a race beats it.
        The same three bytes as a qualifying time, and the same order.
        """
        return self._time(RECORDS + 3 * (course - 1))

    def mini(self, attitude: int) -> tuple[int, bool]:
        """The tile a mini-maniac riding at `attitude` is drawn with, and
        whether it is mirrored. A **sprite's** tile, and a low one: no
        background id names it."""
        at = attitude if attitude < DIRECTIONS else MINI_FALLBACK
        value = self.byte(MINIS + at)
        return value & ~_MIRRORED, bool(value & _MIRRORED)

    def object_palette(self, second: bool) -> int:
        """An object palette: two bits a colour, the shade colour `n` is drawn in."""
        return self.byte(OBJECT_PALETTES[second])

    def pose(self, attitude: int) -> tuple[tuple[int, int, int, int] | None, ...]:
        """The sprite slots a bike at `attitude` writes: `(dy, dx, tile, flags)`
        from the bike's top left, or None for a slot it empties.

        **A slot is a place, not only a picture**: a pose writes as many slots
        as it has and leaves the rest as they were, which is how the bike left
        lying on the ground stays on screen while the thrown rider is drawn in
        the slots before it.
        """
        def signed(value: int) -> int:
            return value - 0x100 if value & 0x80 else value

        at = self.word(POSES + 2 * (attitude if attitude < POSE_COUNT else 0))
        slots: list[tuple[int, int, int, int] | None] = []
        for _ in range(self.byte(at)):
            at += 1
            if self.byte(at) == _EMPTY_SLOT:
                slots.append(None)
                continue
            slots.append((signed(self.byte(at)), signed(self.byte(at + 1)),
                          self.byte(at + 2), self.byte(at + 3)))
            at += 3
        return tuple(slots)

    def tempo(self, tune: int, hurried: bool = False) -> int | None:
        """The tempo the original forces on a course's tune, or none for a tune
        the tables do not cover.

        Higher is slower: the tempo is how often the music waits a tick, so the
        hurried table's smaller numbers are the music going faster -- between a
        ninth and a quarter faster, by tune, and not the double it sounds like.
        """
        if not FIRST_TUNE <= tune < FIRST_TUNE + TUNES:
            return None
        return self.byte((TEMPO_HURRIED if hurried else TEMPO) + tune - FIRST_TUNE)

    def _time(self, at: int) -> int:
        """Three bytes of binary-coded decimal -- hundredths, seconds, minutes --
        as hundredths of a second."""

        def bcd(value: int) -> int:
            return (value >> 4) * 10 + (value & 0x0F)
        hundredths, seconds, minutes = (bcd(self.data[at + i]) for i in range(3))
        return (minutes * 60 + seconds) * 100 + hundredths

    def throw(self, step: int) -> tuple[int, int]:
        """One step of a thrown rider's path: `(dy, dx)`, signed."""
        at = THROW + 4 * step

        def signed(value: int) -> int:
            return value - 0x10000 if value & 0x8000 else value
        return signed(self.word(at)), signed(self.word(at + 2))

    def probes(self, direction: int) -> tuple[int, int, int]:
        """The three probed window cells for `direction`."""
        at = PROBES + 3 * direction
        return (self.data[at], self.data[at + 1], self.data[at + 2])


def identify(data: bytes) -> None:
    """Raise `NotTheCartridge` unless `data` is the European release."""
    if len(data) != SIZE:
        raise NotTheCartridge(
            "a Motocross Maniacs ROM is %d bytes, and this file is %d" % (SIZE, len(data)))
    if data[_TITLE_AT:_TITLE_AT + len(TITLE)] != TITLE:
        raise NotTheCartridge("this file is not Motocross Maniacs")
    if hashlib.sha1(data).hexdigest() != EUROPE_SHA1:
        raise NotTheCartridge(
            "this is Motocross Maniacs, but not the European release, which is the "
            "only one this game reads")
