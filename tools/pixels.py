"""The pixels a generator writes, and the plumbing every generator shares.

Two generators write this game's art -- `tools/tile_gen.py` for the glyphs and
the logo, `tools/sprite_gen.py` for the bike -- and `tools/rom_shot.py` writes a
picture of a cartridge's course. All three want the same few things: a raster is
a tuple of palette indices, a style resolves from a name or from `art/STYLE`,
and a PNG is encoded here by hand.

**By hand rather than through a library.** Pyxel's own `Image.save` needs a
window and a live palette, and a third-party encoder would make
`test_generating_twice_gives_the_same_bytes` a claim about that encoder's
version rather than about this repository. Colour type 2 (RGB8) is what the
loader path expects -- Pyxel maps every source pixel to the nearest palette
entry -- and at distance 0 that mapping is exact.

Nothing here knows what is being drawn.
"""

import argparse
import math
import os
import struct
import sys
import zlib
from collections.abc import Callable, Mapping, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.constants import CELL  # noqa: E402
from game.render import style as styles  # noqa: E402

#: A point in pixels, which every generator passes about.
Point = tuple[float, float]
#: Close enough to zero. A generator compares distances and a distance of
#: exactly zero is a coincidence rather than a case.
EPS = 1e-9

#: One tile: `CELL * CELL` palette indices, row-major.
Raster = tuple[int, ...]
#: A look by name, the look itself, or `None` for the one in `art/STYLE`.
StyleLike = styles.Style | str | None


# The four shades, as palette indices. Which *colour* each one is belongs to the
# style; what each index **means** never does, and that is what lets a look be
# swapped without touching a raster.
SKY, EDGE, RIM, BULK = styles.SKY, styles.EDGE, styles.RIM, styles.BULK

# The art's dials live in `game/render/style.py` now, because the game needs them
# too: the PNGs carry the style's colours verbatim and `palette.apply` has to
# install the same four values, so the two cannot be allowed to disagree.
STYLES = tuple(sorted(styles.STYLES))

# Darkest to lightest, for --print and for the conflict diffs.
_CHARS = {EDGE: "#", BULK: "+", RIM: "-", SKY: "."}
_INDICES = {char: index for index, char in _CHARS.items()}


def from_text(rows: Sequence[str]) -> Raster:
    """A raster from the 16 strings of 16 characters that spell it."""
    if len(rows) != CELL or any(len(row) != CELL for row in rows):
        raise ValueError("a tile is %d rows of %d characters" % (CELL, CELL))
    return tuple(_INDICES[char] for row in rows for char in row)



def to_text(art: Sequence[int]) -> str:
    width, height = _size(art)
    return "\n".join(
        "".join(_CHARS[art[y * width + x]] for x in range(width)) for y in range(height)
    )



# -- PNG ----------------------------------------------------------------------
#
# Written by hand rather than through a library. Pyxel's own Image.save needs a
# window and a live palette, and a third-party encoder would make
# `test_generating_twice_gives_the_same_bytes` a claim about that encoder's
# version rather than about this tool. Colour type 2 (RGB8) is what the loader
# path expects -- Pyxel maps every source pixel to the nearest palette entry --
# and at distance 0 that mapping is exact.

def _style(name: StyleLike = None) -> styles.Style:
    """A Style from a name, from `art/STYLE`, or the one already resolved."""
    if isinstance(name, styles.Style):
        return name
    return styles.STYLES[name] if name else styles.active()


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_rgb(width: int, height: int, rgb: bytes) -> bytes:
    """An RGB8 PNG of `width * height * 3` bytes, as bytes. Deterministic.

    Split out of `encode_png`, which calls it, so the project keeps having
    exactly one PNG writer: a second encoder would be a second thing to get
    right about CRCs and filter bytes.
    """
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter type 0: none, so the bytes are the pixels
        raw += rgb[y * stride:(y + 1) * stride]
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def decode_rgb(data: bytes) -> tuple[int, int, bytes]:
    """`(width, height, rgb)` from RGB8 PNG bytes. The mirror of `encode_rgb`.

    Bit depth 8, colour types 0/2/3/6, every filter type, no interlace. Narrow on
    purpose: that is what the PNGs this project actually reads happen to be --
    our own tiles and `pyxel.screenshot`'s output are type 2, and an RGBA drawing
    is type 6 -- and a
    decoder that accepts only what is handed to it fails loudly instead of
    guessing. Alpha is dropped rather than composited: every source here is
    opaque, and a decoder that silently invented a background would be deciding
    something this tool has no business deciding.
    """
    width, height, colour, plte, idat = _chunks(data)
    samples = {0: 1, 2: 3, 3: 1, 6: 4}[colour]
    stride = width * samples
    raw = zlib.decompress(idat)
    out = bytearray(stride * height)
    prior = bytes(stride)
    for y in range(height):
        filt = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        _unfilter(line, prior, filt, samples)
        out[y * stride:(y + 1) * stride] = line
        prior = bytes(line)
    return width, height, _to_rgb(bytes(out), colour, plte)


def _chunks(data: bytes) -> tuple[int, int, int, bytes, bytes]:
    """`(width, height, colour type, palette, image data)` out of a PNG's chunks,
    refusing what `decode_rgb` does not read."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    header: tuple[int, int, int] | None = None
    plte = b""
    idat = bytearray()
    at = 8
    while at < len(data):
        length, kind = struct.unpack(">I", data[at:at + 4])[0], data[at + 4:at + 8]
        payload = data[at + 8:at + 8 + length]
        if kind == b"IHDR":
            header = _header(payload)
        elif kind == b"PLTE":
            plte = bytes(payload)
        elif kind == b"IDAT":
            idat += payload
        elif kind == b"IEND":
            break
        at += 12 + length
    if header is None:
        raise ValueError("PNG has no IHDR chunk")
    return header + (plte, bytes(idat))


def _header(payload: bytes) -> tuple[int, int, int]:
    """`(width, height, colour type)`, for bit depth 8 and no interlace only."""
    width, height, depth, colour = struct.unpack(">IIBB", payload[:10])
    if depth != 8 or colour not in (0, 2, 3, 6):
        raise ValueError("PNG is bit depth %d colour type %d, want 8 and 0/2/3/6"
                         % (depth, colour))
    if payload[12] != 0:
        raise ValueError("interlaced PNG")
    return width, height, colour


def _unfilter(line: bytearray, prior: bytes, filt: int, samples: int) -> None:
    """Undo one scanline's filter in place, against the line above it."""
    if filt == 0:
        return
    if filt not in _FILTERS:
        raise ValueError("unknown PNG filter %d" % filt)
    for i in range(len(line)):
        left = line[i - samples] if i >= samples else 0
        up_left = prior[i - samples] if i >= samples else 0
        line[i] = (line[i] + _FILTERS[filt](left, prior[i], up_left)) & 0xFF


def _paeth(left: int, up: int, up_left: int) -> int:
    """The PNG spec's predictor: whichever neighbour is nearest `left + up - up_left`."""
    p = left + up - up_left
    pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
    return left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)


#: What each filter adds back to a byte, from its left, upper and upper-left
#: neighbours: Sub, Up, Average and Paeth. A neighbour off the left edge is 0.
_FILTERS: "dict[int, Callable[[int, int, int], int]]" = {
    1: lambda left, up, up_left: left,
    2: lambda left, up, up_left: up,
    3: lambda left, up, up_left: (left + up) >> 1,
    4: _paeth,
}


def _to_rgb(raw: bytes, colour: int, plte: bytes) -> bytes:
    """Whatever the file stored, as three bytes a pixel. Alpha is dropped."""
    if colour == 2:
        return raw
    if colour == 6:
        return bytes(b for i in range(0, len(raw), 4) for b in raw[i:i + 3])
    if colour == 0:
        return bytes(b for value in raw for b in (value, value, value))
    return bytes(b for index in raw for b in plte[index * 3:index * 3 + 3])


def encode_png(art: Sequence[int], width: int = CELL, height: int = CELL,
               style: StyleLike = None) -> bytes:
    """A 16x16 RGB8 PNG of one tile, as bytes. Deterministic."""
    shades = _style(style).shades
    rgb = bytearray()
    for index in art:
        colour = shades[index]
        rgb += bytes(((colour >> 16) & 0xFF, (colour >> 8) & 0xFF, colour & 0xFF))
    return encode_rgb(width, height, bytes(rgb))


# --- what both generators do with the pictures they have drawn ---------------
#
# `sprite_gen` already reads its PNG encoder, its styles and its text dump out
# of this module, so this is where the last two things the two tools said
# identically go as well: putting the art on disk, and the `--check` that says
# the art on disk is still what the code draws. Whichever of the two is asking,
# the program is the same and only the noun changes.


def write_art(directory: str, art: Mapping[str, Sequence[int]],
              look: styles.Style) -> list[str]:
    """Write `art` into `directory` as PNGs and record the style. Names written.

    Records the style next to the art, because the PNGs carry its colours
    verbatim and `palette.apply` has to install the same four values.

    Writes the *derivation* and only that. `art/hand/` is not a generator's to
    touch -- it has nothing to say about a picture it did not draw, and a
    drawing is left exactly as it was by a restyle, which is correct and is
    also how a set of drawings ends up wrong in a style it was not drawn for.
    """
    os.makedirs(directory, exist_ok=True)
    for name in sorted(art):
        with open(os.path.join(directory, name + ".png"), "wb") as handle:
            handle.write(encode_png(art[name], *_size(art[name]), style=look))
    styles.record(look)
    return sorted(art)


def stale_against(directory: str, art: Mapping[str, Sequence[int]],
                  look: styles.Style) -> list[str]:
    """The names in `art` that `directory` does not already hold byte for byte.

    Missing counts as stale: the question `--check` asks is whether the art a
    clone has is the art this code draws, and a file that is not there fails it
    the same way a file that has drifted does.
    """
    stale: list[str] = []
    for name in sorted(art):
        path = os.path.join(directory, name + ".png")
        if not os.path.exists(path):
            stale.append(name)
        elif open(path, "rb").read() != encode_png(art[name], *_size(art[name]), style=look):
            stale.append(name)
    return stale


def generator_arguments(parser: argparse.ArgumentParser, default_out: str, noun: str) -> None:
    """The four arguments both generators take, so they cannot drift apart."""
    parser.add_argument("--out", default=default_out, help="where to write the PNGs")
    parser.add_argument("--style", default=None, choices=STYLES)
    parser.add_argument("--print", dest="show", metavar="NAME",
                        help="one %s to stdout" % noun[:-1])
    parser.add_argument("--check", action="store_true",
                        help="is --out byte for byte the code's own output? "
                             "(says nothing about art/hand/ -- see tools/art_check.py)")


def generator_main(parser: argparse.ArgumentParser, args: argparse.Namespace,
                   art: Mapping[str, Sequence[int]], noun: str, claim: str) -> int:
    """`--print`, `--check` or write, which is the whole of both tools' `main`.

    `noun` is "tiles" or "poses" and `claim` is what the art is a function of;
    everything else about the two programs was already the same text twice.
    Returns a process exit code.
    """
    look = _style(args.style)
    if args.show:
        if args.show not in art:
            parser.error("no such %s: %s (have %s)"
                         % (noun[:-1], args.show, ", ".join(sorted(art))))
        print(to_text(art[args.show]))
        return 0
    if args.check:
        stale = stale_against(args.out, art, look)
        if stale:
            print("stale or missing: %s" % ", ".join(stale), file=sys.stderr)
            return 1
        print("%d %s in %s are what %s, in %s"
              % (len(art), noun, args.out, claim, look.name))
        return 0
    names = write_art(args.out, art, look)
    print("%d %s -> %s in %s" % (len(names), noun, args.out, look.name))
    return 0



def _size(art: Sequence[int]) -> tuple[int, int]:
    """Width and height of a square raster: CELL for a tile or a pose, TILE for terrain."""
    side = math.isqrt(len(art))
    if side * side != len(art):
        raise ValueError("a raster of %d pixels is not square" % len(art))
    return side, side


