"""The cartridge's tiles in Pyxel's bank, and which of them are in it.

**Pyxel has three image banks and this game uses all three**: the glyphs, the
kit's terrain, and this one. So the two hundred and fifty-six tiles here are the
one place a cartridge's art can be, and the cartridge has more art than that:
the race's list of loads writes over most of the lettering the screens between
races are written in, which is why a course's art and that lettering **cannot
both be here**. A course's art is not wanted once its race is over, so a screen
takes the bank and the next race takes it back.

Everything drawn out of a cartridge comes through here -- the course, the panel,
the start, the screens -- and everything that draws asks whether there is a
cartridge at all: with none, each of those is drawn from nothing instead.

Nothing here knows what a run is. `ride_draw` draws the race and `front_draw`
the screens around it; this is the bank they share.
"""

import functools
from collections.abc import Callable, Sequence

import pyxel

from game.constants import TILE
from game.course import original_tile
from game.render import assets
from game.rom import graphics
from game.rom.cartridge import SECOND_PALETTE, X_FLIP, Y_FLIP, Cartridge

#: The bank the cartridge's tiles go in: 16 by 16 tiles of 8 px.
ART_BANK = 2
ART_TILES = 256
COLS = 16

#: Which of the cartridge's tiles are in the bank, by name: the course's art, or
#: whatever a screen asked for. See above for why it is one or the other.
COURSE_ART = "course"

#: Whether a cartridge's art is in the bank at all, and how to fill it with the
#: course's again once a screen has borrowed the bank for its lettering.
_art = False
_pixels: Callable[[int], Sequence[int]] | None = None
_loaded = COURSE_ART
#: The tile memory behind what is in the bank, for the few tiles a background id
#: cannot name: a sprite's own, which start below the background's range.
_video: bytes | bytearray = b""
#: ...and the course's own, which is what `course` puts back along with the bank:
#: a screen's tile memory has none of the bike's sprites in it.
_course_video: bytes | bytearray = b""
#: The cartridge the course being ridden came out of, if it came out of one.
_cartridge: Cartridge | None = None
#: How many sprite tiles a side the little image beside the bank holds, each
#: once for every set of flags it is drawn with: two bikes of sixty-four tiles
#: each way up, the rider's own, and the mini-maniacs, with room to spare.
SPRITE_ROOM = 32
_SPRITES: "pyxel.Image | None" = None
_SPRITE_AT: dict[tuple[int, int], tuple[int, int]] = {}
#: The flags that change a sprite's picture; the rest say where it goes.
_FLAGS = X_FLIP | Y_FLIP | SECOND_PALETTE
#: A palette that draws every colour as itself.
IDENTITY = 0b11100100


def install_art(pixels: Callable[[int], Sequence[int]] | None,
                video: bytes | bytearray = b"") -> None:
    """Put a cartridge's background tiles in the bank, or take them away.

    `pixels(tile)` is a tile as sixty-four colour numbers, 0 the lightest: this
    game's four shades run the other way, darkest first, so a colour number `n`
    is shade `3 - n`.

    `video` is the tile memory those came out of, which is what `_video` is for
    and what a race has to hand over as well: a screen sets it through `use`,
    and without this a race would be drawn out of whatever the last screen left.
    """
    global _art, _loaded, _pixels, _video, _course_video
    _art = pixels is not None
    _loaded = COURSE_ART
    _pixels = pixels
    _video = _course_video = video
    _forget_sprites()
    if pixels is None:
        return
    _fill(pixels)


def install_cartridge(cartridge: Cartridge | None) -> None:
    """Hand over the cartridge being played, or `None` for this game's own maps.

    The same shape as `install_art` and for the same reason: which course was
    started is known where a race is started, and not here. Everything the
    original draws -- its panel, its start, its pin, its boxes and its screens --
    is read from this, and with nothing here every one of them is drawn from
    nothing instead.
    """
    global _cartridge
    _cartridge = cartridge
    _forget_sprites()


def paint_terrain(cartridge: Cartridge) -> int:
    """The terrain bank's tiles, repainted in the cartridge's own pictures.
    How many.

    **A tile of the vocabulary is named for its number in the original**
    (`game/course.ORIGINAL_TILE`), so the cartridge's picture of it is found by
    its name, read out of the tile memory a race has -- and a course of this
    game's own is then drawn in the original's art, in the editor and in the
    race it rides, without a file on the disk changing. A name that is no
    number of the original's keeps its own drawing.
    """
    video = graphics.video(cartridge)
    image = pyxel.images[assets.TERRAIN_BANK]
    painted = 0
    for name in assets.terrain_names():
        tile = original_tile(name)
        if tile is None:
            continue
        u, v = assets.terrain_uv(name)
        colours = graphics.pixels(video, tile)
        for row in range(TILE):
            for column in range(TILE):
                image.pset(u + column, v + row, 3 - colours[row * TILE + column])
        painted += 1
    return painted


def rom() -> Cartridge | None:
    """The cartridge being played, if there is one."""
    return _cartridge


def has_art() -> bool:
    """Whether there is a cartridge's art in the bank to draw out of."""
    return _art


def use(name: str, build: Callable[[Cartridge], bytearray]) -> None:
    """Put the tiles `name` stands for in the bank, if they are not in it already.

    A screen says which art it is written in and how to load it, because the
    screens do not agree: one wants the lettering, the title wants the lettering
    and its own drawing, and the logo wants a drawing the cartridge keeps as
    bytes rather than as a list. `build` is called only when the bank has to
    change, which is the frame a screen comes up and no other.
    """
    global _loaded, _video
    if _loaded == name or _cartridge is None:
        return
    _video = build(_cartridge)
    _forget_sprites()
    _fill(functools.partial(graphics.pixels, _video))
    _loaded = name


def sprite_tile(tile: int, x: int, y: int) -> None:
    """One **sprite's** tile, drawn pixel by pixel where it is not transparent.

    Sprites count their tiles from `$8000` and the background does not, so a
    sprite's tile below 128 is nowhere in the bank -- there is no background id
    that names it. The cursor on the title is one of those, and one tile a frame
    drawn by hand is cheaper than a bank rebuilt to hold it.
    """
    if not _video:
        return
    colours = graphics.sprite_pixels(_video, tile)
    for row in range(TILE):
        for column in range(TILE):
            colour = colours[row * TILE + column]
            if colour:
                pyxel.pset(x + column, y + row, 3 - colour)


def sprites(cells: Sequence[tuple[int, int, int, int]], clear: int) -> None:
    """Sprite tiles at places on the screen, each with the object memory's flags.

    For the tiles `tiles` cannot reach: it gets at the bank by a tile's own
    number, which holds only from 128 up, and **a sprite's tile below that is
    nowhere in the background's range at all**. `sprite_tile` draws one of those
    by hand, which is right for a cursor that moves once a screen and wrong for
    something drawn every frame -- so these go into a little image of their own,
    built the first time each tile is asked for with each set of flags.

    The flags are the cartridge's own (`cartridge.X_FLIP`, `Y_FLIP`,
    `SECOND_PALETTE`): a bike half a turn round is the same bike upside down and
    backwards, and the computer's is drawn through the second palette.
    """
    for x, y, tile, flags in cells:
        at = _sprite(tile, flags & _FLAGS)
        if at is not None and _SPRITES is not None:
            pyxel.blt(x, y, _SPRITES, at[0], at[1], TILE, TILE, clear)


def _sprite(tile: int, flags: int) -> tuple[int, int] | None:
    """Where a sprite's tile is in the little image, putting it there if it is
    not in it yet, or nothing at all if there is no tile memory to read."""
    global _SPRITES
    key = (tile, flags)
    if key in _SPRITE_AT:
        return _SPRITE_AT[key]
    if not _video or len(_SPRITE_AT) >= SPRITE_ROOM * SPRITE_ROOM:
        return None
    if _SPRITES is None:
        _SPRITES = pyxel.Image(SPRITE_ROOM * TILE, SPRITE_ROOM * TILE)
    slot = len(_SPRITE_AT)
    at = (slot % SPRITE_ROOM * TILE, slot // SPRITE_ROOM * TILE)
    palette = _object_palette(bool(flags & SECOND_PALETTE))
    colours = graphics.sprite_pixels(_video, tile)
    for row in range(TILE):
        for column in range(TILE):
            source = colours[(TILE - 1 - row if flags & Y_FLIP else row) * TILE
                             + (TILE - 1 - column if flags & X_FLIP else column)]
            # Colour 0 is a sprite's clear one whatever the palette says, and
            # `3 - 0` is the sky, which is what every caller here passes as its
            # `clear`.
            shade = (palette >> 2 * source) & 3 if source else 0
            _SPRITES.pset(at[0] + column, at[1] + row, 3 - shade)
    _SPRITE_AT[key] = at
    return at


def _object_palette(second: bool) -> int:
    """The object palette a sprite is drawn through: the cartridge's, or
    colour for colour with none in hand."""
    return _cartridge.object_palette(second) if _cartridge is not None else IDENTITY


def _forget_sprites() -> None:
    """The little image is of whatever tile memory was in hand, so it goes when
    that does."""
    global _SPRITES
    _SPRITES = None
    _SPRITE_AT.clear()


def course() -> None:
    """Put the course's art back, if a screen has had the bank since.

    **Whoever draws says which of the two it needs**, and both of these return
    at once when the bank already holds it -- so a race asks every frame and
    pays for it only on the frame after a screen. A race that did not ask would
    be drawn in lettering, which is exactly what it looks like.

    **The tile memory goes back too**, because the bike's sprites are read out
    of it: the card before a race is drawn after the race's art is installed,
    and a race that kept the card's memory drew its bikes out of the lettering,
    where their tiles are empty -- no bike at all.
    """
    global _loaded, _video
    if _loaded is COURSE_ART or _pixels is None:
        return
    _fill(_pixels)
    _video = _course_video
    _forget_sprites()
    _loaded = COURSE_ART


def tiles(cells: Sequence[tuple[int, int, int]], clear: int | None = None) -> None:
    """Tiles of the cartridge's own, at places on the screen, out of the bank.

    A **sprite** passes `clear`, because colour 0 of a sprite is the one not
    drawn and the art's colour 0 is the sky; a background tile passes nothing and
    covers what is under it. A sprite indexes the bank by its own number, which
    works because **a sprite counts its tiles from `$8000` and the background's
    ids 128 to 255 land on the same tiles**, and everything drawn this way is
    above 128 either way.
    """
    for x, y, tile in cells:
        pyxel.blt(x, y, ART_BANK, (tile % COLS) * TILE, (tile // COLS) * TILE,
                  TILE, TILE, clear)


def _fill(pixels: Callable[[int], Sequence[int]]) -> None:
    """Two hundred and fifty-six tiles into the bank, sixteen to a row."""
    image = pyxel.images[ART_BANK]
    for tile in range(ART_TILES):
        colours = pixels(tile)
        u, v = (tile % COLS) * TILE, (tile // COLS) * TILE
        image.set(u, v, ["".join("%x" % (3 - colours[row * TILE + x]) for x in range(TILE))
                         for row in range(TILE)])
