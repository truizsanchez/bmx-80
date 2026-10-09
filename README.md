# bmx-80

A 2D side-scrolling motocross game, built with [Pyxel](https://github.com/kitao/pyxel).
160x144, an 8-pixel terrain grid, and four shades of grey.

**The engine is a reimplementation of Motocross Maniacs' own**, rule for rule: integer
arithmetic, the original's tick order, terrain read as tiles. It rides the original's eight
courses, and it is playable from start to finish **without the cartridge**: the courses
are written out in `maps/`, and the screens between races, the band under the view and the
sound effects are this game's own. Given your own copy of the cartridge, it reads the
original's courses, art, screens, music and sound out of it instead.

## Playing it

The releases carry a zip per system with **one file in it**: unzip it anywhere and run
`bmx-80` (Windows: `bmx-80.exe`). No Python, no install, nothing to uninstall.

Windows will warn that the publisher is unknown: the binary is not code-signed. "More
info" then "Run anyway", or build it yourself from the source below.

Your times and your drafts go in a **`bmx-80-data/` folder beside the executable**, so you
can find them, back them up or delete them. Move the executable and it makes a new one;
move the folder with it and you keep your records.

### The keys

The Game Boy's pad is laid on the keyboard the way two hands held it:

| Game Boy | Keyboard | In a race |
|---|---|---|
| the cross | **W A S D** (or the arrows on the screens) | **A** leans back -- a wheelie on the level -- and **D** forward; **W** held at a take-off makes a longer jump |
| A | **K** | the throttle |
| B | **J** | a nitro |
| Start | **Enter** | start, pause |
| Select | **Space** | on the title, the next way to play |

**Esc** leaves a race, goes from the menu back to the title, and from the title quits.

### The screens

The game opens on the original's front end: a title where you choose **SOLO** or **VS
COMPUTER**, then a course (1 to 8) and a level (eAsy, Bumpy, Crazy), a card with the course
record and the time to qualify, the race, and the results, or **TIME UP** and **GAME OVER**
when the clock runs out first. VS 2-PLAYER is on the title as it is on the original, and
asks for a link cable nobody answers, as the original does with none attached.

The title has a fourth row, **FREE RIDE**: any of the eight courses or your own drafts, at
any level, in either **mode** -- *classic*, the original's, or *excessive*, the same race at
sixty steps a second (experimental; its times are not kept as records). There the arrows
belong to whichever of the three things you are choosing -- the course, the level, the mode --
and **Tab** hands them over; **Space** puts the computer's bike in the race or takes it out,
**Enter** starts, **Esc** goes back. The front end itself always plays the original's way.

## Your cartridge

The game reads **only the European release** of Motocross Maniacs for the Game Boy:

| | |
|---|---|
| Title in the header | `MOTOCROSSMANIACS` |
| Size | 32,768 bytes |
| SHA-1 | `956a12a65a1c39948c312303719895bd6f141a61` |

Check yours before you use it:

```bash
sha1sum "Motocross Maniacs (Europe).gb"                            # Linux
shasum -a 1 "Motocross Maniacs (Europe).gb"                        # macOS
certutil -hashfile "Motocross Maniacs (Europe).gb" SHA1           # Windows
```

Then hand it to the game with `--rom` (the file name does not matter; the hash does):

```bash
bmx-80 --rom "Motocross Maniacs (Europe).gb"        # the release
python main.py --rom "Motocross Maniacs (Europe).gb" # from the source
```

With it, the eight courses are read out of the cartridge rather than out of `maps/`, and
drawn in its own art; the title, the course select, the card and the results are its own
screens; the bike is its own sprites; and the race sounds with the original's sound driver,
music included. The first run renders the cartridge's sound once, about fifteen seconds, and
keeps it in a file called `sound.bank` beside your records so that every run after starts at
once. That file is derived from your copy and is yours: it is never shipped, and deleting it
only means it is rendered again.

**Anything else is refused**, with a line on the terminal saying why -- the wrong size, not
Motocross Maniacs, or Motocross Maniacs but another release -- and the game runs as it does
without a cartridge. The cartridge is not in this repository, and this project does not tell
you where to get one: dump your own.

## Other options

```bash
bmx-80 --palette green          # the four shades in the original screen's green
bmx-80 --mode excessive         # FREE RIDE starts on the experimental excessive mode
bmx-80 --ride <course.json>     # straight onto one course file, as the editor rides one
```

**What it has not got:** a second player, and music without a cartridge -- the sound effects
are this game's, the tunes are the cartridge's.

## Running it from the source

Python 3.10 or newer (Pyxel's own floor) and one dependency, which is Pyxel.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

pyxel run main.py
```

To build the release zip yourself, on the system you are on:

```bash
pip install -r requirements-dev.txt
python tools/build_exe.py           # -> dist/bmx-80-<version>-<system>-x64.zip
```

Linux and Windows. macOS is not built, and a Windows executable cannot be built from
Linux: the repository's `release` workflow builds that one on a Windows machine.

## Making a course

A course is JSON, drawn in the editor or written by hand. It is built the way the original
builds its own: a ring of 16 by 256 **metatiles** of 16x16 pixels, and a course is a list of
**pieces** stamped onto it. Where two pieces land on the same cell they are merged tile by
tile, so the shape where one thing meets another never has to be a piece of its own.

- `art/terrain/<name>.png` -- a tile, 8x8, in the four shades. A drawing.
- `maps/tiles.json` -- what each tile **collides as**: solid, soft, no wheelie, a rock, and
  which of the engine's 32 directions it runs in. Declared, never read off the picture.
- `maps/metatiles.json` -- four tile names each, top left to bottom right. `-` lets whatever
  is underneath through.
- `maps/pieces.json` -- a grid of metatile names: what a course puts down. `.` stamps nothing.
- `maps/labels.json` -- a name you can read and a kind (ground, slope up, curve, sign...)
  for every metatile and piece. The editor's palette is grouped by kind, and the name shows
  on the status line under the pointer.
- `maps/courses/<name>.json` -- the pieces at `[row, col, name]`, the crates at
  `[kind, row, col]`, the three levels' time limits, and the stretches where the computer's
  bike is put back.

The tiles, metatiles and pieces are the original's, under its own numbers in hex (`t45` is its
tile 0x45, `p57` its piece 0x57), and the eight courses are the original's eight written in
them. `python tools/vocab_from_rom.py --rom <file.gb> --check` builds every course out of
`maps/` and compares it, cell by cell and ride by ride, with the one your cartridge builds.
`maps/read.py` describes the files at more length.

```bash
python main.py --edit <name>                  # a course by name, or a new draft in maps/drafts/
python main.py --edit <name> --enhanced       # ...a new draft in the enhanced vocabulary
python main.py --edit <name> --rom <file.gb>  # ...its tiles in your cartridge's own art
```

Pick a piece -- or a single metatile -- from the palette and click to stamp it **on top**;
what is under the pointer is already drawn merged, so what you see is what the game builds.
Drag along a row to repeat it, right-click takes away what is on top, ALT-click picks it up.
The order of the stampings is the merge: `TAB` walks what is stacked under the pointer and
`[` `]` move it down or up. The `things` tab puts down crates, and a drag along a surface
lays a stretch where the computer's bike is put back; the three clocks are on the toolbar.
`Z` zooms, `C` shows the collision, `G` the game's view from the pointer, `O` the whole lap,
and `R` rides what is drawn in a window of its own. The status line names whatever the pointer
is over -- a piece, a metatile, a thing, and what is stacked on the map under it. The orange
lines along the ground are the stretches where the computer's bike is put back when it falls
behind. `CTRL-S` saves, `CTRL-Z`/`CTRL-Y` undo
and redo, `H` lists the keys. Every click goes to `./editor.log`.

**Which directory a course is in is what kind of course it is**; nothing in the file says:

- `maps/courses/` holds the courses the project ships: committed, and on the front end.
- `maps/drafts/` is yours: gitignored, and the `custom` tab of FREE RIDE -- with a cartridge
  or without one, drawn in the cartridge's art and sounding with one of its tunes when there is
  one.
- `maps/enhanced/` is the **enhanced** vocabulary: the original's with this game's own tiles,
  metatiles and pieces added over it. Its `drafts/` are yours and on FREE RIDE with the rest;
  in the editor its own pieces are the `extra` tab.

A name may live in one directory only; a name in two is refused at startup rather than
resolved, so a copy has to be renamed. **No test measures what a course is like**: the suite
asks that every course loads, that its schema is clean, that it reads back as itself and
that it draws. So a course can be retuned for how it plays without a test in the way.

## Working on it

[`CONTRIBUTING.md`](CONTRIBUTING.md) is how to set up, run the checks and send a change.
You do not need Python to improve the art: a terrain tile is a drawing in `art/terrain/`,
redrawn in place, and a PNG in `art/hand/` wins over the generated picture of the same name.

## Licence

MIT. See [`LICENSE`](LICENSE).

Motocross Maniacs is Konami's. This project is not affiliated with or endorsed by Konami, and
the eight courses in `maps/courses/` and the vocabulary they are written in are the original
game's, not this project's to license.

**Part of `tools/editor/` is somebody else's, and it is MIT too.**
[`tools/editor/widgets/`](tools/editor/widgets/) is Pyxel's own editor toolkit, vendored for
the map editor's mouse capture, and [`tools/editor/palette.py`](tools/editor/palette.py) is
adapted from Pyxel's editor as well. Copyright (c) 2018-2026 Takashi Kitao; the licence text
is [`tools/editor/widgets/LICENSE-pyxel`](tools/editor/widgets/LICENSE-pyxel) and every file
says at the top where it came from and what was edited.
