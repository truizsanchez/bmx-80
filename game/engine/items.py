"""The things on a course to pick up, and what each one does.

Six kinds, each a crate or a secret at a metatile of the map:

- **S** raises the speed cap to the ruleset's `cap_s`;
- **T** adds ten seconds to the time left;
- **N** adds four nitros;
- **R** turns the slope term off (`speed.slope`: the R is for the hills);
- **J** lets a nitro be fired anywhere in a flight, nose up;
- **a mini-maniac** is one more of them riding along, up to three.

The J and the mini-maniacs are secrets: they are not in the map, and they are
only picked up **upside down** -- attitude 16 exactly. A thing is picked up when
it is within 15 px of the bike either way, measured from its metatile's corner
and the bike's position, with the bike's x taken within the lap. A crate taken
is gone from the map; at the lap line every one comes back. A **secret** taken
leaves a `Flash` instead, which is the only thing that says one was there.
"""

from dataclasses import dataclass

from game.engine.bike import Bike
from game.engine.original import (
    BYTE,
    FLASH,
    FLASH_Y,
    J,
    LAP_MASK,
    MAX_MINIS,
    METATILE,
    MINI,
    N,
    NITRO_PACK,
    PIXEL,
    R,
    REACH,
    S,
    SPAN,
    T,
    TEN_SECONDS,
    UPSIDE_DOWN,
)

#: From this kind on, a thing is a secret: not in the map, taken upside down.
SECRET = J


@dataclass(slots=True)
class Item:
    """One thing on the course: its kind and its metatile, and whether it is
    still there to be picked up."""

    kind: int
    row: int
    col: int
    there: bool = True

    def reached(self, bike: Bike) -> bool:
        """Whether the bike is on it -- and, for a secret, upside down."""
        if self.kind >= SECRET and bike.attitude != UPSIDE_DOWN:
            return False
        x = (bike.x >> PIXEL) & LAP_MASK
        y = (bike.y >> PIXEL) & BYTE
        return (0 <= self.row * METATILE + REACH - y < SPAN
                and 0 <= self.col * METATILE + REACH - x < SPAN)


@dataclass(slots=True)
class Flash:
    """What taking a secret leaves on the screen: which one, where, how long.

    **It rises a pixel an iteration** rather than sitting where it was taken,
    which is the whole of it being a flourish and not a thing on the course.
    Nothing but the eye reads it -- it is how a player finds out a secret was
    there at all, the J and the mini-maniacs being invisible.
    """

    kind: int
    x: int
    y: int
    left: int

    def step(self) -> None:
        self.left -= 1
        self.y -= 1


def taken(bike: Bike, kind: int) -> Flash:
    """The flourish a secret taken by `bike` leaves, where it leaves it."""
    return Flash(kind, bike.px[0], bike.px[1] + FLASH_Y, FLASH)


def give(bike: Bike, kind: int) -> int:
    """What picking up a thing of `kind` does to the bike. Returns the hundredths
    of a second it adds to the time left -- which is the run's, not the bike's."""
    if kind == S:
        bike.speed.cap = bike.rules.cap_s
    elif kind == T:
        return TEN_SECONDS
    elif kind == N:
        bike.speed.nitros = (bike.speed.nitros + NITRO_PACK) & BYTE
    elif kind == R:
        bike.no_slope = True
    elif kind == J:
        bike.jet = True
    elif kind == MINI:
        bike.minis = min(MAX_MINIS, bike.minis + 1)
    return 0
