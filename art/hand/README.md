# Hand-drawn tiles

Anything here wins over the generated art of the same name, and nothing else
changes -- art is addressed by name, so the game neither knows nor cares which
of the two it got. The generated art is the bike and the rider
(`art/moto/`) and the glyphs and the logo (`art/tiles/`). **The terrain is
drawings already** -- `art/terrain/`, one PNG a name -- so redraw a terrain tile
in place rather than here.

```bash
cp art/moto/bike00.png art/hand/       # start from the derived one
# ...draw...
python tools/art_check.py              # before you look, and before you commit
pyxel run main.py                      # it is already in the game
```

Delete the file and the derived tile comes back. That is the whole mechanism.

The title screen's logo is sixteen tiles like any other -- `logo_00` to `logo_71` --
so this door is open on it too. For one cell of it, use this directory; for a
whole new logo, `tools/tile_gen.BANNERS` holds it as one 128x32 picture and is
the easier place, and it needs no more than a text editor either.

What every tile name means and where it appears: `python tools/art_check.py --list`.
What every one of them looks like, alone and assembled into the metatiles and
pieces it is seen in: `python tools/art_sheet.py`, one PNG.

## What is still checked

`art/tiles/` and `art/moto/` are a **cache with a proof** --
`tools/tile_gen.py --check` and `tools/sprite_gen.py --check` say they are exactly
what the glyphs and the bike model currently produce, and the tests say the same
-- so hand-editing one of *those* is a thing this project rejects on purpose.
This directory is the exemption, and it is very nearly a blanket one, and the
same two rules hold for a terrain drawing:

- **Four colours, and the right four.** Pyxel maps every source pixel to the
  *nearest* palette entry, so a fifth colour does not fail -- it silently becomes
  one of the four and the picture is not the one you drew.
  `test_a_hand_drawn_tile_is_a_tile` catches it, and `tools/art_check.py` catches
  it sooner and says which pixels. The four are whichever style `art/STYLE`
  names.
- **16x16, and a name something loads** -- 8x8 for the terrain, which is drawn
  on a grid of eight. A file whose stem is not a tile name is refused at
  load rather than ignored, because nothing would ever draw it.

Nothing else. Texture, shading, the weight of the line, whether there is a line
at all, **and where the contour of the road goes**: yours. What the bike touches
is what `maps/tiles.json` declares each tile collides as, never the picture, so
a surface drawn two pixels off is a look and not a bug -- which is why there is
no rule here about it.

## Two things worth knowing

**A shared name is one picture in several places.** A tile such as `t05` is
every cell of that ground in every course. That is the vocabulary working as intended -- a small set of
pictures draws the whole world -- but it means one drawing can show up somewhere
you were not looking.
`python tools/art_check.py --list` says, for every name, what draws it and which
maps use it.

**A drawing is not restyled.** The generators rewrite `art/tiles/` and
`art/moto/` when the style changes and leave this directory and `art/terrain/`
exactly as they were,
which is correct -- they are drawings, and a generator has no idea what one would
look like in another palette. It is also how a set of drawings ends up looking
wrong in a style it was not drawn for.

## Licensing

Whatever you put here is committed to this repository under its MIT licence, so
it has to be yours to give. See [`CONTRIBUTING.md`](../../CONTRIBUTING.md).

**The original's own pictures never come through here.** With a cartridge, the
bike and the rider are drawn in its sprites, read from the player's copy at run
time; without one they are `art/moto/`'s, or whatever this directory draws over
them by name -- `bike00` to `bike31`, `wreck` and the five `rider_*`.
